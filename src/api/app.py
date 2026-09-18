from __future__ import annotations

import asyncio
import json
import os
import secrets
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.gongzuo_knowledge.library import Library
from src.gongzuo_knowledge.library_router import router as library_router
from src.integrations.task_sources import TaskSources
from src.integrations.linear import LinearConnection, LinearService
from src.integrations.router import router as integrations_router
from src.config import ConfigManager
from src.database import DatabaseManager
from src.agent_runtime import CodexExecutor, OpenCodeExecutor
from src.gongzuo import GongzuoRepository, GongzuoService
from src.gongzuo.manual_results import router as results_router
from src.gongzuo.router import router as work_router
from src.gongzuo_knowledge import GongzuoKnowledgeRepository, GongzuoKnowledgeService
from src.gongzuo_knowledge.router import router as knowledge_router
from src.gongzuo_runtime.repository import GongzuoRuntimeRepository
from src.gongzuo_runtime.service import GongzuoRuntimeService
from src.gongzuo_runtime.router import router as runtime_router
from src.gongzuo_runtime.models import RunOut
from src.gongzuo_runtime.worker import GongzuoWorker, ServiceWorkerClient

ROOT = Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    config = ConfigManager(project_root=ROOT)
    manager = DatabaseManager(config)
    work = GongzuoService(GongzuoRepository(manager.postgres()))
    roots = {key: Path(os.environ.get(f'GONGZUO_{key.upper()}_KNOWLEDGE_ROOT', str(ROOT / '.runtime/knowledge' / key))).expanduser().resolve() for key in ('personal', 'team')}
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)
    knowledge = GongzuoKnowledgeService(GongzuoKnowledgeRepository(manager.postgres()), roots=roots, gongzuo_service=work)
    engines = {'codex': CodexExecutor(command=os.environ.get('CODEX_COMMAND', 'codex')), 'opencode': OpenCodeExecutor(command=os.environ.get('OPENCODE_COMMAND', 'opencode'))}
    registration = {key: secrets.token_urlsafe(32) for key in roots}
    runtime = GongzuoRuntimeService(repository=GongzuoRuntimeRepository(manager.postgres()), gongzuo_service=work, executors=engines, runtime_root=ROOT / '.runtime/runs', repository_root=None, registration_tokens=registration, capability_provider=knowledge.published_context)
    knowledge.run_reader = lambda workspace, run_id: RunOut.model_validate(runtime.get_run(workspace, run_id)).model_dump(by_alias=True, mode='json')

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager.postgres().open()
        runtime.recover_expired_leases()
        tasks = []
        if os.environ.get('GONGZUO_LOCAL_WORKER', '1') == '1':
            # The personal worker belongs to this installation. Reuse its identity after restart.
            file = ROOT / '.runtime/local-worker.json'
            if file.exists():
                identity = json.loads(file.read_text())
                try:
                    runtime.authenticate_worker('personal', identity['id'], identity['worker_token'])
                except PermissionError:
                    identity = None
            else:
                identity = None
            if identity is None:
                identity = runtime.register_machine('personal', registration_token=registration['personal'], name='这台电脑', capacity=1, engines=list(engines), runtimes=['native'], images=[], labels={'local': 'true'})
                file.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w') as handle:
                    json.dump({'id': identity['id'], 'worker_token': identity['worker_token']}, handle)
            worker = GongzuoWorker(client=ServiceWorkerClient(runtime, 'personal', identity['id'], identity['worker_token']), executors=engines, runtime_root=ROOT / '.runtime/executions', machine_id=identity['id'])
            async def loop():
                while True:
                    try:
                        runtime.recover_expired_leases()
                        await worker.client.heartbeat([], 30)
                        await worker.execute_once()
                    except Exception:
                        logging.exception("本机执行节点暂时失败，将重试")
                    await asyncio.sleep(1)
            tasks.append(asyncio.create_task(loop()))
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            manager.close()

    app = FastAPI(title='共作工作台', version='0.1.0', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.state.database_manager = manager
    app.state.gongzuo_service = work
    app.state.gongzuo_knowledge_service = knowledge
    app.state.gongzuo_runtime_service = runtime
    app.state.executors = engines
    app.state.root = ROOT
    app.state.linear = LinearService(manager.postgres(), LinearConnection(ROOT), work)
    app.state.library = Library(manager.postgres(), roots)
    app.state.task_sources = TaskSources(ROOT, app.state.library)
    runtime.task_sources = app.state.task_sources

    @app.middleware('http')
    async def local_boundary(request: Request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and origin not in {'http://127.0.0.1:8010', 'http://localhost:8010', 'http://127.0.0.1:5180', 'http://localhost:5180'}:
                return JSONResponse({'detail': '请从本机工作台页面发起操作'}, status_code=403)
        return await call_next(request)

    app.include_router(work_router)
    app.include_router(results_router)
    app.include_router(integrations_router)
    app.include_router(library_router)
    app.include_router(knowledge_router)
    app.include_router(runtime_router)

    @app.get('/api/health')
    def health():
        result = manager.postgres().health_check()
        return {'status': 'ok', 'app': '共作', 'database': result.database, 'version': '0.1.0'}

    @app.get('/api/gongzuo/config')
    def configuration():
        return {'workspaces': ['personal', 'team'], 'defaultWorkspace': 'personal', 'identityMode': 'local-user'}

    dist = ROOT / 'web/dist'
    if (dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path.startswith('api/'):
            return JSONResponse({'detail': '接口不存在'}, status_code=404)
        if not (dist / 'index.html').exists():
            return JSONResponse({'detail': '前端尚未构建，请运行 scripts/workbench.py setup'}, status_code=503)
        return FileResponse(dist / 'index.html')

    return app

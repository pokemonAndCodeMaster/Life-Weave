from __future__ import annotations

import os
import secrets
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
from src.gongzuo_runtime.local_workers import LocalWorkers

ROOT = Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    (ROOT / '.runtime').mkdir(exist_ok=True)
    (ROOT / '.runtime').chmod(0o700)
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

    local_workers = LocalWorkers(ROOT, runtime, engines, registration)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager.postgres().open()
        runtime.recover_expired_leases()
        try:
            await local_workers.initialize()
            yield
        finally:
            await local_workers.close()
            manager.close()

    app = FastAPI(title='共作工作台', version='0.1.0', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.state.database_manager = manager
    app.state.gongzuo_service = work
    app.state.gongzuo_knowledge_service = knowledge
    app.state.gongzuo_runtime_service = runtime
    app.state.executors = engines
    app.state.local_workers = local_workers
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

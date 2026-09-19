from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from src.config.environment import get_env
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.lifeweave_knowledge.library import Library
from src.lifeweave_knowledge.library_router import router as library_router
from src.integrations.task_sources import TaskSources
from src.integrations.linear import LinearConnection, LinearService
from src.integrations.router import router as integrations_router
from src.config import ConfigManager
from src.database import DatabaseManager
from src.agent_runtime import CodexExecutor, OpenCodeExecutor
from src.lifeweave import LifeWeaveRepository, LifeWeaveService
from src.lifeweave.manual_results import router as results_router
from src.lifeweave.router import router as work_router
from src.lifeweave.continuation import WorkContinuation
from src.lifeweave.continuation_router import router as continuation_router
from src.lifeweave.conversations import Conversations, research_support
from src.lifeweave.conversation_interpreter import ConversationInterpreter
from src.lifeweave.conversation_router import router as conversation_router
from src.lifeweave.research_outputs import ResearchOutputs, router as research_outputs_router
from src.lifeweave.research_archive import ResearchArchive, router as research_archive_router
from src.lifeweave_knowledge import LifeWeaveKnowledgeRepository, LifeWeaveKnowledgeService
from src.lifeweave_knowledge.router import router as knowledge_router
from src.lifeweave_runtime.repository import LifeWeaveRuntimeRepository
from src.lifeweave_runtime.service import LifeWeaveRuntimeService
from src.lifeweave_runtime.router import router as runtime_router
from src.lifeweave_runtime.models import RunOut
from src.lifeweave_runtime.local_workers import LocalWorkers

ROOT = Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    (ROOT / '.runtime').mkdir(exist_ok=True)
    (ROOT / '.runtime').chmod(0o700)
    config = ConfigManager(project_root=ROOT)
    manager = DatabaseManager(config)
    work = LifeWeaveService(LifeWeaveRepository(manager.postgres()))
    roots = {key: Path(get_env(f'LIFEWEAVE_{key.upper()}_KNOWLEDGE_ROOT', str(ROOT / '.runtime/knowledge' / key))).expanduser().resolve() for key in ('personal', 'team')}
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)
    knowledge = LifeWeaveKnowledgeService(LifeWeaveKnowledgeRepository(manager.postgres()), roots=roots, lifeweave_service=work)
    engines = {'codex': CodexExecutor(command=os.environ.get('CODEX_COMMAND', 'codex')), 'opencode': OpenCodeExecutor(command=os.environ.get('OPENCODE_COMMAND', 'opencode'))}
    registration = {key: secrets.token_urlsafe(32) for key in roots}
    runtime = LifeWeaveRuntimeService(repository=LifeWeaveRuntimeRepository(manager.postgres()), lifeweave_service=work, executors=engines, runtime_root=ROOT / '.runtime/runs', repository_root=None, registration_tokens=registration, capability_provider=knowledge.published_context)
    knowledge.run_reader = lambda workspace, run_id: RunOut.model_validate(runtime.get_run(workspace, run_id)).model_dump(by_alias=True, mode='json')

    local_workers = LocalWorkers(ROOT, runtime, engines, registration)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager.postgres().open()
        runtime.recover_expired_leases()
        conversations.recover()
        try:
            await local_workers.initialize()
            if os.environ.get('LIFEWEAVE_ARCHIVE_WORKER','1') == '1' and get_env('LIFEWEAVE_LOCAL_WORKER','1') != '0':
                await app.state.research_archive.start()
            yield
        finally:
            await app.state.research_archive.close()
            await conversations.close()
            await local_workers.close()
            manager.close()

    app = FastAPI(title='LifeWeave · 经纬', version='0.1.0', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.state.database_manager = manager
    app.state.lifeweave_service = work
    app.state.lifeweave_knowledge_service = knowledge
    app.state.lifeweave_runtime_service = runtime
    app.state.executors = engines
    app.state.local_workers = local_workers
    app.state.root = ROOT
    app.state.linear = LinearService(manager.postgres(), LinearConnection(ROOT), work)
    app.state.library = Library(manager.postgres(), roots)
    app.state.task_sources = TaskSources(ROOT, app.state.library)
    runtime.task_sources = app.state.task_sources
    app.state.work_continuation = WorkContinuation(work, runtime)
    app.state.research_outputs = ResearchOutputs(work, runtime, app.state.library, ROOT)
    app.state.research_archive = ResearchArchive(ROOT, app.state.research_outputs, app.state.linear.connection)
    app.state.library.reference_provider = app.state.research_outputs.document_references
    conversations = Conversations(manager.postgres(), work, runtime, app.state.work_continuation,
                                 app.state.task_sources, ConversationInterpreter(ROOT, local_workers))
    conversations.outputs = app.state.research_outputs
    app.state.conversations = conversations
    runtime.support_provider = lambda workspace, item_id: research_support(conversations,workspace,item_id)

    @app.middleware('http')
    async def local_boundary(request: Request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and origin not in {str(request.base_url).rstrip('/'), 'http://127.0.0.1:8010', 'http://localhost:8010', 'http://127.0.0.1:5180', 'http://localhost:5180'}:
                return JSONResponse({'detail': '请从本机工作台页面发起操作'}, status_code=403)
        if request.url.path == '/api/gongzuo' or request.url.path.startswith('/api/gongzuo/'):
            target = '/api/lifeweave' + request.url.path[len('/api/gongzuo'):]
            # Preserve encoded path/query and method/body for saved clients and references.
            target = request.scope.get('raw_path', target.encode()).decode('ascii').replace('/api/gongzuo', '/api/lifeweave', 1)
            if request.url.query:
                target += '?' + request.url.query
            return RedirectResponse(target, status_code=308)
        return await call_next(request)

    app.include_router(work_router)
    app.include_router(continuation_router)
    app.include_router(conversation_router)
    app.include_router(research_outputs_router)
    app.include_router(research_archive_router)
    app.include_router(results_router)
    app.include_router(integrations_router)
    app.include_router(library_router)
    app.include_router(knowledge_router)
    app.include_router(runtime_router)

    @app.get('/api/health')
    def health():
        result = manager.postgres().health_check()
        return {'status': 'ok', 'app': 'LifeWeave · 经纬', 'database': result.database, 'version': '0.1.0'}

    @app.get('/api/lifeweave/config')
    def configuration():
        return {'workspaces': ['personal', 'team'], 'defaultWorkspace': 'personal', 'identityMode': 'local-user'}

    dist = ROOT / 'web/dist'
    @app.get('/favicon.svg', include_in_schema=False)
    def favicon():
        return FileResponse(ROOT / 'web/public/favicon.svg', media_type='image/svg+xml')
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

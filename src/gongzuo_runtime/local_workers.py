"""The local installation owns optional workers, independently for each space."""
import asyncio
import json
import logging
import os
from pathlib import Path
from .worker import GongzuoWorker, ServiceWorkerClient


class LocalWorkers:
    def __init__(self, root, runtime, engines, registration):
        self.root = root
        self.runtime = runtime
        self.engines = engines
        self.registration = registration
        self.tasks = {}
        self.identities = {}
        self.lock = asyncio.Lock()

    def file(self, workspace):
        return self.root / '.runtime' / f'local-execution-{workspace}.json'

    def status(self, workspace):
        file = self.file(workspace)
        config = json.loads(file.read_text()) if file.exists() else {'enabled': workspace == 'personal', 'useLocalAccount': workspace == 'personal'}
        return {**config, 'running':workspace in self.tasks and not self.tasks[workspace].done()}

    async def initialize(self):
        if os.environ.get('GONGZUO_LOCAL_WORKER', '1') != '1':
            return
        for workspace in ('personal', 'team'):
            if self.status(workspace)['enabled']:
                await self.start(workspace)

    async def configure(self, workspace, enabled, use_local_account):
        async with self.lock:
            if enabled and workspace == 'team' and not use_local_account:
                raise ValueError('启用本机团队执行需要明确选择使用当前本机 CLI 账号')
            if not enabled and workspace in self.identities:
                machine_id = self.identities[workspace]['id']
                machines = self.runtime.list_machines(workspace)
                if any(row['id'] == machine_id and row.get('active_runs', 0) for row in machines):
                    raise ValueError('本机仍有任务运行，请等待完成或取消委托后再停用')
                self.runtime.machine_action(workspace, machine_id, 'pause')
                task = self.tasks.pop(workspace, None)
                if task:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            if enabled:
                await self.start(workspace)
                self.runtime.machine_action(workspace, self.identities[workspace]['id'], 'enable')
            file = self.file(workspace)
            file.parent.mkdir(parents=True, exist_ok=True)
            temporary = file.with_suffix('.tmp')
            temporary.write_text(json.dumps({'enabled':enabled, 'useLocalAccount':use_local_account}))
            temporary.chmod(0o600)
            os.replace(temporary, file)
            return self.status(workspace)

    async def start(self, workspace):
        if workspace in self.tasks and not self.tasks[workspace].done():
            return
        file = self.root / '.runtime' / ('local-worker.json' if workspace == 'personal' else 'local-team-worker.json')
        identity = json.loads(file.read_text()) if file.exists() else None
        if identity:
            try:
                self.runtime.authenticate_worker(workspace, identity['id'], identity['worker_token'])
            except (PermissionError, KeyError):
                identity = None
        if identity is None:
            identity = self.runtime.register_machine(workspace, registration_token=self.registration[workspace], name='这台电脑' if workspace == 'personal' else '这台电脑 · 团队', capacity=1, engines=list(self.engines), runtimes=['native'], images=[], labels={'local':'true'})
            file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as handle:
                json.dump({'id':identity['id'], 'worker_token':identity['worker_token']}, handle)
        self.identities[workspace] = identity
        # Only this explicitly enabled local worker gets these account sources.
        # Remote/team worker defaults continue to require explicit credentials.
        authentication = {
            'GONGZUO_TEAM_CODEX_HOME':os.environ.get('CODEX_HOME', str(Path.home()/'.codex')),
            'GONGZUO_TEAM_OPENCODE_DATA_HOME':os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')),
            'GONGZUO_TEAM_OPENCODE_CONFIG_HOME':os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')),
        } if workspace == 'team' else {}
        worker = GongzuoWorker(client=ServiceWorkerClient(self.runtime, workspace, identity['id'], identity['worker_token']), executors=self.engines, runtime_root=self.root/'.runtime/executions', machine_id=identity['id'], authentication_sources=authentication)
        async def loop():
            while True:
                try:
                    self.runtime.recover_expired_leases()
                    await worker.client.heartbeat([], 30)
                    await worker.execute_once()
                except Exception:
                    logging.exception('本机执行节点暂时失败，将重试')
                await asyncio.sleep(1)
        self.tasks[workspace] = asyncio.create_task(loop())

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()

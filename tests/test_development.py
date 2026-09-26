"""The web development chain advances only from real persisted Run results."""
import json
import subprocess
from types import SimpleNamespace
import pytest
from psycopg.types.json import Jsonb

from test_live_database import dedicated_client, post

from src.agent_runtime.opencode_executor import OpenCodeExecutor
from src.agent_runtime.tree_snapshot import tree_sha256


def test_opencode_readonly_denies_shell_edit_and_subagents():
    request = SimpleNamespace(sandbox='read-only', environment={}, inherit_environment=False)
    config = json.loads(OpenCodeExecutor.environment_for(request)['OPENCODE_CONFIG_CONTENT'])
    assert all(config['permission'][tool] == 'deny' for tool in ('edit', 'bash', 'task', 'external_directory'))


def repository(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').write_text('# Fixture\n')
    for args in [('init', '-q'), ('config', 'user.name', 'Test'),
                 ('config', 'user.email', 'test@example.local'), ('add', '.'),
                 ('commit', '-qm', 'fixture')]:
        subprocess.run(['git', *args], cwd=root, check=True)
    return root


def finish(client, run_id, result):
    client.app.state.database_manager.postgres().execute(
        "UPDATE workbench.t_lifeweave_run SET state='succeeded', result=%s WHERE id=%s",
        (result, run_id))


def readonly_checkout(client, tmp_path, source, run_id):
    client.app.state.development.project_root = tmp_path
    target = tmp_path / '.runtime/executions' / run_id / 'repo'
    target.parent.mkdir(parents=True)
    subprocess.run(['git', 'clone', '-q', str(source), str(target)], check=True)
    client.app.state.database_manager.postgres().execute(
        'UPDATE workbench.t_lifeweave_run SET environment_snapshot=%s WHERE id=%s',
        (Jsonb({'actualDirectory': str(target), 'readonlyTreeSha256': tree_sha256(target)}), run_id))
    return target


def test_development_plan_review_implementation_and_idempotence(dedicated_client, tmp_path):
    client = dedicated_client
    root = repository(tmp_path)
    item = post(client, '/items', {'itemType': 'requirement', 'title': 'Add a useful feature'})
    path = '/api/lifeweave/personal'
    choices = client.get(f'{path}/items/{item["id"]}/development/choices').json()
    assert choices['recommendedAgentId'] == 'development'
    payload = {'requestId': 'test-1', 'itemId': item['id'], 'instruction': 'Add one useful feature and verify it',
               'repositoryPath': str(root), 'agentId': 'development', 'engine': 'codex',
               'methodId': choices['methodId'], 'knowledgeRefs': [], 'reviewMode': 'independent'}
    created = client.post(f'{path}/development', json=payload)
    assert created.status_code == 202, created.text
    first = created.json()
    assert first['status'] == 'planning' and first['planRunId']
    assert client.post(f'{path}/development', json=payload).json()['id'] == first['id']
    changed = client.post(f'{path}/development', json={**payload, 'instruction': 'a different task'})
    assert changed.status_code == 409
    readonly_checkout(client, tmp_path, root, first['planRunId'])
    finish(client, first['planRunId'], 'User behavior: useful feature. Impact: README. Steps: edit and verify. Risk: low. 自检: check output and tests.')
    service = client.app.state.development
    service.advance(first['id'])
    reviewing = service.get('personal', first['id'])
    assert reviewing['status'] == 'reviewing' and reviewing['reviewRunId']
    assert reviewing['planSha256']
    readonly_checkout(client, tmp_path, root, reviewing['reviewRunId'])
    finish(client, reviewing['reviewRunId'], 'Reviewed request and plan.\nREVIEW_DECISION: PASS')
    service.advance(first['id'])
    implementing = service.get('personal', first['id'])
    assert implementing['status'] == 'implementing' and implementing['implementationRunId']
    finish(client, implementing['implementationRunId'], 'Changed README; test command passed.')
    service.advance(first['id'])
    done = service.get('personal', first['id'])
    assert done['status'] == 'awaiting_acceptance'
    assert len({done['planRunId'], done['reviewRunId'], done['implementationRunId']}) == 3
    stage_calls = client.app.state.database_manager.postgres().fetch_all(
        "SELECT operation,state,run_id,output_ref FROM workbench.lifeweave_plugin_call "
        "WHERE assignment_id=%s AND plugin_id='lifeweave.development'", (first['id'],))
    assert {(call['operation'], call['run_id'], call['state']) for call in stage_calls} == {
        ('plan', done['planRunId'], 'succeeded'),
        ('review', done['reviewRunId'], 'succeeded'),
        ('implement', done['implementationRunId'], 'succeeded')}
    assert all(call['output_ref']['stageOutcome'] == 'succeeded' for call in stage_calls)
    for call in stage_calls[:2]:
        response = client.post(f'{path}/evaluations', json={
            'itemId': item['id'], 'targetKind': 'plugin', 'pluginCallId': next(
                entry['id'] for entry in client.get(f'{path}/items/{item["id"]}/plugin-process').json()['calls']
                if entry['plugin_id'] == 'lifeweave.development' and entry['operation'] == call['operation']),
            'title': 'Check the stage', 'instruction': 'Inspect stage result',
            'criteria': 'The stage is recorded with the source Run'})
        assert response.status_code == 201, response.text
    assert client.get(f'{path}/items/{item["id"]}/development').json()['items'][0]['id'] == first['id']
    sandbox = tmp_path / '.runtime/executions/personal/fake-run/repo'
    sandbox.mkdir(parents=True)
    for args in [('init', '-q'), ('config', 'user.name', 'Test'), ('config', 'user.email', 'test@example.local')]:
        subprocess.run(['git', *args], cwd=sandbox, check=True)
    (sandbox / 'README.md').write_text('# Before\n')
    subprocess.run(['git', 'add', '.'], cwd=sandbox, check=True)
    subprocess.run(['git', 'commit', '-qm', 'before'], cwd=sandbox, check=True)
    sandbox_base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sandbox, text=True).strip()
    (sandbox / 'README.md').write_text('# After\n')
    subprocess.run(['git', 'add', 'README.md'], cwd=sandbox, check=True)
    subprocess.run(['git', 'commit', '-qm', 'agent result'], cwd=sandbox, check=True)
    (sandbox / 'new.py').write_text('print("actual code")\n')
    cache = sandbox / '__pycache__/new.cpython-310.pyc'
    cache.parent.mkdir()
    cache.write_bytes(b'generated bytecode')
    generated = sandbox / '.agents/skills/test/SKILL.md'
    generated.parent.mkdir(parents=True)
    generated.write_text('# generated input\n')
    manifest = sandbox / '.lifeweave/capability-manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{}\n')
    service.project_root = tmp_path
    client.app.state.database_manager.postgres().execute(
        'UPDATE workbench.t_lifeweave_run SET environment_snapshot=%s WHERE id=%s',
        (Jsonb({'actualDirectory': str(sandbox), 'materializedCapabilities': ['.agents/skills/test/SKILL.md']}), done['implementationRunId']))
    client.app.state.database_manager.postgres().execute(
        'UPDATE workbench.lifeweave_development_assignment SET repository_revision=%s WHERE id=%s',
        (sandbox_base, done['id']))
    diff = client.get(f'{path}/development/{first["id"]}/diff').json()
    assert diff['fileCount'] == 2
    assert diff['generatedArtifactsExcluded'] == ['__pycache__/new.cpython-310.pyc']
    assert '+# After' in diff['patch'] and 'print("actual code")' in diff['patch']
    assert 'generated input' not in diff['patch']


def test_development_review_failure_blocks_implementation(dedicated_client, tmp_path):
    client = dedicated_client
    root = repository(tmp_path)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Fix a bug'})
    path = '/api/lifeweave/personal'
    created = client.post(f'{path}/development', json={
        'requestId': 'test-block', 'itemId': item['id'], 'instruction': 'Fix the bug',
        'repositoryPath': str(root), 'reviewMode': 'independent'}).json()
    service = client.app.state.development
    readonly_checkout(client, tmp_path, root, created['planRunId'])
    finish(client, created['planRunId'], 'Plan a precise fix with checks. This is more than eighty characters so the planning gate can proceed. 自检 done.')
    service.advance(created['id'])
    reviewing = service.get('personal', created['id'])
    readonly_checkout(client, tmp_path, root, reviewing['reviewRunId'])
    finish(client, reviewing['reviewRunId'], 'Missing regression check. REVIEW_DECISION: NEEDS_REVISION')
    service.advance(created['id'])
    blocked = service.get('personal', created['id'])
    assert blocked['status'] == 'blocked' and blocked['implementationRunId'] is None


def test_readonly_stage_change_blocks_next_stage(dedicated_client, tmp_path):
    client = dedicated_client
    root = repository(tmp_path)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'A read-only stage must stay read-only'})
    created = client.post('/api/lifeweave/personal/development', json={
        'requestId': 'test-readonly-bypass', 'itemId': item['id'], 'instruction': 'Update the README',
        'repositoryPath': str(root), 'reviewMode': 'self'}).json()
    checkout = readonly_checkout(client, tmp_path, root, created['planRunId'])
    (checkout / 'README.md').write_text('# Mutated during planning\n')
    finish(client, created['planRunId'], 'The intended change is a README update. The plan identifies the current content, one-file scope, and a verification. 自检 done.')
    client.app.state.development.advance(created['id'])
    blocked = client.app.state.development.get('personal', created['id'])
    assert blocked['status'] == 'blocked'
    assert '只读阶段修改' in blocked['error']
    assert blocked['implementationRunId'] is None


def test_readonly_stage_ignored_file_blocks_next_stage(dedicated_client, tmp_path):
    client = dedicated_client
    root = repository(tmp_path)
    (root / '.gitignore').write_text('cache/\n')
    subprocess.run(['git', 'add', '.gitignore'], cwd=root, check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.local',
                    'commit', '-qm', 'ignore generated files'], cwd=root, check=True)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'A read-only stage must not create ignored files'})
    created = client.post('/api/lifeweave/personal/development', json={
        'requestId': 'test-readonly-ignored', 'itemId': item['id'], 'instruction': 'Update the README',
        'repositoryPath': str(root), 'reviewMode': 'self'}).json()
    checkout = readonly_checkout(client, tmp_path, root, created['planRunId'])
    cache = checkout / 'cache/changed.txt'
    cache.parent.mkdir()
    cache.write_text('written during planning\n')
    finish(client, created['planRunId'], 'The intended change is a README update. The plan identifies the current content, one-file scope, and a verification. 自检 done.')
    client.app.state.development.advance(created['id'])
    blocked = client.app.state.development.get('personal', created['id'])
    assert blocked['status'] == 'blocked'
    assert '只读阶段修改' in blocked['error']
    assert blocked['implementationRunId'] is None


@pytest.mark.parametrize('bypass', ['assume-unchanged', 'core-worktree'])
def test_readonly_snapshot_catches_git_metadata_bypass(dedicated_client, tmp_path, bypass):
    client = dedicated_client
    root = repository(tmp_path)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Git metadata must not hide a read-only edit'})
    created = client.post('/api/lifeweave/personal/development', json={
        'requestId': f'test-readonly-{bypass}', 'itemId': item['id'], 'instruction': 'Update the README',
        'repositoryPath': str(root), 'reviewMode': 'self'}).json()
    checkout = readonly_checkout(client, tmp_path, root, created['planRunId'])
    (checkout / 'README.md').write_text('# Mutated during planning\n')
    if bypass == 'assume-unchanged':
        subprocess.run(['git', 'update-index', '--assume-unchanged', 'README.md'], cwd=checkout, check=True)
    else:
        subprocess.run(['git', 'config', 'core.worktree', str(root)], cwd=checkout, check=True)
    hidden = subprocess.check_output(['git', 'diff', '--name-only', created['repositoryRevision']],
                                     cwd=checkout, text=True)
    assert hidden == ''  # The previous Git-only guard would have missed this edit.
    finish(client, created['planRunId'], 'The intended change is a README update. The plan identifies the current content, one-file scope, and a verification. 自检 done.')
    client.app.state.development.advance(created['id'])
    blocked = client.app.state.development.get('personal', created['id'])
    assert blocked['status'] == 'blocked'
    assert '只读阶段修改' in blocked['error']
    assert blocked['implementationRunId'] is None


def test_opencode_requires_recent_successful_explicit_model_in_same_workspace(dedicated_client, tmp_path, monkeypatch):
    monkeypatch.setattr('src.lifeweave.development.OPENCODE_DEVELOPMENT_ENABLED', True)
    client = dedicated_client
    root = repository(tmp_path)
    item = post(client, '/items', {'itemType': 'requirement', 'title': 'Document fixture'})
    path = '/api/lifeweave/personal'
    payload = {'requestId': 'opencode-1', 'itemId': item['id'], 'instruction': 'Update the fixture README',
               'repositoryPath': str(root), 'engine': 'opencode', 'model': 'opencode/mimo-v2.5-free',
               'reviewMode': 'self'}
    assert not client.get(f'{path}/items/{item["id"]}/development/choices').json()['executors']['opencode']['available']
    assert client.post(f'{path}/development', json=payload).status_code == 409
    run = client.app.state.development.runtime.create_run('personal', item_id=item['id'], instruction='probe',
                                                           engine='opencode', model=payload['model'], directory=str(root))
    database = client.app.state.database_manager.postgres()
    database.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded',result='probe response',exit_code=0,finished_at=now(),"
                     "environment_snapshot=%s WHERE id=%s",
                     (Jsonb({'effectiveModel': payload['model']}), run['id']))
    choices = client.get(f'{path}/items/{item["id"]}/development/choices').json()
    assert choices['executors']['opencode']['available']
    assert choices['executors']['opencode']['verifiedModel'] == payload['model']
    assert client.post(f'{path}/development', json={**payload, 'model': 'another/model'}).status_code == 409
    assert client.get(f'/api/lifeweave/team/items/{item["id"]}/development/choices').status_code == 404
    created = client.post(f'{path}/development', json=payload)
    assert created.status_code == 202, created.text
    plan = client.get(f'{path}/runs/{created.json()["planRunId"]}').json()
    assert plan['engine'] == 'opencode' and plan['model'] == payload['model']

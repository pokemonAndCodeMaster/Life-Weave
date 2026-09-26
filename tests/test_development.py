"""The web development chain advances only from real persisted Run results."""
import subprocess
from psycopg.types.json import Jsonb

from test_live_database import dedicated_client, post


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
    finish(client, first['planRunId'], 'User behavior: useful feature. Impact: README. Steps: edit and verify. Risk: low. 自检: check output and tests.')
    service = client.app.state.development
    service.advance(first['id'])
    reviewing = service.get('personal', first['id'])
    assert reviewing['status'] == 'reviewing' and reviewing['reviewRunId']
    assert reviewing['planSha256']
    finish(client, reviewing['reviewRunId'], 'Reviewed request and plan.\nREVIEW_DECISION: PASS')
    service.advance(first['id'])
    implementing = service.get('personal', first['id'])
    assert implementing['status'] == 'implementing' and implementing['implementationRunId']
    finish(client, implementing['implementationRunId'], 'Changed README; test command passed.')
    service.advance(first['id'])
    done = service.get('personal', first['id'])
    assert done['status'] == 'awaiting_acceptance'
    assert len({done['planRunId'], done['reviewRunId'], done['implementationRunId']}) == 3
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
    finish(client, created['planRunId'], 'Plan a precise fix with checks. This is more than eighty characters so the planning gate can proceed. 自检 done.')
    service.advance(created['id'])
    reviewing = service.get('personal', created['id'])
    finish(client, reviewing['reviewRunId'], 'Missing regression check. REVIEW_DECISION: NEEDS_REVISION')
    service.advance(created['id'])
    blocked = service.get('personal', created['id'])
    assert blocked['status'] == 'blocked' and blocked['implementationRunId'] is None

"""Bound Codex events are idempotent and disclose only metadata plus observed Git state."""
import subprocess

from test_live_database import dedicated_client, post
from scripts import lifeweave_hook


def test_bound_hook_event_and_wrong_native_session(dedicated_client, tmp_path):
    client = dedicated_client
    repo = tmp_path / 'code'
    repo.mkdir()
    (repo / 'README.md').write_text('# Before\n')
    for args in [('init', '-q'), ('config', 'user.name', 'Test'),
                 ('config', 'user.email', 'test@example.local'), ('add', '.'),
                 ('commit', '-qm', 'base')]:
        subprocess.run(['git', *args], cwd=repo, check=True)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Hook fixture'})
    route = f'/items/{item["id"]}/external-development/sessions'
    start = post(client, route, {'requestId': 'hook-start', 'repositoryPath': str(repo),
                                 'summary': 'Fix README', 'nativeSessionId': 'native-session-123'})
    session = start['sessionId']
    assert start['event']['payload']['agentId'] == 'development'
    assert start['event']['payload']['methodId']
    assert any(entry['id'] == start['event']['payload']['methodId']
               for entry in start['event']['payload']['declaredInputs'])
    (repo / 'README.md').write_text('# After\n')
    body = {'eventId': 'PostToolUse:turn-1:tool-1', 'nativeSessionId': 'native-session-123',
            'kind': 'PostToolUse', 'turnId': 'turn-1', 'toolUseId': 'tool-1',
            'toolName': 'Bash', 'model': 'gpt-6-astra', 'inputHash': 'sha256:abc', 'exitCode': 0}
    event = post(client, route + f'/{session}/hook-events', body)
    assert event['payload']['source'] == 'codex_hook'
    assert event['payload']['observedGit']['changedPaths'] == ['README.md']
    assert event['payload']['model'] == 'gpt-6-astra'
    assert post(client, route + f'/{session}/hook-events', body)['id'] == event['id']
    response = client.post('/api/lifeweave/personal' + route + f'/{session}/hook-events',
                           json={**body, 'eventId': 'wrong', 'nativeSessionId': 'another-native-session'})
    assert response.status_code == 409
    assert 'tool_input' not in str(event) and '# After' not in str(event)


def test_hook_payload_hashes_input_and_never_sends_raw_command(tmp_path, monkeypatch):
    monkeypatch.setattr(lifeweave_hook, 'FOLDER', tmp_path / 'hooks')
    monkeypatch.setattr(lifeweave_hook, 'FILE', tmp_path / 'hooks/bindings.json')
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    lifeweave_hook.bind_session('native-session-123', base_url='http://127.0.0.1:8010',
                               workspace='personal', item_id='item-1', external_id='external-1',
                               repository=str(repo))
    event = {'session_id': 'native-session-123', 'cwd': str(repo),
             'hook_event_name': 'PostToolUse', 'turn_id': 'turn-1',
             'tool_use_id': 'tool-1', 'tool_name': 'Bash',
             'tool_input': {'command': 'export SECRET=should-never-be-sent'},
             'tool_response': {'exit_code': 0, 'output': 'private result'}, 'model': 'gpt-6-astra'}
    payload = lifeweave_hook.event_payload(event)
    assert payload['inputHash'].startswith('sha256:')
    assert 'SECRET' not in str(payload) and 'private result' not in str(payload)
    assert lifeweave_hook.FILE.stat().st_mode & 0o077 == 0

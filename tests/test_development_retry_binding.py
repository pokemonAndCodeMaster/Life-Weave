"""A failed managed assignment can retry its own declared stages."""
import subprocess

import pytest
from psycopg.types.json import Jsonb

from test_live_database import dedicated_client, post
from src.agent_runtime.tree_snapshot import tree_sha256


BASE = '/api/lifeweave/personal'
PLAN_RESULT = ('The change updates the fixture README. The plan covers the user result, '
               'one-file scope, implementation order, and a check of the final diff. '
               'Risk is limited to the fixture. 自检: verify the output and repository state.')


def _repository(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'README.md').write_text('# Before\n')
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', 'README.md'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c',
                    'user.email=test@example.local', 'commit', '-qm', 'fixture'], check=True)
    return root


def _checkout(client, tmp_path, source, run_id, *, change=False):
    client.app.state.development.project_root = tmp_path
    target = tmp_path / '.runtime/executions' / run_id / 'repo'
    target.parent.mkdir(parents=True)
    subprocess.run(['git', 'clone', '-q', str(source), str(target)], check=True)
    client.app.state.database_manager.postgres().execute(
        'UPDATE workbench.t_lifeweave_run SET environment_snapshot=%s WHERE id=%s',
        (Jsonb({'actualDirectory': str(target), 'readonlyTreeSha256': tree_sha256(target)}), run_id))
    if change:
        (target / 'README.md').write_text('# After\n')


def _finish(client, run_id, result):
    client.app.state.database_manager.postgres().execute(
        "UPDATE workbench.t_lifeweave_run SET state='succeeded',result=%s WHERE id=%s",
        (result, run_id))


def _start(client, item_id, root, request_id, *, scope='implement', review='independent',
           step_id=None, plan_version=None):
    body = {'requestId': request_id, 'itemId': item_id, 'instruction': 'Update the fixture README',
            'repositoryPath': str(root), 'engine': 'codex', 'reviewMode': review,
            'executionScope': scope, 'knowledgeRefs': []}
    if step_id is not None:
        body.update({'stepId': step_id, 'planVersion': plan_version})
    response = client.post(BASE + '/development', json=body)
    assert response.status_code == 202, response.text
    return response.json()


def _advance_success(client, tmp_path, root, assignment, *, scope='implement', review='independent'):
    service = client.app.state.development
    _checkout(client, tmp_path, root, assignment['planRunId'])
    _finish(client, assignment['planRunId'], PLAN_RESULT)
    service.advance(assignment['id'])
    current = service.get('personal', assignment['id'])
    if review == 'independent':
        assert current['status'] == 'reviewing'
        _checkout(client, tmp_path, root, current['reviewRunId'])
        _finish(client, current['reviewRunId'], 'Reviewed scope and verification.\nREVIEW_DECISION: PASS')
        service.advance(assignment['id'])
        current = service.get('personal', assignment['id'])
    if scope == 'implement':
        assert current['status'] == 'implementing'
        _checkout(client, tmp_path, root, current['implementationRunId'], change=True)
        _finish(client, current['implementationRunId'], 'README changed and the diff was checked.')
        service.advance(assignment['id'])
        current = service.get('personal', assignment['id'])
        assert current['status'] == 'awaiting_acceptance'
    else:
        assert current['status'] == 'plan_ready'
    return current


def _fail_first_plan(client, assignment):
    client.app.state.database_manager.postgres().execute(
        "UPDATE workbench.t_lifeweave_run SET state='failed',error='model unavailable' WHERE id=%s",
        (assignment['planRunId'],))
    client.app.state.development.advance(assignment['id'])
    assert client.app.state.development.get('personal', assignment['id'])['status'] == 'failed'


def test_failed_managed_plan_retries_each_stage_without_losing_failure(dedicated_client, tmp_path):
    client = dedicated_client
    root = _repository(tmp_path)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Retry one development assignment'})
    first = _start(client, item['id'], root, 'first')
    _fail_first_plan(client, first)
    before = client.get(f'{BASE}/items/{item["id"]}/work-view').json()['plan']
    assert [node['state'] for node in before['nodes']] == ['failed', 'planned', 'planned']

    retry = _start(client, item['id'], root, 'retry', step_id=before['nodes'][2]['id'],
                   plan_version=before['version'])
    binding = client.app.state.development._business_binding(
        {'workspace': 'personal', 'item_id': item['id'], 'id': retry['id']})
    assert binding['stageSteps'] == {stage: f'{first["id"]}:{stage}'
                                     for stage in ('plan', 'review', 'implementation')}
    complete = _advance_success(client, tmp_path, root, retry)
    view = client.get(f'{BASE}/items/{item["id"]}/work-view').json()['plan']
    assert [node['state'] for node in view['nodes']] == ['succeeded'] * 3
    assert [node['outputIds'] for node in view['nodes']] == [
        [f'run:{retry["planRunId"]}'], [f'run:{complete["reviewRunId"]}'],
        [f'delivery:{retry["id"]}']]
    assert [node['runId'] for node in view['nodes']] == [
        retry['planRunId'], complete['reviewRunId'], complete['implementationRunId']]
    assert any(attempt['runId'] == first['planRunId'] and attempt['outcome'] == 'failed'
               for attempt in view['nodes'][0]['attempts'])
    assert any(attempt['runId'] == retry['planRunId'] and attempt['outcome'] == 'succeeded'
               for attempt in view['nodes'][0]['attempts'])


@pytest.mark.parametrize(('scope', 'review', 'stage_names'), [
    ('plan_only', 'self', ['plan']),
    ('plan_only', 'independent', ['plan', 'review']),
    ('implement', 'self', ['plan', 'implementation']),
])
def test_managed_retry_preserves_scope_and_review_shape(dedicated_client, tmp_path, scope, review, stage_names):
    client = dedicated_client
    root = _repository(tmp_path)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Retry development stages'})
    first = _start(client, item['id'], root, 'first', scope=scope, review=review)
    _fail_first_plan(client, first)
    plan = client.get(f'{BASE}/items/{item["id"]}/work-view').json()['plan']
    selected = plan['nodes'][-1]['id']
    retry = _start(client, item['id'], root, 'retry', scope=scope, review=review,
                   step_id=selected, plan_version=plan['version'])
    binding = client.app.state.development._business_binding(
        {'workspace': 'personal', 'item_id': item['id'], 'id': retry['id']})
    assert binding['stageSteps']['plan'] == f'{first["id"]}:plan'
    assert binding['stageSteps']['review'] == f'{first["id"]}:{"review" if review == "independent" else "plan"}'
    assert binding['stageSteps']['implementation'] == f'{first["id"]}:{"implementation" if scope == "implement" else "plan"}'
    _advance_success(client, tmp_path, root, retry, scope=scope, review=review)
    nodes = client.get(f'{BASE}/items/{item["id"]}/work-view').json()['plan']['nodes']
    assert [node['id'] for node in nodes] == [f'{first["id"]}:{stage}' for stage in stage_names]
    assert [node['state'] for node in nodes] == ['succeeded'] * len(stage_names)


def test_declared_single_code_step_keeps_all_phases_on_that_step(dedicated_client, tmp_path):
    client = dedicated_client
    root = _repository(tmp_path)
    item = post(client, '/items', {'itemType': 'fix', 'title': 'User-authored code step'})
    response = client.put(f'{BASE}/items/{item["id"]}/work-plan', json={
        'version': item['version'], 'title': 'My code plan', 'provider': 'user',
        'nodes': [{'id': 'write-code', 'title': 'Change README', 'state': 'planned',
                   'dependsOn': [], 'expectedOutputs': [
                       {'id': 'code', 'title': 'Reviewed code', 'kind': 'code', 'required': True}],
                   'acceptance': 'Check the changed README and delivery'}]})
    assert response.status_code == 200, response.text
    plan = response.json()['plan']
    assignment = _start(client, item['id'], root, 'user-plan', step_id='write-code',
                        plan_version=plan['version'])
    binding = client.app.state.development._business_binding(
        {'workspace': 'personal', 'item_id': item['id'], 'id': assignment['id']})
    assert set(binding['stageSteps'].values()) == {'write-code'}
    _advance_success(client, tmp_path, root, assignment)
    nodes = client.get(f'{BASE}/items/{item["id"]}/work-view').json()['plan']['nodes']
    assert len(nodes) == 1 and nodes[0]['id'] == 'write-code'
    assert nodes[0]['state'] == 'succeeded'
    assert nodes[0]['outputIds'] == [f'delivery:{assignment["id"]}']

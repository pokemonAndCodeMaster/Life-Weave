"""Shared business steps remain correct across reports, retries and plan changes."""
from concurrent.futures import ThreadPoolExecutor
import subprocess

from test_live_database import dedicated_client, post


def git_repository(path):
    path.mkdir()
    subprocess.run(['git', '-C', str(path), 'init', '-q'], check=True)
    (path / 'README.md').write_text('# fixture\n')
    subprocess.run(['git', '-C', str(path), 'add', 'README.md'], check=True)
    subprocess.run(['git', '-C', str(path), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '-qm', 'baseline'], check=True)
    return path


def plan_step(identity):
    return {'id': identity, 'title': identity, 'state': 'planned', 'dependsOn': [],
            'expectedOutputs': [{'id': 'verified', 'title': '固定验证记录',
                                 'kind': 'validation', 'required': True}],
            'acceptance': '核对实际检查结果和来源版本'}


def report(client, item_id, step_id, session_id, plan_version, request_id,
           deliverables=None, summary='已完成真实检查'):
    return client.post(f'/api/lifeweave/personal/items/{item_id}/work-plan/steps/{step_id}/reports', json={
        'requestId': request_id, 'planVersion': plan_version, 'stepId': step_id,
        'sessionId': session_id, 'outcome': 'succeeded', 'summary': summary,
        'deliverables': deliverables or [],
        'checks': [{'label': '实际检查', 'result': 'passed', 'evidence': '测试输出已核对'}],
    })


def test_external_steps_require_fixed_matching_outputs_and_keep_attempts(dedicated_client, tmp_path):
    client = dedicated_client
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Shared workflow'})
    base = f'/api/lifeweave/personal/items/{item["id"]}'
    saved = client.put(base + '/work-plan', json={
        'version': item['version'], 'title': 'Checked work', 'provider': 'development',
        'nodes': [plan_step('verify-a'), plan_step('verify-b')],
    })
    assert saved.status_code == 200, saved.text
    version = saved.json()['plan']['version']
    # A plan edit cannot claim completion by attaching a same-item result;
    # the report path is the only owner of current progress.
    bypass = client.put(base + '/work-plan', json={
        'version': saved.json()['itemVersion'], 'title': 'Forged completion',
        'provider': 'development', 'nodes': [{**plan_step('verify-a'), 'state': 'succeeded'},
                                             plan_step('verify-b')],
    })
    assert bypass.status_code == 400
    project = git_repository(tmp_path / 'project')
    started = post(client, f'/items/{item["id"]}/external-development/sessions', {
        'requestId': 'external-start', 'repositoryPath': str(project), 'summary': '真实会话',
        'stepId': 'verify-a', 'planVersion': version,
    })
    session_id = started['sessionId']
    missing = report(client, item['id'], 'verify-a', session_id, version, 'missing')
    assert missing.status_code == 201, missing.text
    assert missing.json()['applied'] is False
    assert any('缺少必需产物' in issue for issue in missing.json()['issues'])
    assert report(client, item['id'], 'verify-a', session_id, version, 'missing').json()['id'] == missing.json()['id']
    view = client.get(base + '/work-view').json()
    assert view['plan']['nodes'][0]['state'] == 'planned'
    assert view['plan']['nodes'][0]['deliveryStatus'] == 'missing'

    result = post(client, f'/items/{item["id"]}/manual-results', {
        'title': '验证记录', 'content': '检查确实通过，保留输入和实际结果。',
        'verification': '核对数据库读回', 'environment': '独立测试数据库', 'resultKind': 'validation',
    })
    reference = {'expectationId': 'verified', 'outputId': f'artifact:{result["artifactId"]}',
                 'version': result['version']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(report, client, item['id'], 'verify-a', session_id, version, 'valid-a', [reference])
        second = pool.submit(report, client, item['id'], 'verify-b', session_id, version, 'valid-b', [reference])
        responses = [first.result(), second.result()]
    assert all(response.status_code == 201 for response in responses), [response.text for response in responses]
    assert all(response.json()['applied'] for response in responses)
    view = client.get(base + '/work-view').json()
    assert [node['state'] for node in view['plan']['nodes']] == ['succeeded', 'succeeded']
    assert all(node['deliveryStatus'] == 'complete' for node in view['plan']['nodes'])
    assert len(view['plan']['nodes'][0]['attempts']) == 2

    replacement = post(client, f'/items/{item["id"]}/manual-results', {
        'title': '复查后的验证记录', 'content': '第二版包含真实新检查。',
        'verification': '追加环境核验', 'environment': '独立测试数据库', 'resultKind': 'validation',
    })
    replacement_ref = {'expectationId': 'verified', 'outputId': f'artifact:{replacement["artifactId"]}',
                       'version': replacement['version']}
    assert report(client, item['id'], 'verify-a', session_id, version, 'valid-replacement', [replacement_ref]).json()['applied']
    # A later rejected report pointing at the old artifact must not become default.
    rejected = report(client, item['id'], 'verify-a', session_id, version, 'rejected-old',
                      [{**reference, 'expectationId': 'unknown-expectation'}])
    assert rejected.json()['applied'] is False
    view = client.get(base + '/work-view').json()
    assert view['plan']['nodes'][0]['outputIds'] == [replacement_ref['outputId'], reference['outputId']]
    assert len(view['plan']['nodes'][0]['attempts']) == 4

    revised = client.put(base + '/work-plan', json={
        'version': view['itemVersion'], 'title': 'Changed checks', 'provider': 'development',
        'revisionReason': '验收要求发生变化',
        'nodes': [{**plan_step('verify-a'), 'acceptance': '加入新环境检查'}, plan_step('verify-b')],
    })
    assert revised.status_code == 200, revised.text
    assert revised.json()['plan']['nodes'][0]['state'] == 'planned'
    stale = report(client, item['id'], 'verify-a', session_id, version, 'stale', [reference])
    assert stale.status_code == 201, stale.text
    assert stale.json()['applied'] is False
    assert any('计划版本已变更' in issue for issue in stale.json()['issues'])
    assert client.get(base + '/work-view').json()['plan']['nodes'][0]['state'] == 'planned'


def test_optional_expectation_still_needs_real_result_and_removed_step_keeps_report(dedicated_client, tmp_path):
    client = dedicated_client
    item = post(client, '/items', {'itemType': 'fix', 'title': 'Optional output case'})
    base = f'/api/lifeweave/personal/items/{item["id"]}'
    saved = client.put(base + '/work-plan', json={
        'version': item['version'], 'title': 'Optional result', 'provider': 'development',
        'nodes': [{**plan_step('review'), 'expectedOutputs': [
            {'id': 'optional', 'title': '可选固定记录', 'kind': 'validation', 'required': False}]}],
    })
    assert saved.status_code == 200, saved.text
    version = saved.json()['plan']['version']
    project = git_repository(tmp_path / 'project')
    started = post(client, f'/items/{item["id"]}/external-development/sessions', {
        'requestId': 'optional-start', 'repositoryPath': str(project), 'summary': '真实会话',
        'stepId': 'review', 'planVersion': version,
    })
    session_id = started['sessionId']
    empty = report(client, item['id'], 'review', session_id, version, 'optional-empty')
    assert empty.status_code == 201, empty.text
    assert empty.json()['applied'] is False
    assert any('至少需要一份' in issue for issue in empty.json()['issues'])
    updated = client.put(base + '/work-plan', json={
        'version': client.get(base + '/work-view').json()['itemVersion'],
        'title': 'Step removed', 'provider': 'development',
        'revisionReason': '该步骤不再适用', 'nodes': [],
    })
    assert updated.status_code == 200, updated.text
    late = report(client, item['id'], 'review', session_id, version, 'late-after-removal')
    assert late.status_code == 201, late.text
    assert late.json()['applied'] is False
    assert any('计划版本已变更' in issue for issue in late.json()['issues'])
    activities = client.get(base).json()['activity']
    assert any(row['id'] == late.json()['id'] for row in activities)


def test_work_binding_reuses_existing_item_and_creates_one_child(dedicated_client):
    client = dedicated_client
    parent = post(client, '/items', {'itemType': 'requirement', 'title': 'Parent target'})
    route = '/work-bindings/resolve'
    binding = {'requestId': 'child-request', 'decision': 'child', 'parentId': parent['id'],
               'title': 'Independent child', 'goal': 'Deliver separately', 'itemType': 'fix'}
    first = post(client, route, binding, 200)
    again = post(client, route, binding, 200)
    assert first == again
    assert first['action'] == 'created_child'
    child = client.get(f'/api/lifeweave/personal/items/{first["itemId"]}').json()
    assert child['payload']['parentId'] == parent['id']
    assert any(row['relationType'] == 'part_of' and row['toId'] == parent['id']
               for row in child['relations'])
    assert client.post('/api/lifeweave/personal' + route,
                       json={**binding, 'goal': 'Different goal'}).status_code == 409
    matched = post(client, route, {'requestId': 'auto-reuse', 'decision': 'auto',
                                   'title': 'Independent child'}, 200)
    assert matched['itemId'] == first['itemId']
    ambiguous = post(client, route, {'requestId': 'ambiguous', 'decision': 'auto',
                                     'title': 'target'}, 200)
    assert ambiguous['action'] == 'needs_choice'
    assert ambiguous['candidates']


def test_external_phase_report_uses_same_step_rule_and_retry_receipt(dedicated_client, tmp_path):
    client = dedicated_client
    item = post(client, '/items', {'itemType': 'fix', 'title': 'External report binding'})
    base = f'/api/lifeweave/personal/items/{item["id"]}'
    planned = client.put(base + '/work-plan', json={
        'version': item['version'], 'title': '验证计划', 'provider': 'development',
        'nodes': [plan_step('verified')],
    }).json()
    version = planned['plan']['version']
    started = post(client, f'/items/{item["id"]}/external-development/sessions', {
        'requestId': 'phase-start', 'repositoryPath': str(git_repository(tmp_path / 'project')),
        'summary': '外部会话', 'stepId': 'verified', 'planVersion': version,
    })
    result = post(client, f'/items/{item["id"]}/manual-results', {
        'title': '核验结果', 'content': '实际检查并记录结果。',
        'verification': '检查通过', 'environment': '独立测试数据库', 'resultKind': 'validation',
    })
    route = f'/items/{item["id"]}/external-development/sessions/{started["sessionId"]}/events'
    body = {'requestId': 'phase-verified', 'phase': 'verification', 'summary': '已核对实际结果',
            'checks': ['独立测试数据库通过'], 'stepId': 'verified', 'planVersion': version,
            'outcome': 'succeeded', 'deliverables': [
                {'expectationId': 'verified', 'outputId': f'artifact:{result["artifactId"]}',
                 'version': result['version']}],
            }
    first = post(client, route, body)
    assert first['stepReport']['applied'] is True
    assert first['stepReport']['sessionId'] == started['sessionId']
    assert client.get(base + '/work-view').json()['plan']['nodes'][0]['state'] == 'succeeded'
    retried = post(client, route, body)
    assert retried['stepReport']['id'] == first['stepReport']['id']
    assert client.post('/api/lifeweave/personal' + route,
                       json={**body, 'summary': '另一份报告'}).status_code == 409

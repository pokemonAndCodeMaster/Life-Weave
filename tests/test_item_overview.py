"""Overview edits and projection through the real HTTP API."""
import subprocess
import pytest
from psycopg.types.json import Jsonb

from tests.test_live_database import database_client
from src.lifeweave.item_overview import ItemOverviewService
from src.agent_runtime.tree_snapshot import tree_sha256


@pytest.fixture
def client(tmp_path_factory):
    yield from database_client(tmp_path_factory)


def test_overview_is_sourced_editable_and_versioned(client):
    base = '/api/lifeweave/personal'
    item = client.post(base + '/items', json={'itemType': 'research', 'title': '研读论文',
                       'payload': {'goal': '理解方法', 'scope': 'GSSM 方法范围'}}).json()
    view = client.get(base + f'/items/{item["id"]}/work-view').json()
    assert view['overview']['intent'] == '理解方法'
    assert view['overview']['background'] == 'GSSM 方法范围'
    assert view['overview']['progress']['completedSteps'] == 0
    assert view['overview']['outputIds'] == []
    edited = client.put(base + f'/items/{item["id"]}/overview', json={
        'version': view['itemVersion'], 'background': '两篇论文需要比较',
        'intent': '比较两篇论文的实际方法', 'expectedResult': '形成可读结论'})
    assert edited.status_code == 200, edited.text
    assert edited.json()['overview']['intent'] == '比较两篇论文的实际方法'
    assert edited.json()['overview']['sources']['intent'] == 'item.overview'
    assert client.get(base + f'/items/{item["id"]}').json()['payload']['goal'] == '比较两篇论文的实际方法'
    context = client.app.state.lifeweave_service.current_context_snapshot('personal', item['id'])
    assert context['content']['goal'] == '比较两篇论文的实际方法'
    assert context['localIntent']['source'] == 'item.overview'
    assert client.app.state.lifeweave_service.repository.context('personal', item['id'])['content']['goal'] == '理解方法'
    assert client.put(base + f'/items/{item["id"]}/overview', json={
        'version': view['itemVersion'], 'background': '', 'intent': '', 'expectedResult': ''}).status_code == 409


def test_overview_uses_current_report_and_next_step_instead_of_plan_counts():
    item = {'id': 'one', 'workspace': 'personal', 'status': 'awaiting_acceptance',
            'payload': {'overview': {'background': '背景', 'intent': '目标', 'expectedResult': '结果'}},
            'context': {'content': {'goal': '旧目标'}}}
    view = {'plan': {'version': 2, 'nodes': [
        {'id': 'implementation', 'title': '实施', 'state': 'succeeded', 'summary': '旧记录',
         'outputIds': ['run:old', 'run:new'], 'attempts': [
             {'planVersion': 1, 'applied': True, 'outcome': 'succeeded',
              'summary': '旧版报告', 'createdAt': '2026-09-27T00:00:00Z', 'outputIds': ['run:old']},
             {'planVersion': 2, 'applied': True, 'outcome': 'succeeded',
              'summary': '测试通过并固定交付', 'createdAt': '2026-09-28T00:00:00Z', 'outputIds': ['run:new']} ]},
        {'id': 'acceptance', 'title': '用户验收', 'state': 'planned', 'summary': '',
         'outputIds': [], 'attempts': []}]},
        'current': {'state': 'awaiting_acceptance', 'summary': '业务计划含 2 个步骤'},
        'outputs': [{'id': 'run:old', 'kind': 'development', 'title': '旧版', 'createdAt': '2026-09-27T00:00:00Z'},
                    {'id': 'run:new', 'kind': 'development', 'title': '新版', 'createdAt': '2026-09-28T00:00:00Z'}]}
    overview = ItemOverviewService(None).project(item, view)
    assert overview['progress']['summary'] == '实施：测试通过并固定交付；下一步：用户验收'
    assert overview['progress']['completedSteps'] == 1
    assert overview['outputIds'] == ['run:new']
    view['plan']['nodes'][0]['attempts'] = []
    view['plan']['nodes'][0]['state'] = 'planned'
    view['plan']['nodes'][0]['summary'] = ''
    view['plan']['nodes'][0]['outputIds'] = []
    no_fact = ItemOverviewService(None).project(item, view)
    assert no_fact['progress']['summary'] == '尚未开始；下一步：实施'
    assert '业务计划含' not in no_fact['progress']['summary']
    view['plan']['nodes'] = [{'id': str(index), 'title': f'步骤 {index}', 'state': 'succeeded',
                              'summary': '已完成', 'outputIds': [f'run:{index}'], 'attempts': []}
                             for index in range(7)]
    view['outputs'] = [{'id': f'run:{index}', 'kind': 'development', 'title': f'成果 {index}',
                        'createdAt': f'2026-09-28T00:00:{index:02d}Z'} for index in range(7)]
    assert ItemOverviewService(None).project(item, view)['outputIds'] == [f'run:{index}' for index in range(7)]


def test_development_stops_after_intent_edit_but_ignores_step_progress(client, tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'README.md').write_text('# Fixture\n')
    for args in [('init', '-q'), ('config', 'user.name', 'Test'),
                 ('config', 'user.email', 'test@example.local'), ('add', '.'),
                 ('commit', '-qm', 'fixture')]:
        subprocess.run(['git', *args], cwd=project, check=True)
    client.app.state.development.project_root = tmp_path
    base = '/api/lifeweave/personal'

    def complete_plan(run_id):
        checkout = tmp_path / '.runtime/executions' / run_id / 'repo'
        checkout.parent.mkdir(parents=True)
        subprocess.run(['git', 'clone', '-q', str(project), str(checkout)], check=True)
        client.app.state.database_manager.postgres().execute(
            "UPDATE workbench.t_lifeweave_run SET state='succeeded',result=%s,environment_snapshot=%s WHERE id=%s",
            ('User behavior: useful result. Impact: README. Steps: edit and verify. Risk: low. 自检: checked output and tests.',
             Jsonb({'actualDirectory': str(checkout), 'readonlyTreeSha256': tree_sha256(checkout)}), run_id))

    for case, edit_intent, child_item in (('root-intent', True, False),
                                          ('progress', False, False),
                                          ('child-intent', True, True)):
        parent = (client.post(base + '/items', json={'itemType': 'requirement',
                  'title': '共同父背景', 'payload': {'goal': '父级正式目标'}}).json() if child_item else None)
        item = client.post(base + '/items', json={'itemType': 'requirement',
                           'title': {'root-intent': '目标变更保护', 'progress': '步骤更新不中断',
                                     'child-intent': '子目标变更保护'}[case],
                           'payload': {'goal': '先形成可审方案',
                                       **({'parentId': parent['id']} if parent else {})}}).json()
        method = client.get(base + f'/items/{item["id"]}/development/choices').json()['methodId']
        created_response = client.post(base + '/development', json={
            'requestId': case, 'itemId': item['id'],
            'instruction': '形成方案后审阅', 'repositoryPath': str(project), 'agentId': 'development',
            'engine': 'codex', 'methodId': method, 'knowledgeRefs': [],
            'reviewMode': 'independent', 'executionScope': 'implement'})
        assert created_response.status_code == 202, created_response.text
        created = created_response.json()
        view = client.get(base + f'/items/{item["id"]}/work-view').json()
        if edit_intent:
            old_snapshot = client.app.state.lifeweave_service.current_context_snapshot('personal', item['id'])
            edited = client.put(base + f'/items/{item["id"]}/overview', json={
                'version': view['itemVersion'], 'background': '原背景',
                'intent': '改为另一个交付目标', 'expectedResult': '新的结果'})
            assert edited.status_code == 200, edited.text
            if child_item:
                new_snapshot = client.app.state.lifeweave_service.current_context_snapshot('personal', item['id'])
                assert new_snapshot['content']['goal'] == old_snapshot['content']['goal'] == '父级正式目标'
                assert new_snapshot['focus']['goal'] == '改为另一个交付目标'
        else:
            step = view['plan']['nodes'][0]
            report = client.post(base + f'/items/{item["id"]}/work-plan/steps/{step["id"]}/reports', json={
                'requestId': 'progress-only', 'planVersion': view['plan']['version'],
                'stepId': step['id'], 'outcome': 'running', 'summary': '方案编写进展已记录',
                'runId': created['planRunId'], 'assignmentId': created['id']})
            assert report.status_code == 201, report.text
            assert report.json()['applied'] is True
        complete_plan(created['planRunId'])
        client.app.state.development.advance(created['id'])
        result = client.app.state.development.get('personal', created['id'])
        if edit_intent:
            assert result['status'] == 'blocked'
            assert '目标或背景已更新' in result['error']
            assert result['reviewRunId'] is None
        else:
            assert result['status'] == 'reviewing'
            assert result['reviewRunId']

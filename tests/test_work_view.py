"""The work graph reports persisted plans and observed facts without inventing progress."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.lifeweave.repository import ConcurrentUpdateError
from src.lifeweave.work_view import WorkViewService
from src.lifeweave.work_view_models import MAX_WORK_STEPS, WorkPlanInput
from test_live_database import dedicated_client, post


def step(index: int, dependencies: list[str] | None = None, **extra):
    return {'id': f's{index}', 'title': f'步骤 {index}', 'description': '',
            'state': 'planned', 'summary': '', 'dependsOn': dependencies or [],
            'outputIds': [], **extra}


def plan(nodes, version=1):
    return WorkPlanInput.model_validate({'version': version, 'title': '工作计划',
                                         'provider': 'manual', 'nodes': nodes})


class FakeWork:
    def __init__(self):
        self.items = {('personal', 'main'): {'id': 'main', 'version': 1, 'status': 'open',
                                             'payload': {'keep': {'nested': 'untouched'}}}}
        self.activities = []
        self.repository = SimpleNamespace(list_relations=lambda *_: [], get_entity=lambda *_: None)

    def get_item(self, workspace, item_id):
        if (workspace, item_id) not in self.items:
            raise KeyError(item_id)
        return deepcopy(self.items[workspace, item_id])

    def update_item(self, workspace, item_id, *, version, actor_id, payload):
        item = self.items[workspace, item_id]
        if item['version'] != version:
            raise ConcurrentUpdateError('conflict')
        item['payload'] = deepcopy(payload)
        item['version'] += 1
        return deepcopy(item)

    def append_activity(self, workspace, item_id, **values):
        self.activities.append((workspace, item_id, values))


class FakeRuntime:
    def __init__(self):
        self.runs = {}

    def get_run(self, workspace, run_id):
        row = self.runs.get((workspace, run_id))
        if row is None:
            raise KeyError(run_id)
        return deepcopy(row)

    def list_runs(self, workspace, *, item_id, limit, offset):
        rows = [row for (space, _), row in self.runs.items()
                if space == workspace and row['item_id'] == item_id]
        rows.sort(key=lambda row: row['id'], reverse=True)
        return deepcopy(rows[offset:offset + limit]), len(rows)


class FakeDevelopment:
    def __init__(self):
        self.assignments = {}
        self.deliveries = {}

    def get(self, workspace, identity):
        if (workspace, identity) not in self.assignments:
            raise KeyError(identity)
        return deepcopy(self.assignments[workspace, identity])

    def list(self, workspace, item_id):
        return [deepcopy(row) for (space, _), row in self.assignments.items()
                if space == workspace and row['itemId'] == item_id]

    def delivery(self, workspace, identity):
        return deepcopy(self.deliveries.get((workspace, identity)))


def fixture():
    work, runtime, development = FakeWork(), FakeRuntime(), FakeDevelopment()
    return WorkViewService(work, runtime, development), work, runtime, development


def test_maximum_legal_graph_persists_and_preserves_other_payload():
    service, work, _, _ = fixture()
    nodes = [step(index, [f's{earlier}' for earlier in range(index)])
             for index in range(MAX_WORK_STEPS)]
    saved = service.save('personal', 'main', plan(nodes), 'tester')
    assert len(saved['plan']['nodes']) == MAX_WORK_STEPS
    assert len(saved['plan']['nodes'][-1]['dependsOn']) == MAX_WORK_STEPS - 1
    assert saved['plan']['source'] == 'declared'
    assert saved['current']['label'] == '步骤 0'
    assert saved['itemVersion'] == 2
    assert work.items['personal', 'main']['payload']['keep'] == {'nested': 'untouched'}
    assert work.activities[0][2]['payload']['planVersion'] == 1
    assert len(work.activities[0][2]['payload']['plan']['nodes']) == MAX_WORK_STEPS
    updated = service.save('personal', 'main', plan([step(0)], version=2), 'tester')
    assert updated['plan']['version'] == 2
    assert len(work.activities[0][2]['payload']['plan']['nodes']) == MAX_WORK_STEPS
    with pytest.raises(ConcurrentUpdateError):
        service.save('personal', 'main', plan(nodes), 'tester')


@pytest.mark.parametrize('nodes, message', [
    ([step(0), step(0)], '重复'),
    ([step(0, ['s0'])], '自身'),
    ([step(0, ['missing'])], '不存在'),
    ([step(0), step(1, ['s0', 's0'])], '重复'),
    ([step(0, ['s1']), step(1, ['s0'])], '环路'),
])
def test_invalid_dependencies_rejected_at_request_boundary(nodes, message):
    with pytest.raises(ValidationError, match=message):
        plan(nodes)


def test_over_limit_graph_and_dependencies_rejected():
    with pytest.raises(ValidationError, match='80'):
        plan([step(index) for index in range(MAX_WORK_STEPS + 1)])
    with pytest.raises(ValidationError, match='79'):
        plan([step(0, [f'x{index}' for index in range(MAX_WORK_STEPS)])])


def test_foreign_run_and_assignment_cannot_be_saved():
    service, _, runtime, development = fixture()
    runtime.runs['personal', 'other-run'] = {'id': 'other-run', 'item_id': 'other',
                                             'state': 'succeeded', 'result': 'secret'}
    development.assignments['personal', 'dev-other'] = {'id': 'dev-other', 'itemId': 'other',
                                                         'status': 'accepted'}
    with pytest.raises(ValueError, match='不属于当前事项'):
        service.save('personal', 'main', plan([step(0, runId='other-run')]), 'tester')
    with pytest.raises(ValueError, match='不属于当前事项'):
        service.save('personal', 'main', plan([step(0, assignmentId='dev-other')]), 'tester')
    assert service.read('personal', 'main')['plan']['source'] == 'empty'
    work = service.work
    work.items['team', 'main'] = {'id': 'main', 'version': 1, 'status': 'open', 'payload': {}}
    runtime.runs['personal', 'owned-personal'] = {'id': 'owned-personal', 'item_id': 'main',
                                                  'state': 'succeeded', 'result': 'result'}
    development.assignments['personal', 'owned-dev'] = {'id': 'owned-dev', 'itemId': 'main',
                                                        'status': 'accepted'}
    with pytest.raises(KeyError):
        service.save('team', 'main', plan([step(0, runId='owned-personal')]), 'tester')
    with pytest.raises(KeyError):
        service.save('team', 'main', plan([step(0, assignmentId='owned-dev')]), 'tester')


def test_manual_artifacts_can_be_bound_and_all_remain_in_catalog():
    service, work, _, _ = fixture()
    entities = {
        'artifact-old': {'id': 'artifact-old', 'entityType': 'artifact', 'title': 'First',
                         'payload': {'body': 'First result'}, 'version': 1, 'updatedAt': '2026-01-01'},
        'artifact-new': {'id': 'artifact-new', 'entityType': 'artifact', 'title': 'Second',
                         'payload': {'body': 'Second result'}, 'version': 2, 'updatedAt': '2026-02-01'},
    }
    work.repository.list_relations = lambda *_: [
        {'fromKind': 'item', 'fromId': 'main', 'toKind': 'entity',
         'toId': identity, 'relationType': 'produces'} for identity in entities]
    work.repository.get_entity = lambda _workspace, identity: entities[identity]
    view = service.save('personal', 'main', plan([
        step(0, outputIds=['artifact:artifact-old'])]), 'tester')
    assert [output['artifactId'] for output in view['outputs']] == ['artifact-new', 'artifact-old']
    assert view['plan']['nodes'][0]['outputIds'] == ['artifact:artifact-old']
    with pytest.raises(ValueError, match='成果引用'):
        service.save('personal', 'main', plan([step(0, outputIds=['artifact:foreign'])], version=2), 'tester')


@pytest.mark.parametrize('uri', ['javascript:alert(1)', 'http://user:pass@example.com/x',
                                  'https://example.com/\nmalicious', '//elsewhere/x', '/api/../secret'])
def test_unsafe_context_links_rejected(uri):
    service, _, _, _ = fixture()
    with pytest.raises(ValueError, match='安全'):
        service.save('personal', 'main', plan([step(0, contextRefs=[{'title': 'bad', 'uri': uri}])]), 'tester')


def test_development_stages_use_real_runs_and_delivery_is_first_output():
    service, _, runtime, development = fixture()
    service.work.items['personal', 'main']['updatedAt'] = '2026-09-19T09:00:00+00:00'
    assignment = {'id': 'dev-main', 'itemId': 'main', 'status': 'awaiting_acceptance',
                  'updatedAt': '2026-09-27T09:00:00+00:00',
                  'executionScope': 'implement', 'reviewMode': 'independent',
                  'planRunId': 'run-plan', 'reviewRunId': 'run-review',
                  'implementationRunId': 'run-implementation', 'plan': 'plan',
                  'reviewDecision': 'pass', 'error': None}
    development.assignments['personal', 'dev-main'] = assignment
    for identity in ('run-plan', 'run-review', 'run-implementation'):
        runtime.runs['personal', identity] = {'id': identity, 'item_id': 'main',
                                              'state': 'succeeded', 'result': identity + ' ' * 5000}
    development.deliveries['personal', 'dev-main'] = {'id': 'delivery-main',
        'implementationRunId': 'run-implementation', 'artifactSha256': 'abc', 'decision': None}
    view = service.read('personal', 'main')
    assert [node['state'] for node in view['plan']['nodes']] == [
        'succeeded', 'succeeded', 'succeeded', 'waiting']
    assert view['outputs'][0]['id'] == 'delivery:dev-main'
    assert view['outputs'][0]['artifactId'] is None
    assert view['outputs'][1]['id'] == 'run:run-implementation'
    assert all(len(row['summary']) <= 240 for row in view['outputs'])
    assert view['current']['state'] == 'open'  # A successful Run does not accept the item.
    assert view['current']['label'] == '交付待验收'
    assert view['current']['updatedAt'] == '2026-09-27T09:00:00+00:00'


def test_latest_research_result_kept_when_newer_run_failed():
    service, _, runtime, _ = fixture()
    runtime.runs['personal', 'run-a'] = {'id': 'run-a', 'item_id': 'main',
                                        'state': 'succeeded', 'result': 'Complete report'}
    runtime.runs['personal', 'run-z'] = {'id': 'run-z', 'item_id': 'main',
                                        'state': 'failed', 'result': '', 'error': 'network failed'}
    view = service.read('personal', 'main')
    assert view['plan']['nodes'][0]['state'] == 'failed'
    assert view['outputs'][0]['runId'] == 'run-a'
    assert view['outputs'][0]['kind'] == 'research'
    assert view['plan']['nodes'][0]['outputIds'] == []
    assert view['current']['label'] == '运行失败'
    assert '较早的完整成果' in view['current']['summary']
    linked = service.save('personal', 'main', plan([step(0, outputIds=['run:run-a'])]), 'tester')
    assert linked['plan']['nodes'][0]['outputIds'] == ['run:run-a']
    runtime.runs['personal', 'run-zz'] = {'id': 'run-zz', 'item_id': 'main',
                                         'state': 'succeeded', 'result': 'New complete report'}
    retained = service.read('personal', 'main')
    assert retained['outputs'][0]['runId'] == 'run-zz'
    assert {output['id'] for output in retained['outputs']} == {'run:run-zz', 'run:run-a'}
    assert retained['plan']['nodes'][0]['outputIds'] == ['run:run-a']


def test_observed_development_saved_as_plan_keeps_stage_states():
    service, _, runtime, development = fixture()
    assignment = {'id': 'dev-main', 'itemId': 'main', 'status': 'planning',
                  'executionScope': 'implement', 'reviewMode': 'independent',
                  'planRunId': 'run-plan', 'reviewRunId': None, 'implementationRunId': None,
                  'plan': None, 'review': None, 'error': None}
    development.assignments['personal', 'dev-main'] = assignment
    runtime.runs['personal', 'run-plan'] = {'id': 'run-plan', 'item_id': 'main',
                                           'state': 'running', 'result': ''}
    observed = service.read('personal', 'main')
    assert [node['state'] for node in observed['plan']['nodes']] == [
        'running', 'planned', 'planned', 'planned']
    saved = service.save('personal', 'main', plan(observed['plan']['nodes']), 'tester')
    assert saved['plan']['source'] == 'declared'
    assert [node['state'] for node in saved['plan']['nodes']] == [
        'running', 'planned', 'planned', 'planned']
    assignment.update({'status': 'reviewing', 'planRunId': 'run-plan', 'reviewRunId': 'run-review'})
    runtime.runs['personal', 'run-plan'] = {'id': 'run-plan', 'item_id': 'main',
                                           'state': 'succeeded', 'result': 'Plan result'}
    runtime.runs['personal', 'run-review'] = {'id': 'run-review', 'item_id': 'main',
                                             'state': 'running', 'result': ''}
    progressing = service.read('personal', 'main')
    assert [node['state'] for node in progressing['plan']['nodes']] == [
        'succeeded', 'running', 'planned', 'planned']
    assert progressing['plan']['nodes'][0]['runId'] == 'run-plan'
    assert progressing['plan']['nodes'][0]['outputIds'] == ['run:run-plan']


def test_saved_observed_implementation_keeps_delivery_failure_state():
    service, _, runtime, development = fixture()
    development.assignments['personal', 'dev-main'] = {
        'id': 'dev-main', 'itemId': 'main', 'status': 'delivery_failed',
        'executionScope': 'implement', 'reviewMode': 'independent',
        'planRunId': 'run-plan', 'reviewRunId': 'run-review',
        'implementationRunId': 'run-implementation', 'plan': 'plan',
        'review': 'review', 'error': '交付包未生成'}
    for identity in ('run-plan', 'run-review', 'run-implementation'):
        runtime.runs['personal', identity] = {
            'id': identity, 'item_id': 'main', 'state': 'succeeded',
            'result': f'{identity} result'}

    observed = service.read('personal', 'main')
    assert observed['plan']['nodes'][2]['state'] == 'failed'
    saved = service.save('personal', 'main', plan(observed['plan']['nodes']), 'tester')
    assert saved['plan']['source'] == 'declared'
    assert saved['plan']['nodes'][2]['state'] == 'failed'
    assert saved['plan']['nodes'][2]['runId'] == 'run-implementation'


def test_new_plan_only_assignment_does_not_hide_older_code_delivery():
    service, _, _, development = fixture()
    development.assignments['personal', 'dev-new'] = {
        'id': 'dev-new', 'itemId': 'main', 'status': 'planning',
        'executionScope': 'plan_only', 'planRunId': None, 'reviewRunId': None,
        'implementationRunId': None, 'reviewMode': 'self', 'review': None}
    development.assignments['personal', 'dev-old'] = {
        'id': 'dev-old', 'itemId': 'main', 'status': 'accepted',
        'executionScope': 'implement', 'planRunId': None, 'reviewRunId': None,
        'implementationRunId': None, 'reviewMode': 'self', 'review': 'checked'}
    development.deliveries['personal', 'dev-old'] = {
        'id': 'delivery-old', 'implementationRunId': 'old-run',
        'artifactSha256': 'abc', 'decision': 'accepted'}
    view = service.read('personal', 'main')
    assert view['plan']['nodes'][0]['assignmentId'] == 'dev-new'
    assert view['outputs'][0]['id'] == 'delivery:dev-old'


def test_declared_node_retains_older_delivery_after_new_delivery_arrives():
    service, _, _, development = fixture()
    old = {'id': 'dev-old', 'itemId': 'main', 'status': 'accepted',
           'executionScope': 'implement', 'planRunId': None, 'reviewRunId': None,
           'implementationRunId': None, 'reviewMode': 'self', 'review': None}
    development.assignments['personal', 'dev-old'] = old
    development.deliveries['personal', 'dev-old'] = {
        'id': 'delivery-old', 'implementationRunId': 'run-old',
        'artifactSha256': 'old-hash', 'decision': 'accepted'}
    service.save('personal', 'main', plan([step(0, outputIds=['delivery:dev-old'])]), 'tester')
    new = {**old, 'id': 'dev-new'}
    development.assignments = {('personal', 'dev-new'): new, ('personal', 'dev-old'): old}
    development.deliveries['personal', 'dev-new'] = {
        'id': 'delivery-new', 'implementationRunId': 'run-new',
        'artifactSha256': 'new-hash', 'decision': None}
    view = service.read('personal', 'main')
    assert [output['id'] for output in view['outputs']] == [
        'delivery:dev-new', 'delivery:dev-old']
    assert view['plan']['nodes'][0]['outputIds'] == ['delivery:dev-old']


def test_http_persistence_and_workspace_isolation(dedicated_client):
    client = dedicated_client
    item = post(client, '/items', {'itemType': 'research', 'title': 'Graph',
                                   'payload': {'keep': 'sentinel'}})
    item_id = item['id']
    base = f'/api/lifeweave/personal/items/{item_id}'
    empty = client.get(base + '/work-view')
    assert empty.status_code == 200, empty.text
    assert empty.json()['plan']['source'] == 'empty'
    saved = client.put(base + '/work-plan', json={'version': item['version'],
        'title': 'Two paths', 'provider': 'manual',
        'nodes': [step(0), step(1), step(2, ['s0', 's1'])]})
    assert saved.status_code == 200, saved.text
    assert saved.json()['plan']['nodes'][2]['dependsOn'] == ['s0', 's1']
    assert client.get(base).json()['payload']['keep'] == 'sentinel'
    assert any(entry['kind'] == 'work_plan_updated' for entry in client.get(base).json()['activity'])
    assert client.put(base + '/work-plan', json={'version': item['version'],
        'title': 'stale', 'provider': 'manual', 'nodes': []}).status_code == 409
    dense = [step(index, [f's{earlier}' for earlier in range(index)])
             for index in range(MAX_WORK_STEPS)]
    full = client.put(base + '/work-plan', json={'version': saved.json()['itemVersion'],
        'title': 'Maximum graph', 'provider': 'manual', 'nodes': dense})
    assert full.status_code == 200, full.text
    assert len(full.json()['plan']['nodes']) == MAX_WORK_STEPS
    too_many = client.put(base + '/work-plan', json={'version': full.json()['itemVersion'],
        'title': 'Too many', 'provider': 'manual', 'nodes': dense + [step(MAX_WORK_STEPS)]})
    assert too_many.status_code == 422
    foreign = post(client, '/items', {'itemType': 'research', 'title': 'Other'})
    run = client.post('/api/lifeweave/personal/runs', json={
        'itemId': foreign['id'], 'instruction': 'Check the ownership boundary', 'engine': 'codex'})
    assert run.status_code == 202, run.text
    cross_item = client.put(base + '/work-plan', json={'version': full.json()['itemVersion'],
        'title': 'Foreign run', 'provider': 'manual',
        'nodes': [step(0, runId=run.json()['id'])]})
    assert cross_item.status_code == 400
    assert client.get(base + '/work-view').json()['itemVersion'] == full.json()['itemVersion']
    work = client.app.state.lifeweave_service
    with pytest.MonkeyPatch.context() as patch:
        def fail_activity(*_args, **_kwargs):
            raise RuntimeError('activity unavailable')
        patch.setattr(work, 'append_activity', fail_activity)
        with pytest.raises(RuntimeError, match='activity unavailable'):
            WorkViewService(work, client.app.state.lifeweave_runtime_service,
                            client.app.state.development).save(
                'personal', item_id, plan([step(0)], version=full.json()['itemVersion']), 'tester')
    assert client.get(base + '/work-view').json()['itemVersion'] == full.json()['itemVersion']
    team = client.post('/api/lifeweave/team/items', json={'itemType': 'research', 'title': 'Team item'})
    assert team.status_code == 201, team.text
    cross_space = client.put(f'/api/lifeweave/team/items/{team.json()["id"]}/work-plan', json={
        'version': team.json()['version'], 'title': 'Foreign space', 'provider': 'manual',
        'nodes': [step(0, runId=run.json()['id'])]})
    assert cross_space.status_code == 404
    assert client.get(f'/api/lifeweave/team/items/{item_id}/work-view').status_code == 404

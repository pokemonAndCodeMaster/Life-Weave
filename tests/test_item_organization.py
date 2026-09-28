"""Real organization API and persistence, always in a disposable database."""
from uuid import uuid4

import pytest

from tests.test_live_database import database_client


@pytest.fixture
def client(tmp_path_factory):
    yield from database_client(tmp_path_factory)


BASE = '/api/lifeweave/personal'


def post(client, path, body, expected=200):
    response = client.post(BASE + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def create_item(client, title, payload=None):
    return post(client, '/items', {'itemType': 'research', 'title': title,
                                  'payload': {'goal': title, **(payload or {})}}, 201)


def create_entity(client, kind, title):
    return post(client, '/entities', {'entityType': kind, 'title': title}, 201)


def test_create_inheritance_explicit_priority_and_rules(client):
    topic = create_entity(client, 'topic', '论文专题')
    domain = create_entity(client, 'domain', '研究领域')
    alternate = create_entity(client, 'topic', '另一个专题')
    rules = client.put(BASE + '/item-organization/rules', json={'rules': [{
        'id': 'paper', 'title': '明确论文词', 'terms': ['论文'], 'topicIds': [topic['id']],
        'domainIds': [domain['id']], 'enabled': True}]})
    assert rules.status_code == 200, rules.text
    root = create_item(client, '论文 A')
    child = create_item(client, '子项 B', {'parentId': root['id']})
    binding = post(client, '/work-bindings/resolve', {'requestId': 'child-binding', 'decision': 'child',
        'parentId': root['id'], 'title': '子项 C', 'goal': '继续论文研究'})
    manual = create_item(client, '论文 C', {'topicIds': [alternate['id']]})
    rows = {row['id']: row for row in client.get(BASE + '/item-organization/catalog').json()['items']}
    assert rows[root['id']]['topicIds'] == [topic['id']]
    assert rows[child['id']]['domainIds'] == [domain['id']]
    assert rows[child['id']]['parentId'] == root['id']
    assert rows[binding['itemId']]['parentId'] == root['id']
    assert rows[binding['itemId']]['topicIds'] == [topic['id']]
    assert rows[manual['id']]['topicIds'] == [alternate['id']]
    assert rows[manual['id']]['domainIds'] == []
    assert client.get('/api/lifeweave/team/item-organization/catalog').json()['items'] == []
    bad = client.post(BASE + '/items', json={'itemType': 'research', 'title': '跨空间',
                                            'payload': {'parentId': 'missing'}})
    assert bad.status_code == 400


def test_proposal_group_apply_undo_preserves_work_and_rejects_stale_relation(client):
    topic = create_entity(client, 'topic', '研究专题')
    domain = create_entity(client, 'domain', '研究')
    first = create_item(client, '论文甲', {'note': '不可覆盖的原文'})
    second = create_item(client, '论文乙')
    body = {'requestId': uuid4().hex, 'reason': '两篇论文共同研读',
            'changes': [{'itemId': row['id'], 'itemVersion': row['version'],
                         'topicIds': [topic['id']], 'domainIds': [domain['id']],
                         'reason': 'Agent 阅读目标后给出的明确判断'} for row in (first, second)],
            'groups': [{'key': 'papers', 'title': '论文共同目标', 'goal': '汇总两篇论文',
                        'itemIds': [first['id'], second['id']]}]}
    proposal = post(client, '/item-organization/proposals', body)
    assert proposal['status'] == 'proposed'
    assert len(proposal['changes']) == 2
    assert proposal['groups'][0]['topicIds'] == [topic['id']]
    assert post(client, '/item-organization/proposals', body)['id'] == proposal['id']
    before = client.get(BASE + '/item-organization/catalog').json()
    assert next(row for row in before['items'] if row['id'] == first['id'])['topicIds'] == []
    applied = post(client, f'/item-organization/proposals/{proposal["id"]}/apply', {'requestId': 'apply-1'})
    assert applied['status'] == 'applied'
    assert post(client, f'/item-organization/proposals/{proposal["id"]}/apply', {'requestId': 'apply-1'})['status'] == 'applied'
    catalog = client.get(BASE + '/item-organization/catalog').json()
    group = next(row for row in catalog['items'] if row['title'] == '论文共同目标')
    assert group['topicIds'] == [topic['id']]
    assert group['domainIds'] == [domain['id']]
    assert client.get(BASE + f'/items/{group["id"]}').json()['payload']['owner'] is None
    assert all(next(row for row in catalog['items'] if row['id'] == item['id'])['parentId'] == group['id']
               for item in (first, second))
    changed = client.get(BASE + f'/items/{first["id"]}').json()
    updated = client.patch(BASE + f'/items/{first["id"]}', json={'version': changed['version'],
                            'payload': {**changed['payload'], 'newProgress': '晚到成果'}})
    assert updated.status_code == 200, updated.text
    undone = post(client, f'/item-organization/proposals/{proposal["id"]}/undo', {'requestId': 'undo-1'})
    assert undone['status'] == 'undone'
    after = client.get(BASE + f'/items/{first["id"]}').json()
    assert after['status'] == first['status']
    assert after['payload']['note'] == '不可覆盖的原文'
    assert after['payload']['newProgress'] == '晚到成果'
    catalog = client.get(BASE + '/item-organization/catalog').json()
    assert next(row for row in catalog['items'] if row['id'] == first['id'])['parentId'] is None
    assert next(row for row in catalog['items'] if row['id'] == first['id'])['topicIds'] == []
    assert next(row for row in catalog['items'] if row['id'] == group['id'])['organizationStatus'] == 'undone'
    assert client.post(BASE + f'/item-organization/proposals/{proposal["id"]}/apply',
                       json={'requestId': 'apply-again'}).status_code == 409


def test_proposal_rejects_cycle_and_stale_preview(client):
    parent = create_item(client, '父项')
    child = create_item(client, '子项', {'parentId': parent['id']})
    cycle = client.post(BASE + '/item-organization/proposals', json={
        'requestId': 'cycle', 'changes': [{'itemId': parent['id'], 'itemVersion': parent['version'],
                                         'parentId': child['id'], 'reason': '不合法循环'}]})
    assert cycle.status_code == 400
    proposal = post(client, '/item-organization/proposals', {'requestId': 'stale', 'changes': [
        {'itemId': child['id'], 'itemVersion': child['version'], 'parentId': None, 'reason': '改为独立目标'}]})
    current = client.get(BASE + f'/items/{child["id"]}').json()
    assert client.patch(BASE + f'/items/{child["id"]}', json={'version': current['version'],
                                                               'payload': {**current['payload'], 'new': 1}}).status_code == 200
    assert client.post(BASE + f'/item-organization/proposals/{proposal["id"]}/apply',
                       json={'requestId': 'stale-apply'}).status_code == 409
    assert client.get(BASE + f'/item-organization/proposals/{proposal["id"]}').json()['status'] == 'proposed'


def test_undo_rejects_cycle_created_outside_original_batch(client):
    topic = create_entity(client, 'topic', '目标分类')
    parent = create_item(client, '原父项', {'topicIds': [topic['id']]})
    child = create_item(client, '原子项', {'parentId': parent['id']})
    proposal = post(client, '/item-organization/proposals', {'requestId': 'reparent-preview',
        'changes': [{'itemId': child['id'], 'itemVersion': child['version'], 'parentId': None,
                     'reason': '暂时独立'}]})
    post(client, f'/item-organization/proposals/{proposal["id"]}/apply', {'requestId': 'reparent-apply'})
    attach = post(client, '/relations', {'fromKind': 'item', 'fromId': parent['id'],
        'toKind': 'item', 'toId': child['id'], 'relationType': 'part_of'}, 201)
    assert attach['toId'] == child['id']
    undo = client.post(BASE + f'/item-organization/proposals/{proposal["id"]}/undo',
                       json={'requestId': 'reparent-undo'})
    assert undo.status_code == 400 or undo.status_code == 409
    catalog = client.get(BASE + '/item-organization/catalog').json()
    rows = {row['id']: row for row in catalog['items']}
    assert rows[parent['id']]['parentId'] == child['id']
    assert rows[child['id']]['parentId'] is None
    assert client.get(BASE + f'/item-organization/proposals/{proposal["id"]}').json()['status'] == 'applied'


def test_valid_parent_reversal_is_atomic_in_either_change_order(client):
    old_parent = create_item(client, '上级')
    old_child = create_item(client, '下级', {'parentId': old_parent['id']})
    proposal = post(client, '/item-organization/proposals', {'requestId': 'reverse-parent',
        'changes': [
            {'itemId': old_parent['id'], 'itemVersion': old_parent['version'],
             'parentId': old_child['id'], 'reason': '反转目标拆分'},
            {'itemId': old_child['id'], 'itemVersion': old_child['version'],
             'parentId': None, 'reason': '提升为一级目标'}]})
    assert post(client, f'/item-organization/proposals/{proposal["id"]}/apply',
                {'requestId': 'reverse-apply'})['status'] == 'applied'
    rows = {row['id']: row for row in client.get(BASE + '/item-organization/catalog').json()['items']}
    assert rows[old_parent['id']]['parentId'] == old_child['id']
    assert rows[old_child['id']]['parentId'] is None
    assert post(client, f'/item-organization/proposals/{proposal["id"]}/undo',
                {'requestId': 'reverse-undo'})['status'] == 'undone'
    rows = {row['id']: row for row in client.get(BASE + '/item-organization/catalog').json()['items']}
    assert rows[old_parent['id']]['parentId'] is None
    assert rows[old_child['id']]['parentId'] == old_parent['id']


def test_legacy_relation_and_item_update_cannot_bypass_parent_governance(client):
    first = create_item(client, '一级目标')
    second = create_item(client, '另一个目标')
    child = create_item(client, '业务子项', {'parentId': first['id']})
    duplicate_parent = client.post(BASE + '/relations', json={'fromKind': 'item', 'fromId': child['id'],
        'toKind': 'item', 'toId': second['id'], 'relationType': 'contributes_to'})
    assert duplicate_parent.status_code == 400
    cycle = client.post(BASE + '/relations', json={'fromKind': 'item', 'fromId': first['id'],
        'toKind': 'item', 'toId': child['id'], 'relationType': 'part_of'})
    assert cycle.status_code == 400
    forged = client.patch(BASE + f'/items/{child["id"]}', json={'version': child['version'],
                           'payload': {**child['payload'], 'parentId': second['id']}})
    assert forged.status_code == 400
    valid_reference = post(client, '/relations', {'fromKind': 'item', 'fromId': child['id'],
        'toKind': 'item', 'toId': second['id'], 'relationType': 'references'}, 201)
    assert valid_reference['relationType'] == 'references'


def test_group_inherits_only_common_explicit_owner(client):
    topic = create_entity(client, 'topic', '共同专题')
    first = create_item(client, '负责事项甲', {'owner': '张三', 'topicIds': [topic['id']]})
    second = create_item(client, '负责事项乙', {'owner': '张三', 'topicIds': [topic['id']]})
    proposal = post(client, '/item-organization/proposals', {'requestId': 'owner-group',
        'groups': [{'key': 'owner', 'title': '共同负责目标', 'goal': '共同完成',
                    'itemIds': [first['id'], second['id']]}]})
    assert proposal['groups'][0]['owner'] == '张三'
    post(client, f'/item-organization/proposals/{proposal["id"]}/apply', {'requestId': 'owner-apply'})
    group = next(row for row in client.get(BASE + '/item-organization/catalog').json()['items']
                 if row['title'] == '共同负责目标')
    assert client.get(BASE + f'/items/{group["id"]}').json()['payload']['owner'] == '张三'

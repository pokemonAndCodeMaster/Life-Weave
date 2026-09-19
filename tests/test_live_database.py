"""Real migrations, HTTP and persistence, in a disposable database only."""
from pathlib import Path
from uuid import uuid4
import os
import pytest
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def database_client(tmp_path_factory):
    if os.environ.get('LIFEWEAVE_TEST_DB') != '1':
        pytest.skip('LIFEWEAVE_TEST_DB=1 enables disposable PostgreSQL integration tests')
    from src.api.app import create_app
    from src.cli import migrate
    root = tmp_path_factory.mktemp('live-app')
    name = 'test_lifeweave_' + uuid4().hex[:12]
    connection = psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'), port=55440, user='lifeweave', dbname='postgres', autocommit=True)
    connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('LIFEWEAVE_DB_NAME', name)
        patch.setenv('LIFEWEAVE_LOCAL_WORKER', '0')
        patch.setenv('LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT', str(root/'personal'))
        patch.setenv('LIFEWEAVE_TEAM_KNOWLEDGE_ROOT', str(root/'team'))
        try:
            migrate()
            app = create_app()
            app.state.task_sources.root = root
            app.state.local_workers.root = root
            with TestClient(app) as active:
                yield active
        finally:
            connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            connection.close()


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    yield from database_client(tmp_path_factory)


@pytest.fixture
def dedicated_client(tmp_path_factory):
    yield from database_client(tmp_path_factory)


def post(client, route, body, status=201):
    response = client.post('/api/lifeweave/personal'+route, json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_legacy_api_keeps_method_body_query_and_same_data(client):
    old = '/api/gongzuo/personal/items'
    redirect = client.post(old, json={'itemType':'other','title':'旧入口继续使用'}, follow_redirects=False)
    assert redirect.status_code == 308
    assert redirect.headers['location'] == '/api/lifeweave/personal/items'
    created = client.post(old, json={'itemType':'other','title':'旧入口继续使用'})
    assert created.status_code == 201
    item_id = created.json()['id']
    assert client.get('/api/lifeweave/personal/items/'+item_id).json()['title'] == '旧入口继续使用'
    redirect = client.get('/api/gongzuo/personal/runs?state=failed&limit=5', follow_redirects=False)
    assert redirect.headers['location'] == '/api/lifeweave/personal/runs?state=failed&limit=5'
    assert client.post(old, json={}, headers={'Origin':'https://outside.example'}, follow_redirects=False).status_code == 403


def test_persistent_work_context_conflict_and_acceptance(client):
    item = post(client, '/items', {'itemType':'research','title':'真实数据库纵切','payload':{'goal':'明确结果'}})
    path = '/api/lifeweave/personal/items/'+item['id']
    assert client.get(path).json()['context']['content']['goal'] == '明确结果'
    assert client.get(path.replace('/personal/', '/team/')).status_code == 404
    accepted = client.post(path+'/accept', json={'version':1})
    assert accepted.status_code == 400
    changed = client.patch(path, json={'version':1,'status':'planned','payload':{'priority':2,'due':'2026-09-30'}})
    assert changed.status_code == 200, changed.text
    assert client.patch(path, json={'version':1,'title':'过时编辑'}).status_code == 409
    proposal = post(client, '/items/'+item['id']+'/context/proposals', {'baseVersion':1,'title':'补充目标','proposedContent':{'goal':'可核验的新目标'},'provenance':[]})
    post(client, '/context-proposals/'+proposal['id']+'/accept', {'version':1}, 200)
    assert client.get(path).json()['context']['content']['goal'] == '可核验的新目标'
    evidence = post(client, '/items/'+item['id']+'/evidence', {'artifactRef':'docs/result.md','artifactVersion':'test-v1','environmentRef':'isolated-integration-db','summary':'人工验证结果'})
    post(client, '/evidence/'+evidence['id']+'/review', {'status':'accepted','reason':'结果符合预期'}, 200)
    row = client.get(path).json()
    post(client, '/items/'+item['id']+'/accept', {'version':row['version']}, 200)
    assert client.get(path).json()['status'] == 'completed'


def test_knowledge_review_conflicts_and_external_read_only(client, tmp_path):
    library = client.app.state.library
    target = library.roots['personal']/'学习'/'笔记.md'
    draft = post(client,'/library/revisions',{'path':'学习/笔记.md','content':'# 笔记\n\n第一版','baseVersion':'new','reason':'真实审阅'})
    assert not target.exists()
    post(client,'/library/revisions/'+draft['id']+'/decision',{'accept':True},200)
    assert target.read_text() == '# 笔记\n\n第一版'
    doc = client.get('/api/lifeweave/personal/library/document', params={'path':'学习/笔记.md'}).json()
    draft2 = post(client,'/library/revisions',{'path':doc['path'],'content':'# 笔记\n第二版','baseVersion':doc['version'],'reason':'冲突验证'})
    target.write_text('# 笔记\n来自本地编辑器的新内容')
    response = client.post('/api/lifeweave/personal/library/revisions/'+draft2['id']+'/decision',json={'accept':True})
    assert response.status_code == 409
    assert '本地编辑器' in target.read_text()
    post(client,'/library/revisions/'+draft2['id']+'/decision',{'accept':False},200)
    outside = tmp_path/'external'; outside.mkdir(); file = outside/'index.md'; file.write_text('# 原知识\n独立来源')
    source = post(client,'/library/sources',{'title':'外部来源','root':str(outside)})
    doc = library.document('personal', source['id'], 'index.md')
    draft3 = post(client,'/library/revisions',{'sourceId':source['id'],'path':'index.md','content':'不可静默覆盖','baseVersion':doc['version'],'reason':'边界'})
    response = client.post('/api/lifeweave/personal/library/revisions/'+draft3['id']+'/decision',json={'accept':True})
    assert response.status_code == 409 and file.read_text() == '# 原知识\n独立来源'
    assert client.get('/api/lifeweave/team/library/document', params={'path':'index.md','sourceId':source['id']}).status_code == 404
    for path in ('../index.md','raw/index.md','/etc/passwd','.hidden.md'):
        assert client.get('/api/lifeweave/personal/library/document',params={'path':path}).status_code == 409
    (library.roots['personal']/'escape.md').symlink_to(file)
    assert client.get('/api/lifeweave/personal/library/document',params={'path':'escape.md'}).status_code == 409


class FakeLinear:
    def __init__(self):
        self.remote = {'id':'source-id','identifier':'TEST-1','title':'远程标题','description':'原描述','url':'https://linear.app/example/issue/TEST-1','updatedAt':'2026-09-18T00:00:00Z','priority':3}
        self.comments = {}; self.writes = 0; self.timeout = False
    def issue(self, identity): return dict(self.remote)
    def query(self, query, variables):
        if 'mutation' in query:
            self.writes += 1
            value = variables['input']; self.comments[value['id']] = {'id':value['id'],'body':value['body']}
            if self.timeout: raise ValueError('模拟响应丢失')
            return {'commentCreate':{'success':True,'comment':self.comments[value['id']]}}
        return {'comment':self.comments.get(variables['id'])}


def test_linear_import_preserves_local_and_publish_readback_is_idempotent(client):
    from src.integrations.linear import LinearService
    fake = FakeLinear()
    service = LinearService(client.app.state.database_manager.postgres(), fake, client.app.state.lifeweave_service)
    imported = service.import_issue('personal','TEST-1')
    item = service.work.get_item('personal', imported['itemId'])
    service.work.update_item('personal', item['id'], version=item['version'], title='本地重新澄清', status=None, payload={'due':None,'priority':1}, actor_id='local-user')
    fake.remote['title'] = '远程后来改过'; fake.remote['priority'] = 4
    assert service.import_issue('personal','TEST-1')['created'] is False
    after = service.work.get_item('personal', item['id'])
    assert after['title'] == '本地重新澄清' and after['payload'] == {'due':None,'priority':1}
    prepared = service.prepare('personal', item['id'], '## 真实正文预览\n固定内容')
    assert fake.writes == 0
    fake.timeout = True
    with pytest.raises(ValueError, match='响应丢失'): service.publish('personal',prepared['id'])
    assert service.publish('personal',prepared['id'])['status'] == 'confirmed'
    service.publish('personal',prepared['id'])
    assert fake.writes == 1


def test_task_inputs_are_frozen_and_run_limits_are_enforced(client, tmp_path):
    root = tmp_path/'skills'; method = root/'focused'; method.mkdir(parents=True)
    (method/'SKILL.md').write_text('---\nname: focused\ndescription: 有界方法\n---\n\n读 references/example.md')
    (method/'references').mkdir(); support = method/'references/example.md'; support.write_text('原方法依据')
    catalog = post(client,'/methods/roots',{'root':str(root)},200)
    method_id = catalog['items'][0]['id']
    item = post(client,'/items',{'itemType':'research','title':'验证委托输入','payload':{}})
    refs=[]
    for number in range(10):
        name=f'combination-{number}.md'
        (client.app.state.library.roots['personal']/name).write_text(f'# 文档 {number}\n独立事实 {number}')
        refs.append('local:'+name)
    payload = {'itemId':item['id'],'instruction':'只分析指定依据','engine':'codex','methodId':method_id,'knowledgeRefs':refs}
    run = post(client,'/runs',payload,202)
    snapshot = client.app.state.lifeweave_runtime_service.get_run_snapshot('personal',run['id'])
    entries = snapshot['capability_snapshot']
    assert len(entries) == 11 and entries[0]['files']['references/example.md'] == '原方法依据'
    support.write_text('源方法后来变化')
    assert snapshot['capability_snapshot'][0]['files']['references/example.md'] == '原方法依据'
    assert client.post('/api/lifeweave/personal/runs',json={**payload,'knowledgeRefs':['local:学习/笔记.md']*11}).status_code == 422
    assert client.post('/api/lifeweave/personal/runs',json={**payload,'methodId':'missing'}).status_code == 409
    cancelled = post(client,'/runs/'+run['id']+'/cancel',{},200)
    assert cancelled['state'] == 'cancelled'
    retry = post(client,'/runs/'+run['id']+'/retry',{'syncContext':True},202)
    assert client.app.state.lifeweave_runtime_service.get_run_snapshot('personal',retry['id'])['capability_snapshot'][0]['files']['references/example.md'] == '原方法依据'


def test_origin_boundary(client):
    assert client.post('/api/lifeweave/personal/items',json={'itemType':'personal','title':'不应创建'},headers={'Origin':'https://elsewhere.test'}).status_code == 403


def test_manual_result_body_is_readable_and_duplicate_save_is_idempotent(client):
    item=post(client,'/items',{'itemType':'research','title':'人工工作闭环','payload':{}})
    body={'title':'验证记录','content':'# 实际结果\n正文可阅读','verification':'已核对关键路径；远程协作尚未覆盖','environment':'本机浏览器'}
    first=post(client,'/items/'+item['id']+'/manual-results',body)
    again=post(client,'/items/'+item['id']+'/manual-results',body)
    assert first==again
    detail=client.get('/api/lifeweave/personal/items/'+item['id']).json()
    assert len(detail['evidence'])==1 and detail['evidence'][0]['payload']['body']==body['content']
    entity=client.get('/api/lifeweave/personal/entities/'+first['artifactId']).json()
    assert entity['payload']['body']==body['content']
    assert client.post('/api/lifeweave/team/items/'+item['id']+'/manual-results',json=body).status_code==404


def test_current_context_reaches_lists_meeting_and_export_without_rewriting_snapshot(client):
    item=post(client,'/items',{'itemType':'research','title':'多入口共识验证','payload':{'goal':'旧目标','scope':'旧范围','owner':'独立负责人'}})
    meeting=client.get('/api/lifeweave/personal/state').json()['meeting']
    response=client.put('/api/lifeweave/personal/meeting',json={'version':meeting['version'],'config':{'title':'范围验证','sections':[{'key':'deliveries','title':'交付','enabled':True,'mode':'generic','filters':{'itemIds':[item['id']]},'fields':['title','payload'],'payloadFields':['goal','scope','owner']}]}})
    assert response.status_code==200,response.text
    snapshot=post(client,'/meeting/freeze',{})
    proposal=post(client,'/items/'+item['id']+'/context/proposals',{'baseVersion':1,'title':'澄清目标','proposedContent':{'goal':'新目标','scope':'新范围'}})
    pending=next(row for row in client.get('/api/lifeweave/personal/state').json()['items'] if row['id']==item['id'])
    assert pending['contextProposals'][0]['id']==proposal['id']
    post(client,'/context-proposals/'+proposal['id']+'/accept',{'version':1},200)
    current=next(row for row in client.get('/api/lifeweave/personal/state').json()['items'] if row['id']==item['id'])
    assert current['context']['content']['goal']=='新目标' and current['payload']['goal']=='旧目标'
    preview=client.get('/api/lifeweave/personal/meeting/preview').json()
    assert preview['sections'][0]['entries'][0]['values']['payload']=={'goal':'新目标','scope':'新范围','owner':'独立负责人'}
    exported=client.get('/api/lifeweave/personal/meeting/markdown').text
    assert '目标：新目标' in exported and '范围：新范围' in exported
    frozen=client.get('/api/lifeweave/personal/meeting/markdown',params={'snapshotId':snapshot['id']}).text
    assert '目标：旧目标' in frozen and '新目标' not in frozen


def test_team_local_worker_requires_explicit_account_choice(client):
    response=client.put('/api/lifeweave/team/settings/local-worker',json={'enabled':True,'useLocalAccount':False})
    assert response.status_code==409
    assert client.get('/api/lifeweave/team/settings').json()['localWorker']['enabled'] is False


def test_continuation_feedback_is_idempotent_scoped_and_pinned_in_next_run(client):
    item = post(client, '/items', {'itemType':'research','title':'维护噪声识别方法','initialContext':{'goal':'先讨论误报的适用范围，不做代码'}})
    path = '/items/' + item['id']
    payload = {'body':'重点是标注分歧，先不要比较训练速度','requestId':'feedback-once'}
    first = post(client, path+'/feedback', payload)
    again = post(client, path+'/feedback', payload)
    assert first == again
    assert client.post('/api/lifeweave/personal'+path+'/feedback',json={**payload,'body':'不同内容'}).status_code == 409
    assert client.post('/api/lifeweave/team'+path+'/feedback',json=payload).status_code == 404
    assert client.post('/api/lifeweave/personal'+path+'/feedback',json={**payload,'runId':'missing'}).status_code == 400
    assert client.post('/api/lifeweave/personal'+path+'/feedback',json={**payload,'body':'  '}).status_code == 400
    current = client.get('/api/lifeweave/personal'+path+'/continuation').json()
    assert current['context']['content']['goal'] == '先讨论误报的适用范围，不做代码'
    assert [f['id'] for f in current['feedback']] == [first['id']]
    run = post(client, '/runs', {'itemId':item['id'],'instruction':'只讨论','engine':'codex'}, 202)
    runtime = client.app.state.lifeweave_runtime_service
    original = runtime.get_run_snapshot('personal',run['id'])['prompt_snapshot']
    assert payload['body'] in original
    second = post(client, path+'/feedback', {'body':'补充考虑漏检','requestId':'feedback-two','runId':run['id']})
    post(client, '/runs/'+run['id']+'/cancel', {}, 200)
    retried = post(client, '/runs/'+run['id']+'/retry', {'syncContext':False}, 202)
    snapshot = runtime.get_run_snapshot('personal', retried['id'])
    assert [f['id'] for f in snapshot['environment_snapshot']['feedbackSnapshot']] == [first['id'], second['id']]
    assert '补充考虑漏检' in snapshot['prompt_snapshot']
    assert runtime.get_run_snapshot('personal',run['id'])['prompt_snapshot'] == original
    third = post(client, '/items', {'itemType':'personal','title':'另一项生活工作'})
    assert client.post('/api/lifeweave/personal/items/'+third['id']+'/feedback',json={'body':'不属于这个事项','requestId':'wrong-run','runId':run['id']}).status_code == 400


def test_discovery_and_recommendations_reuse_accepted_knowledge_without_a_paper_fixture(client, tmp_path):
    idea = post(client, '/entities', {'entityType':'idea','title':'整理阳台植物','payload':{'body':'想了解采光，暂时只记录'}})
    assert any(row['id'] == idea['id'] for row in client.get('/api/lifeweave/personal/work-discovery?query=阳台采光').json()['items'])
    item = post(client, '/items', {'itemType':'personal','title':'阳台采光记录','initialContext':{'goal':'比较朝向对植物采光的影响'}})
    draft = post(client, '/library/revisions', {'path':'生活/采光.md','content':'# 阳台采光\n植物朝向影响照射时长。','baseVersion':'new','reason':'已有领域知识'})
    post(client, '/library/revisions/'+draft['id']+'/decision', {'accept':True}, 200)
    method = tmp_path/'methods'/'lighting'; method.mkdir(parents=True)
    (method/'SKILL.md').write_text('---\nname: lighting\ndescription: 比较植物采光的观察方法\n---\n\n保留朝向、时间与实际观察。')
    post(client, '/methods/roots', {'root':str(method.parent)}, 200)
    path = '/api/lifeweave/personal/items/'+item['id']+'/input-recommendations'
    before = client.get(path).json()
    assert 'local:生活/采光.md' in before['suggested']['knowledgeRefs']
    assert before['methods'][0]['title'] == 'lighting'
    full = client.get('/api/lifeweave/personal/methods/'+before['methods'][0]['id'])
    assert full.status_code == 200 and '保留朝向' in full.json()['content']
    assert full.json()['version'] == before['methods'][0]['version']
    assert client.get('/api/lifeweave/team/methods/'+before['methods'][0]['id']).status_code == 409
    assert before['methods'][0]['matchedTerms'] and before['documents'][0]['version']
    version = next(d['version'] for d in before['documents'] if d['ref'] == 'local:生活/采光.md')
    (client.app.state.library.roots['personal']/'生活/采光.md').write_text('# 阳台采光\n补充新观察')
    run = post(client, '/runs', {'itemId':item['id'],'instruction':'观察植物采光','engine':'codex',**before['suggested']}, 202)
    snapshot = client.app.state.lifeweave_runtime_service.get_run_snapshot('personal',run['id'])
    doc = next(d for d in snapshot['capability_snapshot'] if d.get('sourcePath') == 'local:生活/采光.md')
    assert doc['version'] != version and '补充新观察' in doc['content']
    assert snapshot['environment_snapshot']['inputRecommendations']['strategy'] == 'lexical-v1'
    assert client.get(path.replace('/personal/','/team/')).status_code == 404
    assert client.get('/api/lifeweave/team/work-discovery?query=阳台').json()['items'] == []
    assert client.get('/api/lifeweave/personal/work-discovery?query=zyxwuniqueunmatched').json()['items'] == []


def test_worker_http_reports_keep_input_provenance_and_retry_uses_current_feedback(client):
    runtime = client.app.state.lifeweave_runtime_service
    base = '/api/lifeweave/team'

    def send(path, body, status=200, headers=None):
        response = client.post(base+path, json=body, headers=headers)
        assert response.status_code == status, response.text
        return response.json()

    machine = send('/machines/register', {'name':'input provenance regression','capacity':1,
                   'engines':['codex'],'runtimes':['native']}, 201,
                   {'X-LifeWeave-Registration-Token':runtime.registration_tokens['team']})
    auth = {'X-LifeWeave-Worker-Token':machine['workerToken']}
    item = send('/items', {'itemType':'research','title':'运行全过程保留依据'}, 201)
    feedback_path = '/items/'+item['id']+'/feedback'
    first = send(feedback_path, {'body':'先核对依据','requestId':'before-running'}, 201)
    run = send('/runs', {'itemId':item['id'],'instruction':'核对依据','engine':'codex',
                        'machineId':machine['id']}, 202)
    fixed = run['environmentSnapshot']
    original_prompt = runtime.get_run_snapshot('team', run['id'])['prompt_snapshot']
    claim = send('/worker/'+machine['id']+'/claim', {'leaseSeconds':30}, headers=auth)
    assert claim['id'] == run['id']
    report_path = '/worker/'+machine['id']+'/runs/'+run['id']+'/report'
    for outcome, environment in (
        ('running', {'runtime':'native','actualDirectory':'/isolated/task',
                     'feedbackSnapshot':[], 'selectedInputs':{'forged':True},
                     'inputRecommendations':{'forged':True}}),
        ('succeeded', {'exitObserved':True}),
    ):
        saved = send(report_path, {'leaseId':claim['lease_id'],'outcome':outcome,
                                  'exitCode':0,'environment':environment}, headers=auth)
        actual = saved['environmentSnapshot']
        for key in ('feedbackSnapshot','selectedInputs','inputRecommendations','requestedRuntime'):
            assert actual[key] == fixed[key]
        assert actual['actualDirectory'] == '/isolated/task'
    current = client.get(base+'/runs/'+run['id']).json()
    assert current['environmentSnapshot']['feedbackSnapshot'][0]['id'] == first['id']
    second = send(feedback_path, {'body':'补充第二轮问题','requestId':'after-running','runId':run['id']}, 201)
    retry = send('/runs/'+run['id']+'/retry', {'syncContext':False}, 202)
    assert [f['id'] for f in retry['environmentSnapshot']['feedbackSnapshot']] == [first['id'],second['id']]
    assert retry['environmentSnapshot']['selectedInputs'] == fixed['selectedInputs']
    assert runtime.get_run_snapshot('team', run['id'])['prompt_snapshot'] == original_prompt


@pytest.mark.parametrize('transport', ['http', 'local'])
def test_pdf_nul_does_not_abort_worker_and_original_evidence_is_recoverable(dedicated_client, transport):
    import asyncio
    import base64
    import hashlib
    import json
    from src.lifeweave_runtime.worker import ServiceWorkerClient

    client = dedicated_client
    runtime = client.app.state.lifeweave_runtime_service
    base = '/api/lifeweave/personal'
    registered = client.post(base+'/machines/register', json={
        'name': 'PDF NUL '+transport, 'capacity': 1, 'engines': ['codex'], 'runtimes': ['native'],
    }, headers={'X-LifeWeave-Registration-Token': runtime.registration_tokens['personal']})
    assert registered.status_code == 201, registered.text
    machine = registered.json()
    auth = {'X-LifeWeave-Worker-Token': machine['workerToken']}
    prefix = base+'/worker/'+machine['id']
    local = ServiceWorkerClient(runtime, 'personal', machine['id'], machine['workerToken'])
    item = post(client, '/items', {'itemType': 'research', 'title': 'PDF 控制字符回归 '+transport})
    run = post(client, '/runs', {'itemId': item['id'], 'instruction': '读取论文',
                               'engine': 'codex', 'machineId': machine['id']}, 202)
    claim = client.post(prefix+'/claim', json={'leaseSeconds': 30}, headers=auth).json()
    assert claim['id'] == run['id']

    def send(kind, body):
        if transport == 'local':
            return asyncio.run(getattr(local, kind)(run['id'], body))
        response = client.post(prefix+'/runs/'+run['id']+'/'+('events' if kind == 'event' else kind),
                               json=body, headers=auth)
        assert response.status_code in (200, 201, 202), response.text
        return response.json()

    send('report', {'lease_id': claim['lease_id'], 'outcome': 'running'})
    original_event = {
        'event_type': 'item.completed', 'source': 'codex', 'channel': 'stdout',
        'summary': 'PDF 提取\0完成',
        'payload': {'item': {'text': 'ADEn\0中文\n下一行', 'literal': r'\u0000',
                             'nested': [{'\0key': '原值', '␀key': '另一个键'}]}},
    }
    send('event', {'lease_id': claim['lease_id'], **original_event})
    events = client.get(base+'/runs/'+run['id']+'/events').json()['items']
    event = next(entry for entry in events if entry['eventType'] == 'item.completed')
    assert event['summary'] == 'PDF 提取␀完成'
    encoded = event['payload']['_lifeweaveTextStorage']['originalJsonBase64']
    assert json.loads(base64.b64decode(encoded)) == original_event
    assert event['payload']['item']['literal'] == r'\u0000'
    assert len(event['payload']['item']['nested'][0]['entries']) == 2
    report = {'lease_id': claim['lease_id'], 'outcome': 'succeeded', 'exit_code': 0,
              'result': '# 论文\n\n公式 ADEn\0已提取',
              'result_payload': {'report': '# 论文\n\n公式 ADEn\0已提取'},
              'environment': {'reader': 'PDF\0reader', 'selectedInputs': {'forged': True}}}
    version = 'sha256:'+hashlib.sha256(report['result'].encode()).hexdigest()
    report['artifacts'] = [{'kind': 'executor-result', 'version': version}]
    send('report', report)
    saved = client.get(base+'/runs/'+run['id']).json()
    assert saved['state'] == 'succeeded' and '␀' in saved['result']
    assert saved['environmentSnapshot']['selectedInputs'] == run['environmentSnapshot']['selectedInputs']
    encoded = saved['environmentSnapshot']['_lifeweaveTextStorage']['originalJsonBase64']
    recovered = json.loads(base64.b64decode(encoded))
    assert recovered['result'] == report['result']
    assert recovered['result_payload'] == report['result_payload']
    output = client.get(base+'/items/'+item['id']+'/research-output').json()['current']
    assert output['content'] == '# 论文\n\n公式 ADEn␀已提取'
    assert 'NUL' in output['storageNote'] and output['rawDownloadUrl'].endswith('/artifacts/result')
    artifact = client.get(output['rawDownloadUrl'])
    assert artifact.content == report['result'].encode()
    assert artifact.headers['X-Artifact-Version'] == 'sha256:'+hashlib.sha256(artifact.content).hexdigest()
    readable = client.get(output['downloadUrl'])
    assert readable.text == output['content']
    assert readable.headers['ETag'] == '"'+hashlib.sha256(readable.content).hexdigest()+'"'

"""Real migrations, HTTP and persistence, in a disposable database only."""
from pathlib import Path
from uuid import uuid4
import os
import pytest
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    if os.environ.get('GONGZUO_TEST_DB') != '1':
        pytest.skip('GONGZUO_TEST_DB=1 enables disposable PostgreSQL integration tests')
    from src.api.app import create_app
    from src.cli import migrate
    root = tmp_path_factory.mktemp('live-app')
    name = 'test_gongzuo_' + uuid4().hex[:12]
    connection = psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'), port=55440, user='gongzuo', dbname='postgres', autocommit=True)
    connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('GONGZUO_DB_NAME', name)
        patch.setenv('GONGZUO_LOCAL_WORKER', '0')
        patch.setenv('GONGZUO_PERSONAL_KNOWLEDGE_ROOT', str(root/'personal'))
        patch.setenv('GONGZUO_TEAM_KNOWLEDGE_ROOT', str(root/'team'))
        try:
            migrate()
            app = create_app()
            app.state.task_sources.root = root
            with TestClient(app) as active:
                yield active
        finally:
            connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            connection.close()


def post(client, route, body, status=201):
    response = client.post('/api/gongzuo/personal'+route, json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_persistent_work_context_conflict_and_acceptance(client):
    item = post(client, '/items', {'itemType':'research','title':'真实数据库纵切','payload':{'goal':'明确结果'}})
    path = '/api/gongzuo/personal/items/'+item['id']
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
    doc = client.get('/api/gongzuo/personal/library/document', params={'path':'学习/笔记.md'}).json()
    draft2 = post(client,'/library/revisions',{'path':doc['path'],'content':'# 笔记\n第二版','baseVersion':doc['version'],'reason':'冲突验证'})
    target.write_text('# 笔记\n来自本地编辑器的新内容')
    response = client.post('/api/gongzuo/personal/library/revisions/'+draft2['id']+'/decision',json={'accept':True})
    assert response.status_code == 409
    assert '本地编辑器' in target.read_text()
    post(client,'/library/revisions/'+draft2['id']+'/decision',{'accept':False},200)
    outside = tmp_path/'external'; outside.mkdir(); file = outside/'index.md'; file.write_text('# 原知识\n独立来源')
    source = post(client,'/library/sources',{'title':'外部来源','root':str(outside)})
    doc = library.document('personal', source['id'], 'index.md')
    draft3 = post(client,'/library/revisions',{'sourceId':source['id'],'path':'index.md','content':'不可静默覆盖','baseVersion':doc['version'],'reason':'边界'})
    response = client.post('/api/gongzuo/personal/library/revisions/'+draft3['id']+'/decision',json={'accept':True})
    assert response.status_code == 409 and file.read_text() == '# 原知识\n独立来源'
    assert client.get('/api/gongzuo/team/library/document', params={'path':'index.md','sourceId':source['id']}).status_code == 404
    for path in ('../index.md','raw/index.md','/etc/passwd','.hidden.md'):
        assert client.get('/api/gongzuo/personal/library/document',params={'path':path}).status_code == 409
    (library.roots['personal']/'escape.md').symlink_to(file)
    assert client.get('/api/gongzuo/personal/library/document',params={'path':'escape.md'}).status_code == 409


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
    service = LinearService(client.app.state.database_manager.postgres(), fake, client.app.state.gongzuo_service)
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
    payload = {'itemId':item['id'],'instruction':'只分析指定依据','engine':'codex','methodId':method_id,'knowledgeRefs':['local:学习/笔记.md']*10}
    run = post(client,'/runs',payload,202)
    snapshot = client.app.state.gongzuo_runtime_service.get_run_snapshot('personal',run['id'])
    entries = snapshot['capability_snapshot']
    assert len(entries) == 2 and entries[0]['files']['references/example.md'] == '原方法依据'
    support.write_text('源方法后来变化')
    assert snapshot['capability_snapshot'][0]['files']['references/example.md'] == '原方法依据'
    assert client.post('/api/gongzuo/personal/runs',json={**payload,'knowledgeRefs':['local:学习/笔记.md']*11}).status_code == 422
    assert client.post('/api/gongzuo/personal/runs',json={**payload,'methodId':'missing'}).status_code == 409
    cancelled = post(client,'/runs/'+run['id']+'/cancel',{},200)
    assert cancelled['state'] == 'cancelled'
    retry = post(client,'/runs/'+run['id']+'/retry',{'syncContext':True},202)
    assert client.app.state.gongzuo_runtime_service.get_run_snapshot('personal',retry['id'])['capability_snapshot'][0]['files']['references/example.md'] == '原方法依据'


def test_origin_boundary(client):
    assert client.post('/api/gongzuo/personal/items',json={'itemType':'personal','title':'不应创建'},headers={'Origin':'https://elsewhere.test'}).status_code == 403

"""W3 uses a disposable PostgreSQL database; no live model or daily data writes."""
import base64
from pathlib import Path

import pytest

from test_live_database import client, post
from src.lifeweave.research_outputs import ResearchOutputs, router

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


@pytest.fixture
def output_client(client, tmp_path):
    if not hasattr(client.app.state, 'research_outputs'):
        state = client.app.state
        state.research_outputs = ResearchOutputs(state.lifeweave_service, state.lifeweave_runtime_service, state.library, tmp_path)
        fallback = client.app.router.routes.pop()
        client.app.include_router(router)
        client.app.router.routes.append(fallback)
    client.app.state.research_outputs.root = tmp_path
    return client


def completed_run(client, item_id, body='# 研究\n\n受控测试的成果', state='succeeded'):
    run = post(client,'/runs',{'itemId':item_id,'instruction':'受控结果测试，不调用模型','engine':'codex'},202)
    # Explicitly synthetic terminal state in an isolated fixture only.
    client.app.state.database_manager.postgres().execute(
        'UPDATE workbench.t_lifeweave_run SET state=%s,result=%s,finished_at=now() WHERE id=%s', (state,body,run['id']))
    return run


def test_current_output_preserves_manual_old_and_failed_runs(output_client):
    c=output_client
    item=post(c,'/items',{'itemType':'research','title':'成果版本验证'})['id']
    url=f'/api/lifeweave/personal/items/{item}/research-output'
    assert c.get(url).json()=={'current':None,'versions':[]}
    manual=post(c,f'/items/{item}/manual-results',{'title':'人工成果','content':'原来的人工正文','verification':'受控fixture','environment':'临时库'})
    assert c.get(url).json()['current']['id']==manual['artifactId']
    first=completed_run(c,item,'# 第一版\n\n保留旧版')
    latest=completed_run(c,item,'# 当前版\n\n训练数据解释')
    failed=completed_run(c,item,'失败前的部分输出','failed')
    result=c.get(url).json()
    assert result['current']['id']==latest['id']
    assert {out['id'] for out in result['versions']}=={first['id'],latest['id'],failed['id'],manual['artifactId']}
    assert c.get(url.replace('/personal/','/team/')).status_code==404
    download=c.get(result['current']['downloadUrl'])
    assert download.text=='# 当前版\n\n训练数据解释' and download.headers['x-content-type-options']=='nosniff'
    assert 'attachment' in download.headers['content-disposition']


def test_candidates_are_atomic_retryable_reviewed_and_reusable(output_client):
    c=output_client
    item=post(c,'/items',{'itemType':'research','title':'稀缺数据研究'})['id']
    run=completed_run(c,item)
    route=f'/items/{item}/knowledge-candidates'
    body={'runId':run['id'],'path':'研究/稀缺数据.md','content':'# 稀缺数据\n\n保留样本分布依据。','baseVersion':'new','reason':'从成果提炼','requestId':'same-request'}
    draft=post(c,route,body)
    assert draft['status']=='draft' and draft['runId']==run['id'] and '+来源：' in draft['diff']
    assert post(c,route,body)['id']==draft['id']
    assert c.post('/api/lifeweave/personal'+route,json={**body,'content':'different'}).status_code==409
    target=c.app.state.library.roots['personal']/body['path']
    assert not target.exists()
    post(c,'/library/revisions/'+draft['id']+'/decision',{'accept':True},200)
    assert '保留样本分布依据' in target.read_text() and run['id'] in target.read_text()
    assert c.get('/api/lifeweave/personal'+route).json()[0]['status']=='accepted'
    other=post(c,'/items',{'itemType':'research','title':'新任务讨论稀缺数据'})['id']
    recommendations=c.get(f'/api/lifeweave/personal/items/{other}/input-recommendations',params={'query':'稀缺数据'}).json()
    recommended=next(row for row in recommendations['documents'] if row['path']==body['path'])
    assert recommended['sourceId']=='local'
    assert recommended['version']==c.app.state.library.document('personal','local',body['path'])['version']
    doc=c.app.state.library.document('personal','local',body['path'])
    second=post(c,route,{**body,'baseVersion':doc['version'],'content':'第二版','requestId':'second'})
    target.write_text('# 更新的原文\n外部编辑后的事实')
    assert c.post('/api/lifeweave/personal/library/revisions/'+second['id']+'/decision',json={'accept':True}).status_code==409
    assert '外部编辑后的事实' in target.read_text()
    post(c,'/library/revisions/'+second['id']+'/decision',{'accept':False},200)
    assert '外部编辑后的事实' in target.read_text()
    assert c.post(f'/api/lifeweave/personal/items/{other}/knowledge-candidates',json=body).status_code==409
    current=c.app.state.library.document('personal','local',body['path'])
    merged=post(c,route,{**body,'baseVersion':current['version'],'content':'# 合并后的稀缺数据\n已保留外部编辑后的事实','requestId':'merged'})
    post(c,'/library/revisions/'+merged['id']+'/decision',{'accept':True},200)
    assert '合并后' in target.read_text()
    # Feedback remains in the existing continuation/next-run source of truth.
    feedback=post(c,f'/items/{item}/feedback',{'body':'引用训练数据段：解释不足','runId':run['id'],'requestId':'quote-1','anchor':'训练数据:paragraph-1'})
    recorded=c.get(f'/api/lifeweave/personal/items/{item}/continuation').json()['feedback']
    assert recorded[0]['anchor']=='训练数据:paragraph-1' and recorded[0]['runId']==run['id']


def test_assets_check_scope_paths_bytes_and_missing_files(output_client,tmp_path):
    c=output_client
    item=post(c,'/items',{'itemType':'research','title':'图片边界'})['id'];run=completed_run(c,item)
    folder=c.app.state.research_outputs.root/'.runtime/executions/personal'/run['id']/'repo'
    folder.mkdir(parents=True)
    (folder/'figure.png').write_bytes(PNG);(folder/'fake.png').write_text('<svg onload="alert(1)"/>')
    outside=tmp_path/'outside.png';outside.write_bytes(PNG);(folder/'escape.png').symlink_to(outside)
    url=f'/api/lifeweave/personal/runs/{run["id"]}/assets'
    image=c.get(url,params={'path':'figure.png'})
    assert image.status_code==200 and image.content==PNG
    assert image.headers['content-type']=='image/png' and image.headers['x-content-type-options']=='nosniff'
    assert c.get(url,params={'path':'missing.png'}).status_code==404
    for path in ('../outside.png','/etc/passwd','fake.png','escape.png','.git/config'):
        assert c.get(url,params={'path':path}).status_code==409
    assert c.get(url.replace('/personal/','/team/'),params={'path':'figure.png'}).status_code==404
    # A replaced run folder cannot redirect this API to another run's images.
    foreign=folder.parent.parent/'another-run'/'artifacts';foreign.mkdir(parents=True)
    (foreign/'figure.png').write_bytes(PNG)
    (folder.parent/'artifacts').symlink_to(foreign,target_is_directory=True)
    assert c.get(url,params={'path':'artifacts/figure.png'}).status_code==409


def test_source_link_and_review_rollback_share_one_transaction(output_client,monkeypatch):
    c=output_client
    item=post(c,'/items',{'itemType':'research','title':'事务失败验证'})['id'];run=completed_run(c,item)
    library=c.app.state.library; original=library.propose
    before=library.db.fetch_one('SELECT count(*) AS n FROM workbench.document_revision')['n']
    def broken(*args,**kwargs):
        revision=original(*args,**kwargs)
        raise RuntimeError('fail after revision insert')
    monkeypatch.setattr(library,'propose',broken)
    with pytest.raises(RuntimeError):
        c.app.state.research_outputs.propose_from_run('personal',item,run['id'],'rollback.md','草稿','new','验证','failed-request')
    assert library.db.fetch_one('SELECT count(*) AS n FROM workbench.document_revision')['n']==before
    assert library.db.fetch_one('SELECT count(*) AS n FROM workbench.research_knowledge_candidate WHERE item_id=%s',(item,))['n']==0


def test_generated_research_sources_remain_readable_without_opening_private_paths(output_client,tmp_path,monkeypatch):
    c=output_client
    monkeypatch.setattr(c.app.state,'root',tmp_path)
    item=post(c,'/items',{'itemType':'research','title':'来源链接'})['id'];run=completed_run(c,item)
    root=tmp_path/'.runtime/executions/personal'/run['id']/'repo'
    research=root/'.runtime/research';research.mkdir(parents=True)
    (research/'sources.md').write_text('# 已读取来源')
    (root/'.env').write_text('PRIVATE=not-public')
    (research/'escape.md').symlink_to(root/'.env')
    url=f'/api/lifeweave/personal/runs/{run["id"]}/source'
    assert c.get(url,params={'path':'.runtime/research/sources.md'}).text=='# 已读取来源'
    for path in ('.env','.runtime/../.env','.runtime/research/../../.env','.runtime/research/.private.md','.runtime/research/escape.md'):
        assert c.get(url,params={'path':path}).status_code==400

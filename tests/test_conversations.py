"""Conversation business effects over real HTTP and a disposable PostgreSQL DB.

Only semantic decisions are controlled here; real model evidence is separate.
"""
import asyncio
import time
from copy import deepcopy
from pathlib import Path
import pytest
from test_live_database import client
from src.lifeweave.conversation_models import Decision


class Interpreter:
    def __init__(self): self.contexts=[]; self.decision=None
    async def interpret(self, workspace, tid, context, event):
        self.contexts.append(deepcopy(context))
        if self.decision=='wait':
            await asyncio.sleep(60)
        if self.decision=='error':
            raise ValueError('受控执行器失败')
        return Decision.model_validate(self.decision)


def decision(intent='answer', **changes):
    return dict(intent=intent,reply='这是受控模型响应',title='独立目标',itemId=None,
                itemType='research',instruction='核对材料并交付结果',feedback=None,
                proposedGoal=None,knowledge=None,**changes)


@pytest.fixture
def web(client,monkeypatch):
    model=Interpreter()
    monkeypatch.setattr(client.app.state.conversations,'interpreter',model)
    return client,model


def post(c,path,body,status=201):
    r=c.post('/api/lifeweave/personal'+path,json=body)
    assert r.status_code==status,r.text
    return r.json()


def turn(c,cid,body,mode='auto',request_id=None,**extra):
    r=post(c,f'/conversations/{cid}/turns',{'body':body,'mode':mode,'requestId':request_id or body,**extra},202)
    for _ in range(100):
        row=next(t for t in c.get('/api/lifeweave/personal/conversations/'+cid).json()['turns'] if t['id']==r['id'])
        if row['status'] not in {'queued','processing'}: return row
        time.sleep(.01)
    raise AssertionError('turn did not finish')


def test_question_record_execute_receipts_and_idempotency(web):
    c,m=web
    cid=post(c,'/conversations',{'requestId':'paths'})['id']
    before=c.get('/api/lifeweave/personal/state').json()
    m.decision=decision()
    row=turn(c,cid,'普通问题')
    assert row['status']=='completed' and row['receipts']==[] and row['itemId'] is None
    assert len(c.get('/api/lifeweave/personal/state').json()['items'])==len(before['items'])
    m.decision='error'
    row=turn(c,cid,'周末种番茄，先记一下','record')
    assert row['status']=='completed' and row['receipts'][0]['kind']=='idea'
    assert len(m.contexts)==1
    repeated=turn(c,cid,'周末种番茄，先记一下','record')
    assert row==repeated
    assert c.post(f'/api/lifeweave/personal/conversations/{cid}/turns',json={'body':'不同原话','mode':'record','requestId':'周末种番茄，先记一下'}).status_code==409
    m.decision=decision('execute')
    row=turn(c,cid,'请开始研究阳台植物的采光')
    assert row['status']=='completed' and row['runId']
    assert [r['kind'] for r in row['receipts']]==['item','discussion','run']
    run=c.get('/api/lifeweave/personal/runs/'+row['runId']).json()
    assert run['state']=='queued'
    assert turn(c,cid,'请开始研究阳台植物的采光')==row
    assert c.get('/api/lifeweave/team/conversations/'+cid).status_code==404
    assert c.post('/api/lifeweave/team/conversations/'+cid+'/turns',json={'body':'跨空间','requestId':'cross'}).status_code==404


def test_discussion_constraint_and_action_failure_are_atomic(web,monkeypatch):
    c,m=web
    cid=post(c,'/conversations',{'requestId':'atomic'})['id']
    count=len(c.get('/api/lifeweave/personal/state').json()['items'])
    m.decision=decision('execute')
    row=turn(c,cid,'只是讨论，不执行','discuss')
    assert row['status']=='failed' and not row['receipts'] and not row['itemId']
    assert len(c.get('/api/lifeweave/personal/state').json()['items'])==count
    def fail_run(*args,**kwargs): raise ValueError('材料已丢失')
    monkeypatch.setattr(c.app.state.lifeweave_runtime_service,'create_run',fail_run)
    row=turn(c,cid,'请研究另一个新目标')
    assert row['status']=='failed' and '材料已丢失' in row['error']
    assert len(c.get('/api/lifeweave/personal/state').json()['items'])==count
    m.decision=decision();m.decision['itemId']='forged-cross-workspace'
    row=turn(c,cid,'不要相信伪造身份')
    assert row['status']=='failed'


def test_explicit_development_conversation_starts_read_only_plan(web, tmp_path):
    from test_development import repository
    c, model = web
    root = repository(tmp_path)
    cid = post(c, '/conversations', {'requestId': 'development-conversation'})['id']
    model.decision = decision('execute')
    model.decision['itemType'] = 'fix'
    model.decision['instruction'] = 'Fix the issue in the selected repository'
    row = turn(c, cid, '请修复这个项目的问题', 'execute', repositoryPath=str(root))
    assert row['status'] == 'completed' and row['runId']
    assert [receipt['kind'] for receipt in row['receipts']] == ['item', 'discussion', 'development']
    assignment = c.get(f'/api/lifeweave/personal/items/{row["itemId"]}/development').json()['items'][0]
    assert assignment['planRunId'] == row['runId'] and assignment['status'] == 'planning'
    run = c.app.state.lifeweave_runtime_service.get_run_snapshot('personal', row['runId'])
    assert run['sandbox'] == 'read-only' and run['state'] == 'queued'
    assert row['inputContext']['repositoryPath'] == str(root)
    model.decision = decision('execute')
    model.decision['itemType'] = 'requirement'
    without_repo = turn(c, cid, '请新增另一个项目的功能', 'execute')
    assert without_repo['status'] == 'completed' and without_repo['runId'] is None
    assert without_repo['receipts'][-1]['kind'] == 'development'


def test_feedback_profile_and_previous_output_reach_next_run(web):
    c,m=web
    item=post(c,'/items',{'itemType':'research','title':'反馈和偏好','initialContext':{'goal':'理解采光'}})
    cid=post(c,'/conversations',{'requestId':'feedback','itemId':item['id']})['id']
    profile=c.get('/api/lifeweave/personal/personal-model').json()
    value={'version':profile['version'],'goals':'了解植物','preferences':'解释时先给一个具体例子'}
    r=c.put('/api/lifeweave/personal/personal-model',json=value)
    assert r.status_code==200
    assert c.put('/api/lifeweave/personal/personal-model',json=value).status_code==409
    assert c.get('/api/lifeweave/team/personal-model').json()['preferences']==''
    prior=post(c,'/runs',{'itemId':item['id'],'engine':'codex','instruction':'原任务'},202)
    db=c.app.state.database_manager.postgres()
    db.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded',result=%s,finished_at=now() WHERE id=%s",('# 旧成果\n需要解释训练数据。',prior['id']))
    m.decision=decision('execute');m.decision['feedback']='本段要补充来源';m.decision['itemId']=item['id']
    row=turn(c,cid,'这次简短说明训练数据来源并修订全文',runId=prior['id'],anchor='训练数据')
    assert row['status']=='completed'
    run=c.app.state.lifeweave_runtime_service.get_run_snapshot('personal',row['runId'])
    assert '先给一个具体例子' in run['prompt_snapshot']
    assert '需要解释训练数据' in run['prompt_snapshot']
    assert run['environment_snapshot']['feedbackSnapshot'][-1]['anchor']=='训练数据'
    assert row['inputContext']=={'itemId':item['id'],'runId':prior['id'],'anchor':'训练数据',
                                 'repositoryPath':None,'acknowledgeExcludedChanges':False}
    assert c.get('/api/lifeweave/personal/personal-model').json()['preferences']=='解释时先给一个具体例子'
    assert m.contexts[-1]['profile']['goals']=='了解植物'
    assert c.app.state.lifeweave_runtime_service.get_run_snapshot('personal',prior['id'])['result']=='# 旧成果\n需要解释训练数据。'


def test_discussion_reads_current_plus_five_selected_research_with_sources(web):
    c,m=web
    items=[]
    for i in range(6):
        item=post(c,'/items',{'itemType':'research','title':f'研究{i}'})
        run=post(c,'/runs',{'itemId':item['id'],'engine':'codex','instruction':'受控引用验证'},202)
        c.app.state.database_manager.postgres().execute("UPDATE workbench.t_lifeweave_run SET state='succeeded',result=%s,finished_at=now() WHERE id=%s",(f'# 全文{i}\n独特证据{i}',run['id']))
        items.append(item['id'])
    cid=post(c,'/conversations',{'requestId':'cross-research','itemId':items[0]})['id']
    m.decision=decision('discuss');m.decision['itemId']=items[0]
    row=turn(c,cid,'比较这些研究','discuss',researchItemIds=items[1:])
    assert row['status']=='completed' and row['runId'] is None
    loaded=m.contexts[-1]['researchOutputs']
    assert len(loaded)==6 and all(f'独特证据{i}' in loaded[i]['content'] for i in range(6))
    assert len([s for s in row['sources'] if s.get('kind')=='research'])==6
    assert row['inputContext']['researchItemIds']==items[1:]
    c.app.state.database_manager.postgres().execute("UPDATE workbench.t_lifeweave_run SET result=repeat('大',70000) WHERE item_id=ANY(%s)",(items,))
    large=turn(c,cid,'比较长报告','discuss',researchItemIds=items[1:])
    assert large['status']=='completed'
    excerpts=m.contexts[-1]['researchOutputs']
    assert len(excerpts)==6 and all(x['content'] and x['excerpt'] for x in excerpts)
    assert sum(len(x['content']) for x in excerpts)==120000
    assert c.post(f'/api/lifeweave/personal/conversations/{cid}/turns',json={'body':'太多','requestId':'too-many','researchItemIds':items}).status_code==422
    assert c.post(f'/api/lifeweave/personal/conversations/{cid}/turns',json={'body':'不存在','requestId':'missing','researchItemIds':['forged']}).status_code==404


def test_cancel_and_recovery_do_not_replay_business_actions(web):
    c,m=web
    cid=post(c,'/conversations',{'requestId':'cancel'})['id']
    m.decision='wait'
    row=post(c,f'/conversations/{cid}/turns',{'body':'等待响应','requestId':'waiting'},202)
    cancelled=post(c,f'/conversations/{cid}/turns/{row["id"]}/cancel',{},200)
    assert cancelled['status']=='cancelled'
    assert turn(c,cid,'等待响应',request_id='waiting')['status']=='cancelled'
    m.decision='error'
    failed=turn(c,cid,'服务出错')
    assert failed['status']=='failed' and not failed['receipts']
    repo=c.app.state.conversations.repository
    from src.lifeweave.conversation_models import TurnCreate
    interrupted=repo.enqueue('personal',cid,TurnCreate(body='未处理原话',requestId='interrupted'))
    c.app.state.conversations.recover()
    assert repo.turn('personal',cid,interrupted['id'])['status']=='failed'
    assert repo.turn('personal',cid,interrupted['id'])['receipts']==[]


def test_new_topic_and_stale_interpretation_do_not_change_existing_goal(web):
    from src.lifeweave.conversation_models import TurnCreate
    from src.lifeweave.repository import ConcurrentUpdateError
    c,m=web
    original=post(c,'/items',{'itemType':'research','title':'原目标','initialContext':{'goal':'旧背景'}})
    cid=post(c,'/conversations',{'requestId':'topic-switch','itemId':original['id']})['id']
    m.decision=decision('discuss')
    different=turn(c,cid,'现在换一个主题，讨论周末出游，不执行')
    assert different['status']=='completed' and different['itemId']!=original['id']
    service=c.app.state.conversations
    row=service.repository.enqueue('personal',cid,TurnCreate(body='依据旧背景执行',requestId='stale',itemId=original['id']))
    context=service.prepare('personal',cid,row)
    service.db.execute("UPDATE workbench.lifeweave_turn SET status='processing' WHERE id=%s",(row['id'],))
    current=c.get('/api/lifeweave/personal/items/'+original['id']).json()['context']
    proposal=post(c,'/items/'+original['id']+'/context/proposals',{'baseVersion':current['version'],'title':'新背景','proposedContent':{'goal':'改为新背景'}})
    post(c,'/context-proposals/'+proposal['id']+'/accept',{'version':current['version']},200)
    value=decision('execute');value['itemId']=original['id']
    with pytest.raises(ConcurrentUpdateError,match='背景已更新'):
        service.apply('personal',cid,row['id'],Decision.model_validate(value),context)
    assert service.runtime.list_runs('personal',item_id=original['id'],limit=1,offset=0)[1]==0

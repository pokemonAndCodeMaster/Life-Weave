import os, sys, json, tempfile, importlib.util, hashlib
from pathlib import Path
from copy import deepcopy
sys.path.insert(0, '/home/yyh/project/lifeweave')
os.environ['LIFEWEAVE_TEST_DB']='1'
spec=importlib.util.spec_from_file_location('live_fixture','/home/yyh/project/lifeweave/tests/test_live_database.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
evidence={'candidate':'4c58afd1e29262c18348ac4fe0751e5cd3f69abe','checks':[], 'requests':[]}
class Factory:
    def __init__(self,root): self.root=Path(root)
    def mktemp(self,name):
        p=self.root/name; p.mkdir(); return p

def check(name, value, detail=None):
    evidence['checks'].append({'name':name,'pass':bool(value),'detail':detail})
    assert value, name

with tempfile.TemporaryDirectory(prefix='lifeweave-independent-') as root:
    gen=module.client.__wrapped__(Factory(root)); client=next(gen)
    try:
        base='/api/lifeweave/team'
        def request(method,path,body=None,status=200,headers=None):
            response=client.request(method,base+path,json=body,headers=headers)
            evidence['requests'].append({'method':method,'path':path,'status':response.status_code})
            assert response.status_code==status, (method,path,response.status_code,response.text)
            return response.json()
        def post(path,body,status=200,headers=None):return request('POST',path,body,status,headers)
        def get(path):return request('GET',path)
        runtime=client.app.state.lifeweave_runtime_service
        machine=post('/machines/register',{'name':'independent provenance recheck','capacity':1,'engines':['codex'],'runtimes':['native']},201,{'X-LifeWeave-Registration-Token':runtime.registration_tokens['team']})
        auth={'X-LifeWeave-Worker-Token':machine['workerToken']}
        method_root=Path(root)/'methods'; method=method_root/'evacuation'; method.mkdir(parents=True)
        (method/'SKILL.md').write_text('---\nname: 疏散核查\ndescription: 社区疏散路线核查\n---\n阅读 references/check.md 后核对出口。')
        (method/'references').mkdir(); support=method/'references/check.md';support.write_text('原方法依据：核对两处出口')
        catalog=post('/methods/roots',{'root':str(method_root)})
        mid=catalog['items'][0]['id']
        draft=post('/library/revisions',{'path':'社区疏散.md','content':'# 社区疏散\n原材料：北门晚间关闭。','baseVersion':'new','reason':'隔离复核材料'},201)
        post('/library/revisions/'+draft['id']+'/decision',{'accept':True})
        item=post('/items',{'itemType':'other','title':'社区疏散路线核查','payload':{'goal':'核对社区夜间疏散路线'}},201)
        feedback_path='/items/'+item['id']+'/feedback'
        first=post(feedback_path,{'body':'先核对夜间北门状态','requestId':'independent-initial'},201)
        recommend=get('/items/'+item['id']+'/input-recommendations')
        check('真实推荐包含方法与知识',recommend['suggested']=={'methodId':mid,'knowledgeRefs':['local:社区疏散.md']},recommend['suggested'])
        run=post('/runs',{'itemId':item['id'],'instruction':'按已知材料讨论社区疏散路线','engine':'codex','machineId':machine['id'],**recommend['suggested']},202)
        rid=run['id']; fixed=deepcopy(run['environmentSnapshot']); old=deepcopy(runtime.get_run_snapshot('team',rid))
        evidence['initial']={'runId':rid,'feedbackId':first['id'],'fixed':fixed,'inputVersions':[(x['target'],x['version']) for x in old['capability_snapshot']]}
        check('固定反馈与真实选用',fixed['feedbackSnapshot'][0]['id']==first['id'] and fixed['selectedInputs']==recommend['suggested'])
        claim=post('/worker/'+machine['id']+'/claim',{'leaseSeconds':300},headers=auth)
        check('领取包含完整冻结材料与提示',claim['id']==rid and claim['capability_snapshot']==old['capability_snapshot'] and claim['prompt_snapshot']==old['prompt_snapshot'])
        report_path='/worker/'+machine['id']+'/runs/'+rid+'/report'
        badbody={'leaseId':claim['lease_id'],'outcome':'running','environment':{'feedbackSnapshot':[]}}
        post(report_path,badbody,403,{'X-LifeWeave-Worker-Token':'wrong-token'})
        post(report_path,{**badbody,'leaseId':'wrong-lease'},403,auth)
        post(report_path,{**badbody,'promptSnapshot':'forged input'},422,auth)
        check('无效凭证租约额外输入均未写入',runtime.get_run_snapshot('team',rid)['environment_snapshot']==fixed)
        protected=['feedbackSnapshot','inputRecommendations','selectedInputs','requestedRuntime','requestedImage','retriedFrom','contextSynced']
        spoof={k:{'forged':True} for k in protected}
        running=post(report_path,{'leaseId':claim['lease_id'],'outcome':'running','sessionId':'independent-session','environment':{**spoof,'runtime':'native','actualDirectory':'/isolated/evacuation','identity':'independent-env','cliVersion':'test-observed-v1'}},headers=auth)
        check('运行报告不能改写或注入固定字段',all(running['environmentSnapshot'].get(k)==fixed.get(k) for k in protected))
        check('运行详情实际目录消费保留环境',get('/runs/'+rid)['directory']=='/isolated/evacuation')
        ended=post(report_path,{'leaseId':claim['lease_id'],'outcome':'succeeded','exitCode':0,'result':'已核对本次协议结果，不是 AI 执行证明','environment':{**spoof,'exitObserved':True}},headers=auth)
        check('结束部分环境保留原实际环境',all(ended['environmentSnapshot'].get(k)==v for k,v in {'runtime':'native','actualDirectory':'/isolated/evacuation','identity':'independent-env','cliVersion':'test-observed-v1','exitObserved':True}.items()),ended['environmentSnapshot'])
        check('结束后固定字段及列表仍可读取',all(ended['environmentSnapshot'].get(k)==fixed.get(k) for k in protected) and next(r for r in get('/runs?itemId='+item['id'])['items'] if r['id']==rid)['environmentSnapshot']==ended['environmentSnapshot'])
        post(report_path,{'leaseId':claim['lease_id'],'outcome':'failed','environment':{'feedbackSnapshot':[]}},403,auth)
        check('跨空间不可读取',client.get('/api/lifeweave/personal/runs/'+rid).status_code==404)
        second=post(feedback_path,{'body':'第二轮还要检查轮椅通行','runId':rid,'requestId':'independent-after'},201)
        original_doc=get('/library/document?path=社区疏散.md')
        revision=post('/library/revisions',{'path':'社区疏散.md','content':'# 社区疏散\n新材料：北门全天开放。','baseVersion':original_doc['version'],'reason':'验证重试保留旧材料'},201)
        post('/library/revisions/'+revision['id']+'/decision',{'accept':True})
        support.write_text('新方法依据：只核对一处出口')
        proposal=post('/items/'+item['id']+'/context/proposals',{'baseVersion':1,'title':'补充新目标','proposedContent':{'goal':'新版目标检查轮椅通行'},'provenance':[]},201)
        post('/context-proposals/'+proposal['id']+'/accept',{'version':1})
        evidence['retries']=[]
        for sync in (False,True):
            retry=post('/runs/'+rid+'/retry',{'syncContext':sync,'machineId':machine['id']},202)
            retry_id=retry['id']; retry_fixed=deepcopy(retry['environmentSnapshot'])
            claim2=post('/worker/'+machine['id']+'/claim',{'leaseSeconds':300},headers=auth)
            check(f'重试 sync={sync} 实际领取原材料',claim2['id']==retry_id and claim2['capability_snapshot']==old['capability_snapshot'])
            check(f'重试 sync={sync} 新反馈进入实际提示',second['body'] in claim2['prompt_snapshot'] and [x['id'] for x in retry_fixed['feedbackSnapshot']]==[first['id'],second['id']])
            check(f'重试 sync={sync} 保留推荐选用并正确选择背景',retry_fixed['selectedInputs']==fixed['selectedInputs'] and retry_fixed['inputRecommendations']==fixed['inputRecommendations'] and (claim2['context_snapshot']==old['context_snapshot']) == (not sync))
            path='/worker/'+machine['id']+'/runs/'+retry_id+'/report'
            post(path,{'leaseId':claim2['lease_id'],'outcome':'running','environment':{**spoof,'actualDirectory':'/isolated/retry','identity':'retry-env'}},headers=auth)
            failed=post(path,{'leaseId':claim2['lease_id'],'outcome':'failed','exitCode':1,'error':'协议复核主动结束','environment':{}},headers=auth)
            check(f'重试 sync={sync} 失败空环境保留依据',all(failed['environmentSnapshot'].get(k)==retry_fixed.get(k) for k in protected) and failed['environmentSnapshot']['identity']=='retry-env')
            evidence['retries'].append({'syncContext':sync,'id':retry_id,'feedbackIds':[x['id'] for x in retry_fixed['feedbackSnapshot']],'promptSha256':hashlib.sha256(claim2['prompt_snapshot'].encode()).hexdigest(),'materialVersions':[(x['target'],x['version']) for x in claim2['capability_snapshot']]})
        now=runtime.get_run_snapshot('team',rid)
        check('新反馈新材料重试后旧运行输入原样保存',all(now[k]==old[k] for k in ('prompt_snapshot','item_snapshot','context_snapshot','capability_snapshot')) and all(now['environment_snapshot'].get(k)==fixed.get(k) for k in protected))
        continuation=get('/items/'+item['id']+'/continuation')
        check('接续消费者仍可读取三轮运行',len(continuation['runs'])==3)
        evidence['result']='pass'
    except Exception as exc:
        evidence['result']='fail'; evidence['error']=repr(exc)
        raise
    finally:
        gen.close()
        evidence['fixture_cleanup']='completed'
        Path('/tmp/lifeweave-independent-worker-recheck.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str))
print(json.dumps({'result':evidence['result'],'checks':len(evidence['checks']),'requests':len(evidence['requests']),'evidence':'/tmp/lifeweave-independent-worker-recheck.json'},ensure_ascii=False))

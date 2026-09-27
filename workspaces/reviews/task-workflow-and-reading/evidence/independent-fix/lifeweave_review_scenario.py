import sys, subprocess
from pathlib import Path
sys.path.insert(0, '/home/yyh/project/lifeweave/tests')
from test_live_database import dedicated_client, post


def test_review_scenario(dedicated_client, tmp_path):
    c=dedicated_client
    item=post(c,'/items',{'itemType':'fix','title':'Independent ordering review'})
    base=f'/api/lifeweave/personal/items/{item["id"]}'
    repo=tmp_path/'repo';repo.mkdir()
    subprocess.run(['git','-C',str(repo),'init','-q'],check=True)
    (repo/'README.md').write_text('review fixture')
    subprocess.run(['git','-C',str(repo),'add','README.md'],check=True)
    subprocess.run(['git','-C',str(repo),'-c','user.name=Review','-c','user.email=review@example.invalid','commit','-qm','baseline'],check=True)
    def step(acceptance):
        return {'id':'build','title':'构建固定结果','state':'planned','dependsOn':[],
          'expectedOutputs':[{'id':'proof','title':'固定核验','kind':'validation','required':True}],
          'acceptance':acceptance}
    def plan(version,acceptance,reason=None):
        data={'version':version,'title':'交付顺序','provider':'development','nodes':[step(acceptance)]}
        if reason:data['revisionReason']=reason
        r=c.put(base+'/work-plan',json=data);assert r.status_code==200,r.text
        return r.json()
    p1=plan(item['version'],'核对 A 范围')
    v1=p1['plan']['version']
    def start(request,version):
        return post(c,f'/items/{item["id"]}/external-development/sessions',
          {'requestId':request,'repositoryPath':str(repo),'summary':'实际测试会话','stepId':'build','planVersion':version})['sessionId']
    s1=start('start-v1',v1)
    def output(title):
        r=post(c,f'/items/{item["id"]}/manual-results',
          {'title':title,'content':title+' 的固定正文','verification':'隔离数据库读回','environment':'独立临时库','resultKind':'validation'})
        return {'expectationId':'proof','outputId':'artifact:'+r['artifactId'],'version':r['version']}
    def report(request,session,version,outcome,delivery=None):
        body={'requestId':request,'planVersion':version,'stepId':'build','sessionId':session,
          'outcome':outcome,'summary':request,'deliverables':[delivery] if delivery else [],
          'checks':[{'label':'隔离读回','result':'passed','evidence':'固定结果'}] if outcome=='succeeded' else []}
        r=c.post(base+'/work-plan/steps/build/reports',json=body);assert r.status_code==201,r.text
        return r.json()
    def current():
        v=c.get(base+'/work-view').json();n=v['plan']['nodes'][0]
        return {'version':v['plan']['version'],'state':n['state'],'ids':n['outputIds'],
          'attempts':[(a['outcome'],a['applied'],a['outputIds']) for a in n['attempts']],
          'all_ids':[o['id'] for o in v['outputs']]}
    report('initial-failure',s1,v1,'failed')
    report('retry-running',s1,v1,'running')
    a=output('A first')
    assert report('success-A',s1,v1,'succeeded',a)['applied']
    report('post-success-failure',s1,v1,'failed')
    assert current()['ids'][0]==a['outputId']
    report('retry-again',s1,v1,'running')
    b=output('B second')
    assert report('success-B',s1,v1,'succeeded',b)['applied']
    rejected=report('rejected-after-B',s1,v1,'succeeded',{'expectationId':'wrong','outputId':a['outputId'],'version':a['version']})
    assert rejected['applied'] is False
    after_b=current();assert after_b['ids'][:2]==[b['outputId'],a['outputId']],after_b
    p2=plan(c.get(base+'/work-view').json()['itemVersion'],'核对 B 新范围','增加新环境')
    v2=p2['plan']['version'];s2=start('start-v2',v2)
    c_ref=output('C after revision')
    assert report('success-C',s2,v2,'succeeded',c_ref)['applied']
    late=report('late-v1-after-C',s1,v1,'succeeded',a)
    assert late['applied'] is False and any('计划版本已变更' in issue for issue in late['issues']),late
    final=current()
    assert final['ids'][0]==c_ref['outputId'],final
    assert a['outputId'] in final['all_ids'] and b['outputId'] in final['all_ids'],final
    print('OBSERVED',{'item':item['id'],'v1':v1,'v2':v2,'A':a['outputId'],'B':b['outputId'],'C':c_ref['outputId'],'afterB':after_b,'final':final,'lateIssues':late['issues']})

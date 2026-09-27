import sys,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,'/home/yyh/project/lifeweave/tests')
from test_live_database import database_client
class TempFactory:
 def mktemp(self,name): return Path(tempfile.mkdtemp(prefix='lw-independent-'+name+'-'))
def assert_status(r,expected=201):
 assert r.status_code==expected,(r.status_code,r.text)
 return r.json()
g=database_client(TempFactory())
try:
 c=next(g)
 root=Path(tempfile.mkdtemp(prefix='lw-independent-repo-'))
 subprocess.run(['git','-C',str(root),'init','-q'],check=True)
 (root/'README.md').write_text('# test\n')
 subprocess.run(['git','-C',str(root),'add','README.md'],check=True)
 subprocess.run(['git','-C',str(root),'-c','user.name=Independent','-c','user.email=independent@example.invalid','commit','-qm','baseline'],check=True)
 base='/api/lifeweave/personal'
 item=assert_status(c.post(base+'/items',json={'itemType':'fix','title':'独立反馈复核'}))
 iid=item['id']; uri=base+'/items/'+iid
 step={'id':'verify','title':'核验交付','expectedOutputs':[{'id':'evidence','title':'验证记录','kind':'validation','required':True}],'acceptance':'核对初版结果'}
 saved=assert_status(c.put(uri+'/work-plan',json={'version':item['version'],'title':'计划 A','provider':'development','nodes':[step]}),200)
 v1=saved['plan']['version']
 session=assert_status(c.post(uri+'/external-development/sessions',json={'requestId':'start-1','repositoryPath':str(root),'summary':'本机第一轮','stepId':'verify','planVersion':v1}))['sessionId']
 r1=assert_status(c.post(uri+'/work-plan/steps/verify/reports',json={'requestId':'failed-1','planVersion':v1,'stepId':'verify','sessionId':session,'outcome':'failed','summary':'检查失败：缺少对应内容','checks':[{'label':'内容核对','result':'failed','evidence':'发现缺口'}]}))
 assert r1['applied'] and c.get(uri+'/work-view').json()['plan']['nodes'][0]['state']=='failed'
 feedback=assert_status(c.post(uri+'/feedback',json={'requestId':'feedback-1','body':'步骤 verify 的产物需要增加新环境检查','anchor':'步骤：核验交付 [verify]'}))
 continuation=c.get(uri+'/continuation').json()
 assert feedback['id'] in [x['id'] for x in continuation['feedback']]
 view=c.get(uri+'/work-view').json()
 revised=assert_status(c.put(uri+'/work-plan',json={'version':view['itemVersion'],'title':'计划 B','provider':'development','revisionReason':'依据反馈增加新环境检查','nodes':[{**step,'acceptance':'核对初版结果及新环境检查'}]}),200)
 v2=revised['plan']['version'];assert v2==v1+1
 result=assert_status(c.post(uri+'/manual-results',json={'title':'新验证','content':'新环境检查通过','verification':'独立数据库读回','environment':'独立测试库','resultKind':'validation'}))
 delivery={'expectationId':'evidence','outputId':'artifact:'+result['artifactId'],'version':result['version']}
 stale=assert_status(c.post(uri+'/work-plan/steps/verify/reports',json={'requestId':'old-late','planVersion':v1,'stepId':'verify','sessionId':session,'outcome':'succeeded','summary':'迟到的旧版报告','deliverables':[delivery],'checks':[{'label':'检查','result':'passed','evidence':'旧证据'}]}))
 assert not stale['applied'] and '计划版本已变更' in ';'.join(stale['issues'])
 assert c.get(uri+'/work-view').json()['plan']['nodes'][0]['state']=='planned'
 session2=assert_status(c.post(uri+'/external-development/sessions',json={'requestId':'start-2','repositoryPath':str(root),'summary':'本机重试','stepId':'verify','planVersion':v2}))['sessionId']
 valid=assert_status(c.post(uri+'/work-plan/steps/verify/reports',json={'requestId':'valid-2','planVersion':v2,'stepId':'verify','sessionId':session2,'outcome':'succeeded','summary':'新环境检查通过','deliverables':[delivery],'checks':[{'label':'新环境','result':'passed','evidence':'独立数据库读回'}]}))
 final=c.get(uri+'/work-view').json()['plan']['nodes'][0]
 assert valid['applied'] and final['state']=='succeeded' and len(final['attempts'])==3
 result2=assert_status(c.post(uri+'/manual-results',json={'title':'第二次验证','content':'修订后第二份验证','verification':'独立数据库读回','environment':'独立测试库','resultKind':'validation'}))
 delivery2={'expectationId':'evidence','outputId':'artifact:'+result2['artifactId'],'version':result2['version']}
 second=assert_status(c.post(uri+'/work-plan/steps/verify/reports',json={'requestId':'valid-3','planVersion':v2,'stepId':'verify','sessionId':session2,'outcome':'succeeded','summary':'第二份验证替换上一份','deliverables':[delivery2],'checks':[{'label':'新环境','result':'passed','evidence':'独立数据库读回'}]}))
 latest=c.get(uri+'/work-view').json()['plan']['nodes'][0]
 assert second['applied'] and latest['state']=='succeeded' and len(latest['outputIds'])==2
 print('item',iid,'feedback',feedback['id'],'plan',v1,'->',v2,'failed report applied',r1['applied'],'late old report applied',stale['applied'],'new reports applied',valid['applied'],second['applied'],'attempts',len(latest['attempts']),'outputIds',latest['outputIds'],'last report output',delivery2['outputId'])
finally:
 try: next(g)
 except StopIteration: pass

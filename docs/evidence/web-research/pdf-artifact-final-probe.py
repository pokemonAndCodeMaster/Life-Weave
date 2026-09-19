"""Independent deterministic delivery probe; owns only random test DB and port 8015."""
import asyncio, base64, hashlib, json, os, shutil, subprocess, sys, tempfile, threading, time, traceback
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
EVIDENCE = Path(__file__).parent
PREFIX = 'pdf-artifact-final-'
data = {'candidate': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'checks': [], 'runs': []}
def check(name, actual, detail=None):
    data['checks'].append({'name':name,'pass':bool(actual),'detail':detail})
    print(name, 'PASS' if actual else 'FAIL', flush=True)
def dump(name, value):
    (EVIDENCE/(PREFIX+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
def digest(value): return hashlib.sha256(value).hexdigest()

temp=Path(tempfile.mkdtemp(prefix=PREFIX))
dbname='test_pdf_final_'+uuid4().hex[:12]
data.update(database=dbname, temporary_root=str(temp), port=8015)
os.environ.update(LIFEWEAVE_DB_HOST=str(ROOT/'.runtime/postgres/socket'),LIFEWEAVE_DB_NAME=dbname,LIFEWEAVE_DB_PORT='55440',LIFEWEAVE_DB_USER='lifeweave',LIFEWEAVE_LOCAL_WORKER='0',LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT=str(temp/'knowledge/personal'),LIFEWEAVE_TEAM_KNOWLEDGE_ROOT=str(temp/'knowledge/team'))
# Do not copy any real executor credentials, even though no real model is invoked.
os.environ['CODEX_HOME']=str(temp/'empty-codex')
(temp/'empty-codex').mkdir()
(temp/'config').mkdir()
shutil.copy(ROOT/'config/base.yaml',temp/'config/base.yaml')
(temp/'web').mkdir()
(temp/'web/dist').symlink_to(ROOT/'web/dist',target_is_directory=True)
(temp/'web/public').symlink_to(ROOT/'web/public',target_is_directory=True)
import psycopg, httpx, uvicorn
from psycopg import sql
admin=psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname='postgres',autocommit=True)
admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
server=None
thread=None
try:
    from src.cli import migrate
    migrate()
    import src.api.app as api_module
    api_module.ROOT=temp
    app=api_module.create_app()
    runtime=app.state.lifeweave_runtime_service
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8015,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started: break
        time.sleep(.1)
    assert server.started
    from src.agent_runtime.executor import ExecutorResult,ExecutorHealth
    from src.lifeweave_runtime.worker import LifeWeaveWorker,ServiceWorkerClient,HttpWorkerClient
    session=httpx.Client(base_url='http://127.0.0.1:8015',trust_env=False)
    base='/api/lifeweave/personal'
    def get(path):
        r=session.get(path);r.raise_for_status();return r.json()
    def post(path,body,headers=None):
        r=session.post(path,json=body,headers=headers);r.raise_for_status();return r.json()
    def register(name):
        return post(base+'/machines/register',{'name':name,'capacity':1,'engines':['codex'],'runtimes':['native']},{'X-LifeWeave-Registration-Token':runtime.registration_tokens['personal']})
    event={'event_type':'pdf.extracted','source':'deterministic-review','channel':'stdout','summary':'PDF 公式\0提取完成','payload':{'depth':{'values':['x\0y',r'\u0000','␀'],'collision':{'a\0b':1,'a␀b':2}},'literal':r'\0'}}
    report='# 独立 PDF 阅读夹具\n\n公式项 A\0B 保持证据。\n\n[提取来源](source.md)\n\n字面转义 `\\u0000` 保留。'
    raw='EXECUTOR RAW HEADER\n'+report+'\nRAW FOOTER\0'
    payload={'report':report,'nested':{'source':'pdf\0reader','literal':r'\u0000','map':{'\0':10,'␀':20}}}
    class Fixture:
        def __init__(self,nul=True): self.nul=nul
        def health(self): return ExecutorHealth('codex',True,'independent-deterministic-fixture','v1')
        async def run(self,request,on_event,on_process):
            (request.worktree/'source.md').write_text('# 固定来源\n\nThis is the independently created source.\n')
            await on_event(event if self.nul else {**event,'summary':'无控制字符','payload':{'literal':r'\u0000','text':'正常中文'}})
            return ExecutorResult('codex',0,'fixture-'+request.run_id,raw if self.nul else '# 普通结果\n\n中文与字面 \\u0000 不变。',payload if self.nul else {'report':'# 普通结果\n\n中文与字面 \\u0000 不变。'})
    for transport,nul in [('service',True),('http',True),('http-control',False)]:
        machine=register(transport)
        item=post(base+'/items',{'itemType':'research','title':'独立 PDF 交付复核 '+transport,'payload':{'goal':'读取固定 PDF 提取文本并保留原始证据'}})
        run=post(base+'/runs',{'itemId':item['id'],'instruction':'运行独立无模型夹具','engine':'codex','machineId':machine['id']})
        client=ServiceWorkerClient(runtime,'personal',machine['id'],machine['workerToken']) if transport=='service' else HttpWorkerClient(str(session.base_url),'personal',machine['id'],machine['workerToken'])
        worker=LifeWeaveWorker(client=client,executors={'codex':Fixture(nul)},runtime_root=temp/'.runtime/executions',machine_id=machine['id'])
        check(transport+' full worker consumed',asyncio.run(worker.execute_once()))
        saved=get(base+'/runs/'+run['id']);output=get(base+'/items/'+item['id']+'/research-output')['current']
        events=get(base+'/runs/'+run['id']+'/events')['items']
        check(transport+' succeeded',saved['state']=='succeeded',saved['state'])
        check(transport+' input provenance',saved['environmentSnapshot']['selectedInputs']==run['environmentSnapshot']['selectedInputs'])
        if nul:
            stored=next(e for e in events if e['eventType']=='pdf.extracted')
            original=json.loads(base64.b64decode(stored['payload']['_lifeweaveTextStorage']['originalJsonBase64']))
            check(transport+' lossless event',original==event and stored['summary']=='PDF 公式␀提取完成')
            check(transport+' collision and literals',stored['payload']['depth']['collision']['entries']==[['a␀b',1],['a␀b',2]] and stored['payload']['depth']['values'][1]==r'\u0000')
            original_report=json.loads(base64.b64decode(saved['environmentSnapshot']['_lifeweaveTextStorage']['originalJsonBase64']))
            check(transport+' lossless final JSON',original_report['result']==raw and original_report['result_payload']==payload)
            check(transport+' readable projection',output['content']==report.replace('\0','␀') and 'NUL' in output['storageNote'])
        else:
            check(transport+' no unrelated note',output['storageNote'] is None and output['rawDownloadUrl'] is None)
        result=session.get(base+'/runs/'+run['id']+'/artifacts/result')
        wanted=(raw if nul else '# 普通结果\n\n中文与字面 \\u0000 不变。').encode()
        version='sha256:'+digest(result.content)
        check(transport+' raw bytes and headers',result.content==wanted and result.headers['x-artifact-version']==version and result.headers['etag']=='"'+version+'"')
        readable=session.get(output['downloadUrl'])
        check(transport+' readable bytes and version',readable.content==output['content'].encode() and output['version']==digest(readable.content) and readable.headers['etag']=='"'+output['version']+'"')
        (EVIDENCE/(PREFIX+transport+'-raw.txt')).write_bytes(result.content)
        data['runs'].append({'transport':transport,'itemId':item['id'],'runId':run['id'],'output':output,'artifactHeaders':dict(result.headers)})
        dump(transport+'-run',{'run':saved,'events':events,'output':output})
    # Full network boundary probes: wrong lease cannot store NUL event or result;
    # worker-controlled environment cannot replace frozen input provenance.
    machine=register('boundary')
    auth={'X-LifeWeave-Worker-Token':machine['workerToken']}
    item=post(base+'/items',{'itemType':'research','title':'边界及旧存储元数据'})
    run=post(base+'/runs',{'itemId':item['id'],'instruction':'隔离边界','engine':'codex','machineId':machine['id']})
    prefix=base+'/worker/'+machine['id']
    claimed=post(prefix+'/claim',{'leaseSeconds':60},auth)
    for endpoint,body in [('events',{'leaseId':'obsolete','eventType':'pdf.test','summary':'invalid\0','payload':{'x':'y\0'}}),('report',{'leaseId':'obsolete','outcome':'succeeded','result':'invalid\0','exitCode':0})]:
        response=session.post(prefix+'/runs/'+run['id']+'/'+endpoint,json=body,headers=auth)
        check('invalid lease '+endpoint,response.status_code>=400,{'status':response.status_code,'body':response.text})
    immutable=run['environmentSnapshot']
    post(prefix+'/runs/'+run['id']+'/report',{'leaseId':claimed['lease_id'],'outcome':'running','environment':{'oldField':'older\0metadata','selectedInputs':{'forged':True},'researchSupport':{'forged':True}}},auth)
    clean='# clean later result\n\nDifferent actual final result.'
    post(prefix+'/runs/'+run['id']+'/report',{'leaseId':claimed['lease_id'],'outcome':'succeeded','exitCode':0,'result':clean,'resultPayload':{'report':clean},'artifacts':[{'kind':'executor-result','version':'sha256:'+digest(clean.encode())}],'environment':{'selectedInputs':{'forgedAgain':True}}},auth)
    saved=get(base+'/runs/'+run['id']);output=get(base+'/items/'+item['id']+'/research-output')['current']
    check('old metadata cannot restore unrelated result',session.get(base+'/runs/'+run['id']+'/artifacts/result').content==clean.encode() and output['storageNote'] is None)
    check('forged input provenance protected',all(saved['environmentSnapshot'].get(key)==immutable.get(key) for key in ['selectedInputs','researchSupport','feedbackSnapshot','inputRecommendations']))
    for suffix in ['/runs/'+run['id'],'/runs/'+run['id']+'/artifacts/result','/items/'+item['id']+'/research-output']:
        response=session.get('/api/lifeweave/team'+suffix)
        check('cross workspace '+suffix,response.status_code==404,response.status_code)
    cross=session.post(prefix.replace('/personal/','/team/')+'/runs/'+run['id']+'/events',headers=auth,json={'leaseId':claimed['lease_id'],'eventType':'forged','summary':'x\0','payload':{}})
    check('cross workspace worker token',cross.status_code>=400,cross.status_code)
    check('invalid lease did not append event',not any(e['eventType']=='pdf.test' for e in get(base+'/runs/'+run['id']+'/events')['items']))
    dump('boundary',{'run':saved,'output':output})
    # Browser is a real Chromium process; all knowledge writes stay in our root.
    from playwright.sync_api import sync_playwright
    chosen=data['runs'][1]
    browser_errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True, executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome')
        context=browser.new_context(viewport={'width':1440,'height':1100},accept_downloads=True)
        context.tracing.start(screenshots=True,snapshots=True,sources=True)
        page=context.new_page()
        page.on('pageerror',lambda error:browser_errors.append(str(error)))
        page.goto(str(session.base_url).rstrip('/')+'/lifeweave/personal/items/'+chosen['itemId']+'/outputs')
        page.get_by_role('link',name='下载原始执行文本').wait_for()
        region=page.get_by_role('region',name='研究成果')
        check('browser output NUL note', 'NUL' in region.inner_text())
        with page.expect_download() as pending:
            page.get_by_role('link',name='下载原始执行文本').click()
        downloaded=pending.value
        downloaded.save_as(str(EVIDENCE/(PREFIX+'browser-raw.txt')))
        check('browser raw download exact',Path(downloaded.path()).read_bytes()==raw.encode())
        with page.expect_download() as pending:
            page.get_by_role('button',name='下载正文',exact=True).click()
        check('browser readable download exact',Path(pending.value.path()).read_bytes()==chosen['output']['content'].encode())
        page.screenshot(path=str(EVIDENCE/(PREFIX+'output.png')),full_page=True)
        page.get_by_role('button',name='从当前成果提出知识修订').click()
        page.get_by_label('知识文件路径',exact=True).fill('审查/PDF字符证据.md')
        page.get_by_role('button',name='保存候选，查看差异').click()
        page.get_by_text('审查/PDF字符证据.md · 等待审阅',exact=True).click()
        review=page.get_by_role('region',name='知识候选审阅')
        review.get_by_text('阅读建议全文',exact=True).click()
        candidate=get(base+'/items/'+chosen['itemId']+'/knowledge-candidates')[0]
        check('candidate NUL warning API',any('NUL' in w for w in candidate['references']['warnings']),candidate['references'])
        check('candidate NUL warning browser','NUL' in review.inner_text(),review.inner_text())
        check('candidate source mapping and version',candidate['runId']==chosen['runId'] and candidate['runVersion']==chosen['output']['version'] and chosen['runId'] in candidate['references']['links'].get('source.md',''))
        page.screenshot(path=str(EVIDENCE/(PREFIX+'candidate.png')),full_page=True)
        page.get_by_role('button',name='接受并更新知识原文').click()
        page.get_by_role('link',name='阅读已接受知识').click()
        page.get_by_role('button',name='下载原文',exact=True).wait_for()
        doc=get(base+'/library/document?path='+__import__('urllib.parse',fromlist=['quote']).quote('审查/PDF字符证据.md'))
        body=page.locator('.lw-article').inner_text()
        check('accepted NUL warning API',any('NUL' in w for w in doc['references']['warnings']),doc['references'])
        check('accepted NUL warning browser','NUL' in body,body)
        check('accepted original file and version',doc['content']==(temp/'knowledge/personal/审查/PDF字符证据.md').read_text() and doc['version']==digest(doc['content'].encode()) and chosen['output']['version'] in doc['content'])
        check('accepted research mapping unchanged',doc['references']['links']==candidate['references']['links'])
        source=page.locator('.lw-article').get_by_role('link',name='提取来源',exact=True)
        check('accepted browser source href',chosen['runId'] in source.get_attribute('href'))
        r=session.get(source.get_attribute('href'))
        check('accepted source resolves exact fixture',r.status_code==200 and 'independently created source' in r.text)
        with page.expect_download() as pending:
            page.get_by_role('button',name='下载原文',exact=True).click()
        check('accepted download version',digest(Path(pending.value.path()).read_bytes())==doc['version'])
        page.screenshot(path=str(EVIDENCE/(PREFIX+'accepted.png')),full_page=True)
        (EVIDENCE/(PREFIX+'accepted.md')).write_text(doc['content'])
        dump('knowledge',{'candidate':candidate,'accepted':doc,'browserText':body})
        context.tracing.stop(path=str(EVIDENCE/(PREFIX+'browser-trace.zip')))
        browser.close()
    check('browser no uncaught errors',not browser_errors,browser_errors)
except Exception:
    data['exception']=traceback.format_exc()
    print(data['exception'],flush=True)
finally:
    if server: server.should_exit=True
    if thread: thread.join(timeout=15)
    if thread and thread.is_alive(): data['cleanupError']='Owned server did not stop'
    admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(dbname)))
    check('database removed',not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(dbname,)).fetchone())
    admin.close()
    shutil.rmtree(temp)
    data['temporaryRootRemoved']=not temp.exists()
    data['result']='fail' if any(not x['pass'] for x in data['checks']) else ('not_proven' if 'exception' in data else 'pass')
    dump('observations',data)
    print('OVERALL',data['result'],flush=True)

from pathlib import Path
import asyncio, base64, hashlib, json, os, shutil, tempfile, threading, time
from uuid import uuid4
import psycopg
from psycopg import sql
import httpx, uvicorn
ROOT=Path('/home/yyh/project/lifeweave')
EVIDENCE=ROOT/'docs/evidence/web-research'
TMP=Path(tempfile.mkdtemp(prefix='lifeweave-pdf-review-'))
DB='test_pdf_review_'+uuid4().hex[:12]
os.environ.update(LIFEWEAVE_DB_NAME=DB,LIFEWEAVE_LOCAL_WORKER='0',LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT=str(TMP/'personal'),LIFEWEAVE_TEAM_KNOWLEDGE_ROOT=str(TMP/'team'))
from src.api.app import create_app
from src.cli import migrate
from src.agent_runtime.executor import ExecutorResult, ExecutorHealth
from src.lifeweave_runtime.worker import LifeWeaveWorker, ServiceWorkerClient, HttpWorkerClient
admin=psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname='postgres',autocommit=True)
admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DB)))
server=None
observations={'candidate':'7ee164b','database':DB,'results':[]}
try:
    migrate();app=create_app();app.state.root=TMP;app.state.local_workers.root=TMP;app.state.task_sources.root=TMP;app.state.conversations.interpreter.root=TMP;app.state.research_outputs.root=TMP
    runtime=app.state.lifeweave_runtime_service;runtime.runtime_root=TMP/'.runtime/runs'
    class Fixture:
        name='codex'
        def __init__(self, nul): self.nul=nul
        def health(self): return ExecutorHealth(name='codex',available=True,command='deterministic-review-fixture',version='v1')
        async def run(self, request, on_event, on_process):
            self.events=[{'event_type':'pdf.extracted','source':'codex','channel':'stdout','summary':'PDF'+('\0' if self.nul else '')+'完成','payload':{'text':'A'+('\0' if self.nul else '')+'B','literal':r'\u0000','visible':'␀','nested':[{'\0key':'alpha','␀key':'beta'}] if self.nul else []}}, {'event_type':'pdf.followup','source':'codex','channel':'stdout','summary':'继续研究正常','payload':{'reached':True}}]
            for event in self.events: await on_event(event)
            self.result='# 研究成果\n\nADEn'+ ('\0' if self.nul else '') +'等式；字面量 '+r'\u0000'+'；可见符号 ␀。'
            return ExecutorResult(executor='codex',exit_code=0,session_id='review-session',final_message=self.result,final_payload={'report':self.result,'nested':{'text':self.result}})
    runtime.executors['codex']=Fixture(True)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8015,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    assert server.started
    http=httpx.Client(base_url='http://127.0.0.1:8015',trust_env=False)
    def post(path,body,headers=None):
        r=http.post('/api/lifeweave/personal'+path,json=body,headers=headers)
        assert r.is_success,(r.status_code,r.text)
        return r.json()
    for transport in ['local','http']:
      for nul in [True,False]:
        fixture=Fixture(nul)
        machine=post('/machines/register',{'name':f'review-{transport}-{nul}','capacity':1,'engines':['codex'],'runtimes':['native']},{'X-LifeWeave-Registration-Token':runtime.registration_tokens['personal']})
        item=post('/items',{'itemType':'research','title':f'独立PDF字符复核 {transport} {nul}'})
        run=post('/runs',{'itemId':item['id'],'instruction':'验证PDF输出保存与下游读取','engine':'codex','machineId':machine['id']})
        client=ServiceWorkerClient(runtime,'personal',machine['id'],machine['workerToken']) if transport=='local' else HttpWorkerClient('http://127.0.0.1:8015','personal',machine['id'],machine['workerToken'])
        worker=LifeWeaveWorker(client=client,executors={'codex':fixture},runtime_root=TMP/'.runtime/executions',machine_id=machine['id'])
        assert asyncio.run(worker.execute_once())
        saved=http.get('/api/lifeweave/personal/runs/'+run['id']).json()
        events=http.get('/api/lifeweave/personal/runs/'+run['id']+'/events').json()['items']
        event=next(e for e in events if e['eventType']=='pdf.extracted')
        assert saved['state']=='succeeded',saved.get('error')
        assert any(e['eventType']=='pdf.followup' for e in events)
        expected=fixture.result.replace('\0','␀')
        assert saved['result']==expected
        assert saved['environmentSnapshot']['selectedInputs']==run['environmentSnapshot']['selectedInputs']
        if nul:
            decoded=json.loads(base64.b64decode(event['payload']['_lifeweaveTextStorage']['originalJsonBase64']))
            assert decoded==fixture.events[0]
            report=json.loads(base64.b64decode(saved['environmentSnapshot']['_lifeweaveTextStorage']['originalJsonBase64']))
            assert report['result']==fixture.result and report['result_payload']['nested']['text']==fixture.result
            assert len(event['payload']['nested'][0]['entries'])==2
        else:
            assert '_lifeweaveTextStorage' not in event['payload']
            assert '_lifeweaveTextStorage' not in saved['environmentSnapshot']
        assert event['payload']['literal']==r'\u0000' and event['payload']['visible']=='␀'
        output=http.get('/api/lifeweave/personal/items/'+item['id']+'/research-output').json()['current']
        assert output['content']==expected
        download=http.get('/api/lifeweave/personal/runs/'+run['id']+'/artifacts/result')
        actual='sha256:'+hashlib.sha256(download.content).hexdigest()
        declared=download.headers.get('X-Artifact-Version')
        cross=http.get('/api/lifeweave/team/runs/'+run['id']).status_code
        invalid=http.post('/api/lifeweave/personal/worker/'+machine['id']+'/runs/'+run['id']+'/events',headers={'X-LifeWeave-Worker-Token':machine['workerToken']},json={'leaseId':'wrong-lease','eventType':'forbidden','source':'worker','summary':'bad\0lease','payload':{}}).status_code
        badtoken=http.post('/api/lifeweave/personal/worker/'+machine['id']+'/runs/'+run['id']+'/report',headers={'X-LifeWeave-Worker-Token':'wrong-token'},json={'leaseId':'wrong','outcome':'succeeded','result':'bad\0result'}).status_code
        assert cross==404 and invalid==403 and badtoken==403
        row={'transport':transport,'nul':nul,'runId':run['id'],'itemId':item['id'],'state':saved['state'],'events':events,'readableResult':saved['result'],'researchOutput':output,'rawJSONRecovered':True,'provenanceUnchanged':True,'crossSpaceStatus':cross,'wrongLeaseStatus':invalid,'wrongTokenStatus':badtoken,'artifactDeclared':declared,'artifactActual':actual,'artifactHashMatches':declared==actual,'storageNote':saved['environmentSnapshot'].get('_lifeweaveTextStorage',{}).get('note')}
        observations['results'].append(row)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        browser_errors=[]
        page.on('pageerror',lambda error:browser_errors.append(str(error)))
        sample=observations['results'][0]
        page.goto('http://127.0.0.1:8015/lifeweave/personal/items/'+sample['itemId']+'/outputs')
        page.get_by_role('heading',name='当前成果',exact=True).wait_for()
        page.get_by_text('ADEn␀等式',exact=False).first.wait_for()
        visible=page.locator('body').inner_text()
        page.screenshot(path=str(EVIDENCE/'pdf-storage-browser.png'),full_page=True)
        observations['browser']={'bodyText':visible,'pageErrors':browser_errors,'projectionVisible':'ADEn␀' in visible,'projectionExplanationVisible':any(term in visible for term in ['NUL','originalJsonBase64','原始 JSON','显示替换','存储投影'])}
        browser.close()
    http.close()
finally:
    if server:
        server.should_exit=True
        thread.join(timeout=15)
        observations['serverStopped']=not thread.is_alive()
    admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(DB)));admin.close()
    shutil.rmtree(TMP)
    observations['databaseDropped']=True;observations['temporaryDirectoryRemoved']=True
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    (EVIDENCE/'pdf-storage-browser-observations.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2))
print(json.dumps({'cases':len(observations['results']),'hashMatches':[r['artifactHashMatches'] for r in observations['results']],'cleaned':observations['databaseDropped']},ensure_ascii=False))

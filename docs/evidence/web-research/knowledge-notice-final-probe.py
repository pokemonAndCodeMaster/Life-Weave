"""Independent, bounded real worker/DB/browser review; no model calls or implementation edits."""
import asyncio, base64, hashlib, json, os, shutil, subprocess, sys, tempfile, threading, time, traceback
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
E=Path(__file__).parent
P='knowledge-notice-final-'
data={'candidate':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':[],'runs':[]}
def dump(name,value): (E/(P+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
def sha(b): return hashlib.sha256(b).hexdigest()
def check(name,value,detail=None):
    data['checks'].append({'name':name,'pass':bool(value),'detail':detail})
    print(name,'PASS' if value else 'FAIL',flush=True)
temp=Path(tempfile.mkdtemp(prefix=P));db='test_notice_final_'+uuid4().hex[:12]
data.update(database=db,temporaryRoot=str(temp),port=8015)
os.environ.update(LIFEWEAVE_DB_HOST=str(ROOT/'.runtime/postgres/socket'),LIFEWEAVE_DB_PORT='55440',LIFEWEAVE_DB_USER='lifeweave',LIFEWEAVE_DB_NAME=db,LIFEWEAVE_LOCAL_WORKER='0',LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT=str(temp/'knowledge/personal'),LIFEWEAVE_TEAM_KNOWLEDGE_ROOT=str(temp/'knowledge/team'),CODEX_COMMAND='/bin/false',OPENCODE_COMMAND='/bin/false')
(temp/'config').mkdir();shutil.copy(ROOT/'config/base.yaml',temp/'config/base.yaml')
(temp/'web').mkdir();(temp/'web/dist').symlink_to(ROOT/'web/dist',target_is_directory=True);(temp/'web/public').symlink_to(ROOT/'web/public',target_is_directory=True)
import psycopg,httpx,uvicorn
from psycopg import sql
admin=psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname='postgres',autocommit=True)
admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
server=None;thread=None
try:
    from src.cli import migrate
    migrate()
    import src.api.app as api
    api.ROOT=temp;app=api.create_app();runtime=app.state.lifeweave_runtime_service
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8015,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.1)
    assert server.started
    c=httpx.Client(base_url='http://127.0.0.1:8015',trust_env=False);base='/api/lifeweave/personal'
    def get(path): r=c.get(path);r.raise_for_status();return r.json()
    def post(path,body,headers=None): r=c.post(path,json=body,headers=headers);r.raise_for_status();return r.json()
    from src.agent_runtime.executor import ExecutorResult,ExecutorHealth
    from src.lifeweave_runtime.worker import LifeWeaveWorker,HttpWorkerClient
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aA7cAAAAASUVORK5CYII=')
    class Fixture:
        def __init__(self,nul):self.nul=nul;self.report=('# PDF提取样本\n\n公式 A\0B。' if nul else '# 普通知识样本\n\n正常字符、字面 `\\u0000` 和 ␀。')+'\n\n[来源文本](source.md)\n\n![图示](figure.png)\n'
        def health(self):return ExecutorHealth('codex',True,'independent-fixture','v1')
        async def run(self,request,on_event,on_process):
            (request.worktree/'source.md').write_text('# 独立来源\n\nSOURCE-'+('NUL' if self.nul else 'NORMAL'))
            (request.worktree/'figure.png').write_bytes(png)
            await on_event({'event_type':'pdf.extracted','summary':'提取 A\0B' if self.nul else '正常提取','payload':{'text':self.report}})
            self.raw='RAW HEADER\n'+self.report+'\nRAW END'+('\0' if self.nul else '')
            return ExecutorResult('codex',0,'fixture-'+request.run_id,self.raw,{'report':self.report})
    for name,nul in [('nul',True),('normal',False)]:
        machine=post(base+'/machines/register',{'name':P+name,'capacity':1,'engines':['codex'],'runtimes':['native']},{'X-LifeWeave-Registration-Token':runtime.registration_tokens['personal']})
        item=post(base+'/items',{'itemType':'research','title':'知识提示独立复核 '+name})
        run=post(base+'/runs',{'itemId':item['id'],'instruction':'受控 PDF 字符提取协议结果；不调用真实模型','engine':'codex','machineId':machine['id']})
        fixture=Fixture(nul)
        worker=LifeWeaveWorker(client=HttpWorkerClient(str(c.base_url),'personal',machine['id'],machine['workerToken']),executors={'codex':fixture},runtime_root=temp/'.runtime/executions',machine_id=machine['id'])
        check(name+' real HTTP worker consumed',asyncio.run(worker.execute_once()))
        saved=get(base+'/runs/'+run['id']);out=get(base+'/items/'+item['id']+'/research-output')['current']
        check(name+' worker succeeded',saved['state']=='succeeded')
        check(name+' readable projection',out['content']==fixture.report.replace('\0','␀'))
        raw=c.get(base+'/runs/'+run['id']+'/artifacts/result')
        check(name+' original bytes/hash/headers',raw.content==fixture.raw.encode() and raw.headers['x-artifact-version']=='sha256:'+sha(raw.content) and raw.headers['etag']=='"sha256:'+sha(raw.content)+'"',dict(raw.headers))
        (E/(P+name+'-worker-original.txt')).write_bytes(raw.content)
        row={'name':name,'itemId':item['id'],'runId':run['id'],'output':out,'raw':fixture.raw,'rawHash':sha(raw.content)}
        data['runs'].append(row)
        dump(name+'-run',{'run':saved,'output':out,'events':get(base+'/runs/'+run['id']+'/events')})
    from playwright.sync_api import sync_playwright
    browser_errors=[];http_errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome')
        ctx=browser.new_context(viewport={'width':1440,'height':1100},accept_downloads=True)
        ctx.tracing.start(screenshots=True,snapshots=True,sources=True)
        page=ctx.new_page();page.on('pageerror',lambda e:browser_errors.append(str(e)));page.on('response',lambda r:http_errors.append({'url':r.url,'status':r.status}) if r.status>=400 else None)
        def download(button,name):
            with page.expect_download() as pending:button.click()
            target=E/(P+name);pending.value.save_as(str(target));return target
        def create_candidate(row,path,merge=False):
            page.goto(str(c.base_url).rstrip('/')+'/lifeweave/personal/items/'+row['itemId']+'/outputs')
            region=page.get_by_role('region',name='研究成果')
            page.get_by_role('button',name='从当前成果提出知识修订').wait_for()
            check(row['name']+' output browser warning',('NUL' in region.inner_text())==(row['name']=='nul'))
            if row['name']=='nul':
                original=download(page.get_by_role('link',name='下载原始执行文本'),'browser-original.txt')
                check('browser original NUL bytes and hash',original.read_bytes()==row['raw'].encode() and sha(original.read_bytes())==row['rawHash'])
                readable=download(page.get_by_role('button',name='下载正文',exact=True),'readable.md')
                check('readable download content hash',readable.read_text()==row['output']['content'] and sha(readable.read_bytes())==row['output']['version'])
                page.screenshot(path=str(E/(P+'output.png')),full_page=True)
            page.get_by_role('button',name='从当前成果提出知识修订').click()
            page.get_by_label('知识文件路径',exact=True).fill(path)
            if merge:
                page.get_by_role('button',name='读取已有知识并准备合并').click()
                page.get_by_text('已读取当前知识版本；请保留需要的原文后再提交。',exact=True).wait_for()
            proposed=page.get_by_label('建议正文',exact=True).input_value()
            page.get_by_role('button',name='保存候选，查看差异').click()
            page.get_by_text(path+' · 等待审阅',exact=True).click()
            review=page.get_by_role('region',name='知识候选审阅')
            review.get_by_text('阅读建议全文',exact=True).first.click()
            candidate=next(x for x in get(base+'/items/'+row['itemId']+'/knowledge-candidates') if x['path']==path and x['status']=='draft')
            expected=proposed+'\n\n---\n来源：[研究成果]('+candidate['sourceUrl']+') · 事项 `'+row['itemId']+'` · 运行 `'+row['runId']+'` · 版本 `'+row['output']['version']+'`\n'
            check(path+' candidate exact content plus disclosed provenance',candidate['content']==expected and candidate['runVersion']==row['output']['version'])
            check(path+' before accepting file unchanged',not (temp/'knowledge/personal'/path).exists() if not merge else (temp/'knowledge/personal'/path).read_text()==data['firstDoc']['content'])
            return candidate,review
        def accept_and_export(row,path,candidate,review,label,expect_nul):
            warnings=candidate['references']['warnings'];visible=review.inner_text()
            check(label+' candidate NUL warning',any('NUL' in w for w in warnings)==expect_nul and ('NUL' in visible)==expect_nul,{'warnings':warnings,'browserText':visible})
            page.screenshot(path=str(E/(P+label+'-candidate.png')),full_page=True)
            review.get_by_role('button',name='接受并更新知识原文').first.click()
            review.get_by_text(path+' · 已接受',exact=True).wait_for()
            review.get_by_role('link',name='阅读已接受知识').first.click()
            page.get_by_role('button',name='下载阅读版',exact=True).wait_for()
            doc=get(base+'/library/document?path='+quote(path))
            article=page.locator('.lw-article');text=article.inner_text()
            check(label+' formal warnings/maps match candidate',doc['references']==candidate['references'] and all(w in text for w in warnings))
            check(label+' accepted original and hash unchanged',doc['content']==candidate['content']==(temp/'knowledge/personal'/path).read_text() and doc['version']==sha(doc['content'].encode()))
            original=download(page.get_by_role('button',name='下载原文',exact=True),label+'-accepted.md')
            check(label+' original download exact/version',original.read_bytes()==doc['content'].encode() and sha(original.read_bytes())==doc['version'])
            html=download(page.get_by_role('button',name='下载阅读版',exact=True),label+'-reading.html')
            page.screenshot(path=str(E/(P+label+'-accepted.png')),full_page=True)
            exported=ctx.new_page();exported.goto(html.as_uri())
            check(label+' downloaded HTML visible warnings',all(w in exported.locator('body').inner_text() for w in warnings) and ('NUL' in exported.locator('body').inner_text())==expect_nul)
            if label!='overlap':
                for view,key in [(page,'formal'),(exported,'downloaded HTML')]:
                    view.locator('img[alt="图示"]').scroll_into_view_if_needed()
                    view.wait_for_function('document.querySelector("img[alt=图示]").naturalWidth === 1')
                    href=view.get_by_role('link',name='来源文本',exact=True).get_attribute('href')
                    check(label+' '+key+' source and image map',row['runId'] in href and row['runId'] in view.locator('img[alt="图示"]').get_attribute('src'))
                    with view.expect_popup() as pending:
                        view.get_by_role('link',name='来源文本',exact=True).click()
                    sourcepage=pending.value
                    sourcepage.wait_for_url('**/source?**')
                    check(label+' '+key+' clicked source exact',('SOURCE-NUL' if row['name']=='nul' else 'SOURCE-NORMAL') in sourcepage.locator('body').inner_text())
                    sourcepage.close()
            else:
                check('overlap ambiguity visible in exported HTML',sum('多个来源使用相同相对引用' in w for w in warnings)==2 and all(w in exported.locator('body').inner_text() for w in warnings))
            exported.screenshot(path=str(E/(P+label+'-exported.png')),full_page=True);exported.close()
            reread=get(base+'/library/document?path='+quote(path))
            check(label+' reading and downloads never mutate original/version',reread==doc and (temp/'knowledge/personal'/path).read_bytes()==original.read_bytes())
            dump(label+'-knowledge',{'candidate':candidate,'document':doc,'formalBrowserText':text})
            return doc
        nul,normal=data['runs'];path='审查/字符投影.md'
        candidate,review=create_candidate(nul,path)
        check('NUL candidate retains original source/image map',nul['runId'] in candidate['references']['links']['source.md'] and nul['runId'] in candidate['references']['images']['figure.png'])
        data['firstDoc']=accept_and_export(nul,path,candidate,review,'nul',True)
        control,review=create_candidate(normal,'审查/普通知识.md')
        check('ordinary knowledge has zero fabricated warnings',control['references']['warnings']==[])
        accept_and_export(normal,'审查/普通知识.md',control,review,'normal',False)
        overlap,review=create_candidate(normal,path,merge=True)
        check('multiple runs keep NUL explanation and ambiguity',overlap['references']['warnings'].count(nul['output']['storageNote'])==1 and len(overlap['references']['warnings'])==3 and not overlap['references']['links'] and not overlap['references']['images'],overlap['references'])
        accept_and_export(normal,path,overlap,review,'overlap',True)
        check('no browser uncaught errors',not browser_errors,browser_errors)
        check('no HTTP errors in primary browser',not http_errors,http_errors)
        ctx.tracing.stop(path=str(E/(P+'browser-trace.zip')));browser.close()
except Exception:
    data['exception']=traceback.format_exc();print(data['exception'],flush=True)
finally:
    if server:server.should_exit=True
    if thread:thread.join(timeout=15)
    check('owned server stopped',not thread or not thread.is_alive())
    admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(db)))
    check('owned database removed',not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(db,)).fetchone())
    admin.close();shutil.rmtree(temp);check('owned temporary root removed',not temp.exists())
    data['result']='fail' if any(not x['pass'] for x in data['checks']) else 'not_proven' if 'exception' in data else 'pass'
    dump('observations',data);print('OVERALL',data['result'],flush=True)

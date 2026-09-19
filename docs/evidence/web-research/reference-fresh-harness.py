import os,sys,tempfile,threading,time,json,base64,urllib.parse,urllib.request,traceback,socket
from pathlib import Path
ROOT=Path('/home/yyh/project/lifeweave');sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
E=ROOT/'docs/evidence/web-research';OUT={};BROWSER_ERRORS=[]
from playwright.sync_api import sync_playwright
import psycopg
from psycopg import sql
from uuid import uuid4
import uvicorn
from fastapi.testclient import TestClient
from src.api.app import create_app
from src.cli import migrate
from src.lifeweave_runtime.worker import LifeWeaveWorker
from test_live_database import post
from test_research_outputs import completed_run,PNG

def save(): (E/'reference-fresh-review.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str))
def get(base,endpoint,**params):return json.load(urllib.request.urlopen(base+endpoint+('?' + urllib.parse.urlencode(params) if params else '')))
def observation(page):
 return page.locator('.lw-markdown').evaluate_all('(nodes)=>nodes.map(e=>({text:e.textContent,links:Array.from(e.querySelectorAll("a")).map(a=>({text:a.textContent,href:a.getAttribute("href")})),images:Array.from(e.querySelectorAll("img")).map(i=>({alt:i.alt,src:i.getAttribute("src"),width:i.naturalWidth,complete:i.complete})),code:Array.from(e.querySelectorAll("pre")).map(p=>p.textContent)}))')
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome')
 context=browser.new_context(viewport={'width':1400,'height':1100});page=context.new_page();page.on('pageerror',lambda e:BROWSER_ERRORS.append(str(e)))
 page.set_default_timeout(12000)
 real='http://127.0.0.1:8011';knowledge='/lifeweave/personal/knowledge?'+urllib.parse.urlencode({'source':'local','path':'研究/阳台采光因果解释.md'})
 page.goto(real+knowledge);page.get_by_role('link',name='来源记录',exact=True).wait_for();before=get(real,'/api/lifeweave/personal/library/document',sourceId='local',path='研究/阳台采光因果解释.md')
 with page.expect_popup() as pop:page.get_by_role('link',name='来源记录',exact=True).click()
 popup=pop.value;popup.wait_for_load_state();OUT['real_accepted_source']={'url':popup.url,'body':popup.locator('body').inner_text(),'version':before['version'],'references':before['references']};popup.close()
 page.screenshot(path=str(E/'reference-fresh-real-knowledge.png'),full_page=True)
 for label,name in [('下载原文','reference-fresh-real-original.md'),('下载阅读版','reference-fresh-real-reading.html')]:
  with page.expect_download() as down:page.get_by_role('button',name=label,exact=True).click()
  down.value.save_as(E/name)
 OUT['real_raw_download_unchanged']=(E/'reference-fresh-real-original.md').read_text()==before['content']
 page.goto((E/'reference-fresh-real-reading.html').as_uri());a=page.get_by_role('link',name='来源记录',exact=True);OUT['real_html_source']={'href':a.get_attribute('href'),'note':page.locator('body').inner_text()[:70]}
 with page.expect_popup() as pop:a.click()
 popup=pop.value;popup.wait_for_load_state();OUT['real_html_source']['body']=popup.locator('body').inner_text();popup.close()
 page.goto(real+'/lifeweave/personal/conversation/conversation-976d78f0c0785613fd74cd03e2726c3b');page.wait_for_timeout(600);OUT['real_reuse_text']=page.locator('body').inner_text();save()
 browser.close()

with socket.socket() as probe:probe.bind(('127.0.0.1',8014))
with tempfile.TemporaryDirectory(prefix='lifeweave-ref-review-') as tmp:
 root=Path(tmp);name='test_lifeweave_ref_'+uuid4().hex[:12]
 admin=psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname='postgres',autocommit=True);admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
 os.environ.update(LIFEWEAVE_DB_NAME=name,LIFEWEAVE_LOCAL_WORKER='0',LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT=str(root/'personal'),LIFEWEAVE_TEAM_KNOWLEDGE_ROOT=str(root/'team'))
 server=None;thread=None
 try:
  migrate();app=create_app();s=app.state;s.root=root;s.research_outputs.root=root;s.task_sources.root=root;s.local_workers.root=root
  with TestClient(app) as c:
   item=post(c,'/items',{'itemType':'research','title':'来源保真受控反例'})['id']
   body='''# 受控引用反例

[普通来源](research/source.md)
[带空格来源](<research/source one.md>)
[中文来源](research/来源.md)
[行号来源](research/source.md:2)
[锚点来源](research/source.md#section)
[外链](https://example.org/)

![普通图](research/figure.png)
![带空格图](<research/fig one.png>)
![中文图](research/图.png)
![括号图](research/fig(a).png)
![编码空格图](research/fig%20one.png)
![引用式图][fig]

[fig]: <research/fig one.png>

```md
[代码示例](research/source.md)
![代码图](research/figure.png)
```
'''
   run=completed_run(c,item,body);folder=root/'.runtime/executions/personal'/run['id']/'repo';(folder/'research').mkdir(parents=True)
   for f in ('source.md','source one.md','来源.md'):(folder/'research'/f).write_text('# Source identity '+run['id']+'\n\n## section\nIndependent review content.')
   for f in ('figure.png','fig one.png','图.png','fig(a).png'):(folder/'research'/f).write_bytes(PNG)
   (folder/'.env').write_text('CONTROLLED_HIDDEN_ONLY');(folder/'.runtime/research').mkdir(parents=True);(folder/'.runtime/research/allowed.md').write_text('allowed research');(folder/'.runtime/research/.hidden.md').write_text('CONTROLLED_HIDDEN_ONLY')
   path='研究/引用反例.md';content=body+'\n[普通知识链接](other.md)\n';req={'runId':run['id'],'path':path,'content':content,'baseVersion':'new','reason':'受控来源验收','requestId':'reference-review'}
   candidate=post(c,f'/items/{item}/knowledge-candidates',req);OUT['controlled_identity']={'db':name,'item':item,'run':run['id'],'candidate':candidate['id'],'refs':candidate['references']}
   plain=post(c,'/library/revisions',{'path':'研究/other.md','content':'# 普通知识目标\n确实到达另一篇知识。','baseVersion':'new','reason':'普通相对知识反例'});post(c,'/library/revisions/'+plain['id']+'/decision',{'accept':True},200)
   server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8014,log_level='error',lifespan='off'));thread=threading.Thread(target=server.run,daemon=True);thread.start()
   for _ in range(100):
    if server.started:break
    time.sleep(.05)
   base='http://127.0.0.1:8014'
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome');ctx=browser.new_context(viewport={'width':1400,'height':1100});page=ctx.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:BROWSER_ERRORS.append(str(e)))
    page.goto(base+f'/lifeweave/personal/items/{item}/outputs');page.locator('summary').filter(has_text=path).click();page.locator('.research-knowledge').get_by_text('阅读建议全文',exact=True).click();page.wait_for_timeout(500)
    for image in page.locator('.research-knowledge img').all():image.scroll_into_view_if_needed()
    page.wait_for_timeout(300);OUT['candidate_browser']=observation(page);OUT['original_image_sources']={f:c.get(f'/api/lifeweave/personal/runs/{run["id"]}/assets',params={'path':'research/'+f}).status_code for f in ['figure.png','fig one.png','图.png','fig(a).png']};page.screenshot(path=str(E/'reference-fresh-candidate.png'),full_page=True)
    page.get_by_role('button',name='接受并更新知识原文',exact=True).click();page.get_by_role('link',name='阅读已接受知识',exact=True).click();page.get_by_role('button',name='下载阅读版').wait_for()
    for image in page.locator('.lw-article img').all():image.scroll_into_view_if_needed()
    page.wait_for_timeout(350);OUT['accepted_browser']=observation(page);page.screenshot(path=str(E/'reference-fresh-accepted.png'),full_page=True)
    OUT['source_clicks']={}
    for label in ['普通来源','带空格来源','中文来源','行号来源','锚点来源']:
     link=page.get_by_role('link',name=label,exact=True);href=link.get_attribute('href');response=ctx.request.get(base+href if href.startswith('/') else urllib.parse.urljoin(page.url,href));OUT['source_clicks'][label]={'href':href,'status':response.status,'body':response.text()[:300]}
    OUT['actual_clicks']={}
    for label in ['带空格来源','中文来源']:
     network=[]
     def response_capture(response):
      if '/api/' in response.url and response.status>=400:network.append({'url':response.url,'status':response.status,'body':response.text()})
     page.on('response',response_capture)
     page.get_by_role('link',name=label,exact=True).click();page.get_by_role('alert').wait_for()
     OUT['actual_clicks'][label]={'alert':page.get_by_role('alert').inner_text(),'network':network}
     page.screenshot(path=str(E/('reference-fresh-click-'+('space' if label=='带空格来源' else 'unicode')+'.png')),full_page=True)
     page.remove_listener('response',response_capture)
     page.goto(base+'/lifeweave/personal/knowledge?'+urllib.parse.urlencode({'source':'local','path':path}));page.get_by_role('button',name='下载阅读版').wait_for()
    with page.expect_popup() as pop:page.get_by_role('link',name='行号来源',exact=True).click()
    popup=pop.value;popup.wait_for_load_state();OUT['actual_clicks']['行号来源']={'url':popup.url,'body':popup.locator('body').inner_text()};popup.close()
    with page.expect_download() as down:page.get_by_role('button',name='下载阅读版').click()
    down.value.save_as(E/'reference-fresh-controlled-reading.html')
    with page.expect_download() as down:page.get_by_role('button',name='下载原文').click()
    down.value.save_as(E/'reference-fresh-controlled-original.md')
    doc=s.library.document('personal','local',path);OUT['raw_unchanged']=doc['content']==candidate['content']==(E/'reference-fresh-controlled-original.md').read_text();OUT['accepted_version']=doc['version']
    page.get_by_role('link',name='普通知识链接',exact=True).click();page.get_by_role('heading',name='普通知识目标',exact=True).wait_for();OUT['ordinary_knowledge_target']=page.url
    page.goto((E/'reference-fresh-controlled-reading.html').as_uri());
    for image in page.locator('img').all():image.scroll_into_view_if_needed()
    page.wait_for_timeout(500);OUT['download_browser']=observation(page)
    # A second run using identical paths is never silently resolved to first/last.
    second=completed_run(c,item,body+'\n第二个运行');merged=post(c,f'/items/{item}/knowledge-candidates',{**req,'runId':second['id'],'requestId':'ambiguous','baseVersion':doc['version'],'content':doc['content']+'\n'+body});OUT['ambiguous']=merged['references']
    page.goto(base+f'/lifeweave/personal/items/{item}/outputs');page.locator('.candidate').filter(has_text='等待审阅').locator('summary').first.click();page.locator('.candidate').filter(has_text='等待审阅').get_by_text('阅读建议全文',exact=True).click();OUT['ambiguity_visible']=page.locator('.candidate').filter(has_text='等待审阅').inner_text();OUT['stable_formal_after_draft']=s.library.document('personal','local',path)==doc
    # Library revision consumer shares mapping.
    page.goto(base+'/lifeweave/personal/knowledge');page.get_by_role('button',name='修订与历史').click();page.locator('.lw-knowledge-nav button').filter(has_text='已接受').filter(has_text=path).click();page.get_by_text('阅读建议全文',exact=True).click();page.wait_for_timeout(300);OUT['library_revision_browser']=observation(page)
    browser.close()
   other=post(c,'/items',{'itemType':'research','title':'后续任务：引用反例'})['id'];recommended=c.get(f'/api/lifeweave/personal/items/{other}/input-recommendations',params={'query':'引用反例'}).json();OUT['downstream_recommendations']=recommended
   next_run=post(c,'/runs',{'itemId':other,'instruction':'根据已采纳知识读取原来源，不得误作本轮本地文件','engine':'codex','knowledgeRefs':['local:'+path]},202);snapshot=s.lifeweave_runtime_service.get_run_snapshot('personal',next_run['id']);caps=snapshot['capability_snapshot'];OUT['downstream']={'capabilities':caps,'prompt':snapshot['prompt_snapshot']}
   worktree=root/'materialized';worker=LifeWeaveWorker(client=None,executors={},runtime_root=root/'worker',machine_id='review-only');worker._materialize_capabilities(snapshot,worktree);OUT['downstream_manifest']=json.loads((worktree/'.lifeweave/capability-manifest.json').read_text())
   OUT['path_guards']={}
   for kind,paths in {'source':['.env','.runtime/research/.hidden.md','.runtime/research/allowed.md','../x.md','/etc/passwd',f'../../{second["id"]}/repo/research/source.md'], 'assets':['.env','../x.png','/etc/passwd',f'../../{second["id"]}/repo/research/figure.png']}.items():
    for p in paths:
     r=c.get(f'/api/lifeweave/personal/runs/{run["id"]}/{kind}',params={'path':p});OUT['path_guards'][kind+':'+p]=r.status_code
   OUT['cross_workspace']=c.get(f'/api/lifeweave/team/runs/{run["id"]}/source',params={'path':'research/source.md'}).status_code
   OUT['browser_errors']=BROWSER_ERRORS;save()
 except Exception as exc:
  OUT['script_error']=traceback.format_exc();save();raise
 finally:
  if server:server.should_exit=True
  if thread:thread.join(10)
  admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)));admin.close();OUT['cleanup']={'database_dropped':name,'thread_stopped':not thread or not thread.is_alive(),'temporary_root_removed_on_exit':str(root)};save()
print(json.dumps({'real_source':OUT['real_accepted_source']['url'],'source_clicks':OUT.get('source_clicks'),'errors':OUT.get('browser_errors'),'cleanup':OUT.get('cleanup')},ensure_ascii=False,indent=2))

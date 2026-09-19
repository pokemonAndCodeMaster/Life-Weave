import json,httpx,psycopg
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright
R=Path('/home/yyh/project/lifeweave');H=R/'.runtime/independent-web-review';E=R/'docs/evidence/web-research';d=json.loads((H/'downstream-fixture.json').read_text());base='http://127.0.0.1:8013';c=httpx.Client(base_url=base+'/api/lifeweave/personal');checks=[]
def note(name,ok,detail):checks.append({'name':name,'result':'pass' if ok else 'fail','detail':detail});(E/'independent-downstream-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(name,checks[-1]['result'],str(detail)[:300],flush=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome');page=b.new_page();errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.goto(base+'/lifeweave/personal/items/'+d['item']+'/outputs');review=page.get_by_role('region',name='知识候选审阅');review.get_by_text(d['path']+' · 等待审阅',exact=True).click();review.get_by_text('阅读建议全文',exact=True).click();img=review.locator('img');img.scroll_into_view_if_needed();page.wait_for_function("document.querySelector('.research-knowledge img')?.naturalWidth>0")
 href=review.get_by_role('link',name='来源文本',exact=True).get_attribute('href');note('事项候选预览保留图片与源文本',img.evaluate('(e)=>e.naturalWidth')==1 and c.get(base+href).status_code==200,{'href':href,'image':img.get_attribute('src')})
 note('代码块原链接未被当引用改写',review.locator('pre code').inner_text().strip()=='[example](relative.md)',review.locator('pre code').inner_text())
 review.get_by_role('button',name='接受并更新知识原文').click();review.get_by_text(d['path']+' · 已接受',exact=True).wait_for();review.get_by_role('link',name='阅读已接受知识').click();page.locator('.lw-article img').wait_for();page.locator('.lw-article img').scroll_into_view_if_needed();page.wait_for_function("document.querySelector('.lw-article img')?.naturalWidth>0")
 doc=c.get('/library/document',params={'path':d['path']}).json();note('已接受知识保留图片来源上下文',page.locator('.lw-article img').evaluate('(e)=>e.naturalWidth')==1 and bool(doc.get('references',{}).get('images')),doc.get('references'))
 source=page.get_by_role('link',name='来源文本',exact=True);href=source.get_attribute('href');resp=c.get(base+href);note('知识页source link指回固定run',d['run'] in href and 'SOURCE-51' in resp.text,{'status':resp.status_code,'href':href})
 page.get_by_role('link',name='同目录普通知识',exact=True).click();page.get_by_text('SIBLING-91',exact=True).wait_for();note('普通相对知识链接仍由知识目录解析',True,page.url)
 page.goto(base+'/lifeweave/personal/knowledge?source=local&path='+d['path']);page.get_by_role('button',name='下载阅读版',exact=True).wait_for()
 with page.expect_download() as dl:page.get_by_role('button',name='下载原文',exact=True).click()
 raw=Path(dl.value.path()).read_text();note('下载原文不改写',raw==doc['content'],{'version':doc['version']})
 with page.expect_download() as dl:page.get_by_role('button',name='下载阅读版',exact=True).click()
 html=Path(dl.value.path()).read_text();note('HTML阅读版携带固定来源和普通链接',base+'/api/lifeweave/personal/runs/'+d['run'] in html and 'SIBLING-91' not in html and 'path=' in html and '需要该工作台可访问' in html,{'bytes':len(html.encode())})
 page.screenshot(path=str(E/'independent-knowledge-fixed.png'),full_page=True)
 # Read-only live evidence: the knowledge accepted before this patch must retain exact bytes/version.
 real=json.loads((E/'knowledge-reuse.json').read_text());path=real['acceptedKnowledge']['path'];live=httpx.get('http://127.0.0.1:8011/api/lifeweave/personal/library/document',params={'path':path}).json();page.goto('http://127.0.0.1:8011/lifeweave/personal/knowledge?source=local&path='+path);link=page.get_by_role('link',name='来源记录',exact=True);link.wait_for();href=link.get_attribute('href');res=httpx.get('http://127.0.0.1:8011'+href);note('修复前已接受知识原文版本不变且来源可读',live['content']==real['acceptedKnowledge']['content'] and live['version']==real['acceptedKnowledge']['version'] and res.status_code==200,{'version':live['version'],'href':href,'status':res.status_code})
 # Next task receives the exact references through the formal input snapshots.
 item=c.post('/items',json={'itemType':'personal','title':'采光图文引用的下一任务'}).json();run=c.post('/runs',json={'itemId':item['id'],'engine':'codex','instruction':'读取图文知识','knowledgeRefs':['local:'+d['path']]}).json();m=json.loads((H/'manifest.json').read_text())
 with psycopg.connect(host=str(R/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname=m['database'],autocommit=True) as conn:cap=conn.execute('SELECT capability_snapshot FROM workbench.t_lifeweave_run WHERE id=%s',(run['id'],)).fetchone()[0]
 note('另一运行材料消费者携带固定引用映射',any(x.get('references')==doc['references'] for x in cap),{'runId':run['id']});c.post('/runs/'+run['id']+'/cancel',json={})
 note('浏览器无脚本错误',not errs,errs);b.close()

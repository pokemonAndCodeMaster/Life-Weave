import json,httpx
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path('/home/yyh/project/lifeweave');H=R/'.runtime/independent-web-review';E=R/'docs/evidence/web-research';restart=json.loads((H/'restart.json').read_text());cid=restart['url'].rsplit('/',1)[-1];c=httpx.Client(base_url='http://127.0.0.1:8013');after=c.get('/api/lifeweave/personal/conversations/'+cid).json()
ids=json.loads((H/'ids.json').read_text());checks=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome');page=b.new_page();page.goto(restart['url']);page.get_by_text('服务中断了这轮处理，未自动重发；原话已保存，可以重试',exact=True).wait_for();page.get_by_role('button',name='将原文带回输入框').click();checks.append({'name':'硬中断重启保留原文并标失败','result':'pass' if after['turns'][-1]['status']=='failed' and page.get_by_label('说说你现在想做什么').input_value()==restart['body'] else 'fail','turn':after['turns'][-1]})
 page.goto('http://127.0.0.1:8013/lifeweave/personal/items/'+ids['item']+'/overview');page.get_by_text('完整末尾标识-END',exact=False).wait_for();cont=c.get('/api/lifeweave/personal/items/'+ids['item']+'/continuation').json();checks.append({'name':'新浏览器重启后继续旧事项','result':'pass' if cont['feedback'] and cont['context']['content']['goal']=='另一个更晚目标' else 'fail','feedbackCount':len(cont['feedback'])});page.screenshot(path=str(E/'independent-restart.png'),full_page=True)
 (E/'independent-follow-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
 real=json.loads((E/'real-browser.json').read_text());page.goto('http://127.0.0.1:8011/lifeweave/personal/items/'+real['itemId']+'/outputs');panel=page.get_by_role('region',name='研究成果');panel.get_by_text('新增假设反例：浇水可以造成混杂',exact=True).wait_for();links=panel.get_by_role('link',name='来源记录');href=links.get_attribute('href');response=httpx.get('http://127.0.0.1:8011'+href)
 checks.append({'name':'真实修订稿引用可打开','result':'pass' if response.status_code==200 else 'fail','url':href,'status':response.status_code,'body':response.text[:400]})
 with page.expect_popup() as popup:links.click()
 tab=popup.value;tab.wait_for_load_state();tab.screenshot(path=str(E/'independent-source-link-failure.png'));checks.append({'name':'真实修订稿浏览器公式','result':'pass' if panel.locator('.katex').count()>0 else 'fail','formulas':panel.locator('.katex').count(),'revisionRun':real['revisionRunId']});b.close()
(E/'independent-follow-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False,indent=2))

import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
ROOT=Path.cwd();E=ROOT/'docs/evidence/web-research';U='http://127.0.0.1:8011';c=httpx.Client(base_url=U+'/api/lifeweave/personal',timeout=20)
async def main():
 ref=json.loads((ROOT/'.runtime/web-research-acceptance/research.json').read_text());item=ref['itemId'];before=c.get('/items/'+item).json();version=before['context']['currentVersionId']
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True)
  page=await b.new_page(viewport={'width':1440,'height':1080});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(U+'/lifeweave/personal/items/'+item+'/outputs')
  await page.get_by_role('button',name='从当前成果提出知识修订',exact=True).click()
  await page.get_by_label('知识文件路径').fill('研究/阳台采光因果解释.md')
  await page.get_by_role('button',name='保存候选，查看差异',exact=True).click()
  await page.get_by_text('研究/阳台采光因果解释.md · 等待审阅',exact=True).click()
  await page.get_by_role('button',name='接受并更新知识原文',exact=True).click()
  await page.get_by_text('研究/阳台采光因果解释.md · 已接受',exact=True).wait_for()
  doc=c.get('/library/document',params={'path':'研究/阳台采光因果解释.md'}).json();assert '浇水' in doc['content'] and ref['runId'] in doc['content']
  await page.screenshot(path=str(E/'research-knowledge-accepted.png'),full_page=True)
  await b.close()
  # Brand-new browser session: sources must come from product storage.
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True)
  page=await b.new_page(viewport={'width':1440,'height':1080})
  await page.goto(U+'/lifeweave/personal/conversation')
  await page.get_by_label('说说你现在想做什么').fill('已有知识怎样解释阳台采光与新叶数量的相关关系？请用浇水量的例子说明为什么不能直接推出因果，并指出你实际读取的已接受知识来源。这只是一个问题，不建立事项或执行委托。')
  await page.get_by_role('button',name='发送',exact=True).click();await page.wait_for_url('**/conversation/conversation-*')
  cid=page.url.rsplit('/',1)[-1];end=time.time()+300
  while time.time()<end:
   turns=c.get('/conversations/'+cid).json()['turns']
   if turns and turns[-1]['status'] not in ['queued','processing']:break
   await asyncio.sleep(2)
  t=turns[-1];assert t['status']=='completed' and not t['receipts'] and not t['runId'],t
  assert any(s['path']=='研究/阳台采光因果解释.md' and s['version']==doc['version'] for s in t['sources']),t
  assert '浇水' in t['reply'] and '/knowledge?' in t['reply'],t
  await page.reload();await page.get_by_text('本次参考来源',exact=False).wait_for();await page.screenshot(path=str(E/'new-session-knowledge.png'),full_page=True)
  (E/'knowledge-reuse.json').write_text(json.dumps({'itemId':item,'candidateRunId':ref['runId'],'acceptedKnowledge':doc,'newConversation':cid,'turn':t,'pageErrors':errors},ensure_ascii=False,indent=2,default=str))
  print('PASS knowledge reuse',cid,flush=True)
  await b.close()
asyncio.run(main())

import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
async def main():
 c=httpx.Client(base_url='http://127.0.0.1:8011/api/lifeweave/personal',timeout=20)
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True);page=await b.new_page()
  await page.goto('http://127.0.0.1:8011/lifeweave/personal/conversation');await page.get_by_label('说说你现在想做什么').fill('只记一下：下个月想试试陶艺课。暂时不要安排，不要创建研究事项或开始执行。')
  await page.get_by_role('button',name='发送',exact=True).click();await page.wait_for_url('**/conversation/conversation-*');cid=page.url.rsplit('/',1)[-1];end=time.time()+300
  while time.time()<end:
   turns=c.get('/conversations/'+cid).json()['turns']
   if turns and turns[-1]['status'] not in ('queued','processing'):break
   await asyncio.sleep(2)
  t=turns[-1];assert t['status']=='completed' and len(t['receipts'])==1 and t['receipts'][0]['kind']=='idea' and not t['runId'] and not t['itemId'],t
  Path('docs/evidence/web-research/record-auto.json').write_text(json.dumps(t,ensure_ascii=False,indent=2));print('PASS natural record',cid,flush=True);await b.close()
asyncio.run(main())

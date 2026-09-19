import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
R=Path.cwd();E=R/'docs/evidence/web-research';U='http://127.0.0.1:8011';C='conversation-ec9e93d6ed939b134a7a26d468448760';I='item-023bf9dab82a4466';c=httpx.Client(base_url=U+'/api/lifeweave/personal',timeout=20)
async def main():
 before=c.get('/items/'+I).json();old_ids=[t['id'] for t in c.get('/conversations/'+C).json()['turns']]
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True);page=await b.new_page(viewport={'width':1440,'height':1080})
  await page.goto(U+'/lifeweave/personal/conversation/'+C)
  await page.get_by_label('说说你现在想做什么').fill('我想修改这项研究的当前目标：从单纯解释阳台采光差异，调整为建立一份能复用于日常观察的因果判断清单。请提出目标修改建议，等待我采纳；这次不要发起新的研究执行。')
  await page.get_by_role('button',name='发送',exact=True).click();end=time.time()+300
  while time.time()<end:
   turns=c.get('/conversations/'+C).json()['turns'];t=turns[-1]
   if t['id'] not in old_ids and t['status'] not in ['queued','processing']:break
   await asyncio.sleep(2)
  assert t['status']=='completed' and any(x['kind']=='context' for x in t['receipts']) and not t['runId'],t
  pending=c.get('/items/'+I).json();assert pending['context']['content']==before['context']['content']
  await page.goto(U+'/lifeweave/personal/items/'+I+'/context')
  await page.get_by_role('button',name='采纳此修改',exact=True).click()
  end=time.time()+20
  while time.time()<end:
   after=c.get('/items/'+I).json()
   if after['context']['currentVersionId']!=before['context']['currentVersionId']:break
   await asyncio.sleep(.5)
  assert '因果判断清单' in after['context']['content']['goal']
  await page.reload();await page.get_by_text(after['context']['content']['goal'],exact=False).first.wait_for()
  await page.screenshot(path=str(E/'accepted-context.png'),full_page=True)
  continued=c.get('/items/'+I+'/continuation').json()
  (E/'context-change.json').write_text(json.dumps({'before':before['context'],'proposalTurn':t,'after':after['context'],'continuation':continued},ensure_ascii=False,indent=2,default=str))
  print('PASS context proposal',t['id'],flush=True);await b.close()
asyncio.run(main())

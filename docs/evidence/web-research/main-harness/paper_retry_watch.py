import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
R=Path.cwd();E=R/'docs/evidence/web-research';U='http://127.0.0.1:8010';c=httpx.Client(base_url=U+'/api/lifeweave/personal',timeout=20)
async def main():
 d=json.loads((E/'qwen-drive-retry-start.json').read_text());tid=d['turn']['itemId'];rid=d['turn']['runId'];end=time.time()+2400;last=''
 while time.time()<end:
  run=c.get('/runs/'+rid).json()
  if run['state']!=last:print('Paper state',run['state'],flush=True);last=run['state']
  if run['state'] in ('succeeded','failed','unavailable','cancelled','paused'):break
  await asyncio.sleep(5)
 if run['state'] not in ('succeeded','failed','unavailable','cancelled','paused'):raise TimeoutError('Paper run remains active')
 out=c.get('/items/'+tid+'/research-output').json()
 events=c.get('/runs/'+rid+'/events',params={'limit':200}).json()
 record={'conversationId':d['conversationId'],'itemId':tid,'runId':rid,'run':run,'outputs':out,'events':events}
 (E/'qwen-drive-retry-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
 if out['current']:(E/'qwen-drive-report.md').write_text('# Qwen-Drive 首轮研究产物（未经用户接受）\n\n'+out['current']['content']+'\n')
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True);page=await b.new_page(viewport={'width':1440,'height':1080})
  await page.goto(U+'/lifeweave/personal/items/'+tid+'/outputs');await page.get_by_role('heading',name='当前成果',exact=True).wait_for();await page.screenshot(path=str(E/'qwen-drive-retry-result.png'),full_page=True);await b.close()
 print('Paper finished',run['state'],len(out['current']['content']) if out['current'] else 0,flush=True)
asyncio.run(main())

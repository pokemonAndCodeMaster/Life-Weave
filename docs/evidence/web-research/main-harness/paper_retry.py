import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
R=Path.cwd();E=R/'docs/evidence/web-research';U='http://127.0.0.1:8010'
async def main():
 d=json.loads((E/'qwen-drive-start.json').read_text());old=d['turn']['runId']
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True)
  page=await b.new_page(viewport={'width':1440,'height':1080});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(U+'/lifeweave/personal/runs')
  await page.locator('.lw-knowledge-nav button').filter(has_text='Qwen-Drive').filter(has_text='第 1 次').first.click()
  await page.locator('p.lw-notice.warning').filter(has_text='unsupported Unicode escape sequence').wait_for()
  async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/runs/'+old+'/retry')) as response:
   await page.get_by_role('button',name='按当前背景再试',exact=True).click()
  reply=await response.value;assert reply.status==202,await reply.text();run=await reply.json()
  d['turn']['runId']=run['id'];d['retryOf']=old;d['retryResponse']=run;d['pageErrors']=errors
  (E/'qwen-drive-retry-start.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
  await page.screenshot(path=str(E/'qwen-drive-retry-start.png'),full_page=True);await b.close()
  print('Retried through web',run['id'],run['state'],flush=True)
asyncio.run(main())

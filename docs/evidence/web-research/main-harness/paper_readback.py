import asyncio,json,hashlib
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
R=Path.cwd();E=R/'docs/evidence/web-research';U='http://127.0.0.1:8010';RID='gzrun-20260919-095844-49f47906';ITEM='item-810217743bbb4be2'
async def main():
 c=httpx.Client(base_url=U,timeout=20)
 run=c.get('/api/lifeweave/personal/runs/'+RID).json();assert run['state']=='succeeded',run['state']
 out=c.get('/api/lifeweave/personal/items/'+ITEM+'/research-output').json()['current'];assert out['runId']==RID and len(out['content'])>5000
 original=c.get('/api/lifeweave/personal/runs/'+RID+'/artifacts/result');original.raise_for_status()
 assert original.headers['X-Artifact-Version']=='sha256:'+hashlib.sha256(original.content).hexdigest()
 download=c.get(out['downloadUrl']);download.raise_for_status();assert download.text==out['content'];assert download.headers['ETag']=='"'+out['version']+'"'
 record={'runId':RID,'itemId':ITEM,'state':run['state'],'version':out['version'],'contentLength':len(out['content']),'rawArtifactHash':original.headers['X-Artifact-Version'],'readingHash':hashlib.sha256(download.content).hexdigest(),'images':[],'sources':[],'pageErrors':[]}
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True);page=await b.new_page(viewport={'width':1440,'height':1080})
  page.on('pageerror',lambda e:record['pageErrors'].append(str(e)))
  await page.goto(U+'/lifeweave/personal/items/'+ITEM+'/outputs');await page.get_by_role('heading',name='当前成果',exact=True).wait_for()
  article=page.locator('.research-output article').first;await article.wait_for();await page.get_by_role('button',name='从当前成果提出知识修订',exact=True).wait_for()
  body=await article.inner_text();assert 'Qwen-Drive' in body and len(body)>4500
  for img in await article.locator('img').all():
   await img.scroll_into_view_if_needed();await img.evaluate('el=>el.decode()')
   data=await img.evaluate('el=>({src:el.src,width:el.naturalWidth,height:el.naturalHeight,alt:el.alt})');assert data['width']>0;record['images'].append(data)
  record['formulas']=await article.locator('.katex').count();record['formulaErrors']=await article.locator('.katex-error').count();assert record['formulaErrors']==0
  anchors=article.locator('a[href*="/source?path="]')
  seen=set()
  for anchor in await anchors.all():
   href=await anchor.get_attribute('href')
   if href in seen:continue
   seen.add(href)
   async with page.expect_popup() as popup:
    await anchor.click()
   child=await popup.value;await child.wait_for_load_state('domcontentloaded')
   text=await child.locator('body').inner_text();res=c.get(href);assert res.status_code==200
   if res.headers.get('content-type','').startswith('image/'):
    await child.locator('img').first.evaluate('el=>el.decode()');assert await child.locator('img').first.evaluate('el=>el.naturalWidth')>0
   else:assert len(text)>0
   record['sources'].append({'href':href,'status':res.status_code,'bytes':len(res.content),'sha256':hashlib.sha256(res.content).hexdigest(),'browserTextLength':len(text)})
   await child.close()
  record['bodyTextLength']=len(body)
  await page.evaluate('window.scrollTo(0,0)');await page.screenshot(path=str(E/'qwen-drive-reading-verified.png'),full_page=True)
  await page.goto(U+'/lifeweave/personal/conversation/conversation-6851a0d06ad9a9feb6bc7cd5fb90fbca')
  await page.locator('.research-output article').first.wait_for();assert 'Qwen-Drive' in await page.locator('.research-output article').first.inner_text()
  record['originalConversationShowsCurrentResult']=True
  await page.screenshot(path=str(E/'qwen-drive-conversation-verified.png'),full_page=True)
  assert not record['pageErrors'];await b.close()
 (E/'qwen-drive-reading-verified.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps(record,ensure_ascii=False),flush=True)
asyncio.run(main())

import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
ROOT=Path.cwd();E=ROOT/'docs/evidence/web-research';C='conversation-ec9e93d6ed939b134a7a26d468448760';U='http://127.0.0.1:8011';c=httpx.Client(base_url=U+'/api/lifeweave/personal',timeout=20)
async def main():
 data=c.get('/conversations/'+C).json();turn=data['turns'][-1];item=turn['itemId'];old=c.get('/runs/'+turn['runId']).json();before=c.get('/items/'+item+'/research-output').json()['current']
 assert old['state']=='succeeded'
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True)
  page=await b.new_page(viewport={'width':1440,'height':1080});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(U+'/lifeweave/personal/conversation/'+C)
  await page.get_by_text('从当前成果提出知识修订',exact=True).first.wait_for()
  await page.screenshot(path=str(E/'conversation-result.png'),full_page=True)
  await page.get_by_text('当前方向与明确偏好',exact=True).click()
  await page.get_by_label('当前方向',exact=True).fill('理解如何区分观察相关与因果证据（临时验收空间）')
  await page.get_by_label('明确偏好',exact=True).fill('先举具体例子，明确观察事实和推断的区别。')
  await page.get_by_role('button',name='确认并保存',exact=True).click()
  await page.get_by_text('已保存，后续研究会读取本空间当前方向与偏好。').wait_for()
  article=page.locator('.research-output article').first
  await article.evaluate("el=>{let r=document.createRange();r.selectNodeContents(el.querySelector('p')||el);let s=window.getSelection();s.removeAllRanges();s.addRange(r);el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}))}")
  await page.get_by_label('对这份成果的反馈',exact=True).first.fill('请补一个浇水量构成混杂因素的反例，明确为什么即便差值为4片，也不能直接估计采光因果效应。保留完整报告，补充反例后修订全文。')
  await page.get_by_role('button',name='保存反馈，供下一轮使用',exact=True).first.click()
  await page.get_by_text('反馈已保存，下一轮委托会读取这条反馈。',exact=True).first.wait_for()
  await page.get_by_label('说说你现在想做什么').fill('请沿同一项阳台采光研究继续执行：采用刚才对成果的反馈，补充浇水的混杂反例，并保留原报告其余内容，交付一份完整修订稿。此次用简明表达，不查询外部网站。')
  await page.get_by_role('button',name='发送',exact=True).click()
  end=time.time()+300
  while time.time()<end:
   turns=c.get('/conversations/'+C).json()['turns'];next_turn=turns[-1]
   if next_turn['id']!=turn['id'] and next_turn['status'] not in ['queued','processing']:break
   await asyncio.sleep(2)
  assert next_turn['status']=='completed' and next_turn['itemId']==item,next_turn
  rid=next_turn['runId'];assert rid and rid!=turn['runId'];print('Revision run',rid,flush=True)
  end=time.time()+420
  while time.time()<end:
   run=c.get('/runs/'+rid).json()
   if run['state'] in ['succeeded','failed','unavailable','cancelled']:break
   await asyncio.sleep(3)
  assert run['state']=='succeeded',run
  outputs=c.get('/items/'+item+'/research-output').json();after=outputs['current']
  assert '浇水' in after['content'] and len(outputs['versions'])>=2
  env=run['environmentSnapshot'];assert env['feedbackSnapshot'];assert env['researchSupport']['previousOutput']['version']==before['version']
  assert env['researchSupport']['personalModel']['preferences'].startswith('先举具体例子')
  await page.reload();await page.screenshot(path=str(E/'conversation-revised.png'),full_page=True)
  evidence={'conversationId':C,'itemId':item,'firstRunId':turn['runId'],'revisionRunId':rid,'pageErrors':errors,'initialTurn':turn,'revisionTurn':next_turn,'result':after,'previousVersion':before['version'],'feedback':env['feedbackSnapshot'],'researchSupport':env['researchSupport'],'sources':env.get('selectedInputs')}
  (E/'real-browser.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str))
  (ROOT/'.runtime/web-research-acceptance/research.json').write_text(json.dumps({'conversationId':C,'itemId':item,'runId':rid}))
  print('PASS',json.dumps({'itemId':item,'runId':rid,'resultLength':len(after['content']),'pageErrors':errors}),flush=True)
  await b.close()
asyncio.run(main())

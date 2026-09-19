import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
ROOT=Path.cwd(); EVID=ROOT/'docs/evidence/web-research';EVID.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8011';base=URL+'/api/lifeweave/personal'
c=httpx.Client(base_url=base,timeout=15)
# Explicitly labelled fixture, accepted through the normal knowledge API.
doc='# 阳台采光观察（验收材料）\n\n这是临时验收资料，不是论文结论。两盆同种植物：东向窗边A每天约4小时直射光，北向B每天约1小时。两周后A新叶6片，B新叶2片。单次观察没有随机分配，浇水与原始长势未控制，不能据此证明因果。\n'
r=c.post('/library/revisions',json={'path':'生活/阳台采光.md','content':doc,'baseVersion':'new','reason':'临时验收已知材料'});r.raise_for_status()
c.post('/library/revisions/'+r.json()['id']+'/decision',json={'accept':True}).raise_for_status()
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True)
  page=await browser.new_page(viewport={'width':1440,'height':1080}); errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(URL);await page.get_by_label('说说你现在想做什么').wait_for()
  await page.get_by_label('说说你现在想做什么').fill('周末想买一盆薄荷，先记一下，暂时不推进。')
  await page.get_by_label('本次范围').select_option('record')
  await page.get_by_role('button',name='发送',exact=True).click()
  await page.get_by_text('已保存想法，未安排执行').wait_for(timeout=20000)
  await page.reload();await page.get_by_text('已保存想法，未安排执行').wait_for()
  await page.get_by_role('link',name='开始新对话',exact=True).click()
  await page.get_by_label('说说你现在想做什么').fill('请开始一项研究委托：阅读已有的阳台采光观察知识，分析A与B新叶差异是否足以说明采光的因果影响。请给出一个具体例子、必要的公式与表格，再写出有边界的完整解释。不要查询外部网站，不做新的实验。')
  await page.get_by_role('button',name='发送',exact=True).click()
  await page.wait_for_url('**/conversation/conversation-*',timeout=20000)
  cid=page.url.rsplit('/',1)[-1].split('?')[0]
  print('Conversation',cid,flush=True)
  end=time.time()+300;turn=None
  while time.time()<end:
   data=c.get('/conversations/'+cid).json();turn=data['turns'][-1]
   if turn['status'] not in ['queued','processing']:break
   await asyncio.sleep(2)
  assert turn['status']=='completed',turn
  assert turn['runId'],turn
  run_id=turn['runId'];print('Run',run_id,flush=True)
  await page.screenshot(path=str(EVID/'conversation-running.png'),full_page=True)
  end=time.time()+420
  while time.time()<end:
   run=c.get('/runs/'+run_id).json()
   if run['state'] in ['succeeded','failed','unavailable','cancelled']:break
   await asyncio.sleep(3)
  assert run['state']=='succeeded',run
  output=c.get('/items/'+turn['itemId']+'/research-output').json()['current']
  assert '因果' in output['content'] and len(output['content'])>300
  await page.reload();await page.get_by_text('从当前成果提出知识修订').first.wait_for(timeout=30000)
  await page.screenshot(path=str(EVID/'conversation-result.png'),full_page=True)
  evidence={'conversationId':cid,'itemId':turn['itemId'],'runId':run_id,'pageErrors':errors,'turn':turn,
            'run':{k:run[k] for k in ['id','state','session','capabilities','environmentSnapshot']},'result':output}
  (EVID/'real-browser.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str))
  (ROOT/'.runtime/web-research-acceptance/research.json').write_text(json.dumps({'conversationId':cid,'itemId':turn['itemId'],'runId':run_id}))
  print('PASS',json.dumps({'itemId':turn['itemId'],'runId':run_id,'resultLength':len(output['content']),'pageErrors':errors}),flush=True)
  await browser.close()
asyncio.run(main())

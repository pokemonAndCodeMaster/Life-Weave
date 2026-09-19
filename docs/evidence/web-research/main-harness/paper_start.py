import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
R=Path.cwd();E=R/'docs/evidence/web-research';U='http://127.0.0.1:8010';c=httpx.Client(base_url=U+'/api/lifeweave/personal',timeout=20)
PROMPT='请开始 Qwen-Drive-1.0 的真实论文研究，作为在 LifeWeave 中持续推进的事项。候选原文入口为 https://arxiv.org/abs/2609.00111 ，此前提供的标题为 Qwen-Drive-1.0: An Initial Step towards a Vision-Language Foundation Model for Autonomous Driving。先核对标题、作者、论文版本与官方入口是否相符；若候选链接对象不符或拿不到全文，请给出真实查证结果、缺口和下一步，不根据旧摘要虚构论文内容。若能取得正确全文，围绕问题与动机、方法及必要公式、训练数据与训练阶段、实验、局限，以及对自动驾驶相关工作的启发，交付一份连贯、能继续反馈修订的中文研究报告；明确实际阅读范围，区分作者主张、证据与推断，附可核对的原文及代码出处。相关图必须来自真实取得的论文或官方资料，保存在本轮目录后实际核对。遵循可复用研究方法，正文完整留在网页，不只给文件路径。不要自动接受知识或宣布我已经学会；不要发送外部消息或改动外部系统。'
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True);page=await b.new_page(viewport={'width':1440,'height':1080});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(U+'/lifeweave/personal/conversation');await page.get_by_label('说说你现在想做什么').fill(PROMPT);await page.get_by_role('button',name='发送',exact=True).click();await page.wait_for_url('**/conversation/conversation-*')
  cid=page.url.rsplit('/',1)[-1];print('Paper conversation',cid,flush=True)
  record={'conversationId':cid,'prompt':PROMPT,'pageErrors':errors};(E/'qwen-drive-start.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
  end=time.time()+300
  while time.time()<end:
   turns=c.get('/conversations/'+cid).json()['turns']
   if turns and turns[-1]['status'] not in ('queued','processing'):break
   await asyncio.sleep(2)
  t=turns[-1];record['turn']=t;(E/'qwen-drive-start.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
  assert t['status']=='completed',t
  if not t['runId']:print('No run: '+t['reply'],flush=True)
  else:print('Paper run',t['runId'],flush=True)
  await page.reload();await page.get_by_label('对话记录').wait_for();await page.screenshot(path=str(E/'qwen-drive-start.png'),full_page=True);await b.close()
asyncio.run(main())

import os,sys,tempfile,threading,time,subprocess,json,signal,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ['LIFEWEAVE_TEST_DB']='1'
from test_live_database import client as client_fixture,post
from test_research_outputs import completed_run,PNG
from src.lifeweave.research_outputs import ResearchOutputs,router
from playwright.sync_api import sync_playwright
import uvicorn
EVIDENCE=ROOT/'docs/evidence/web-research';EVIDENCE.mkdir(parents=True,exist_ok=True)
import socket
for port in (8012,5193):
 with socket.socket() as probe:
  probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
  probe.bind(('127.0.0.1',port))
class Factory:
 def __init__(self,root):self.root=root
 def mktemp(self,name):
  p=self.root/name;p.mkdir();return p
with tempfile.TemporaryDirectory(prefix='lifeweave-w3-') as temp:
 generator=client_fixture.__wrapped__(Factory(Path(temp)))
 client=next(generator);app=client.app;state=app.state
 if not hasattr(state,'research_outputs'):
  state.research_outputs=ResearchOutputs(state.lifeweave_service,state.lifeweave_runtime_service,state.library,Path(temp))
  fallback=app.router.routes.pop();app.include_router(router);app.router.routes.append(fallback)
 state.research_outputs.root=Path(temp)
 item=post(client,'/items',{'itemType':'research','title':'受控夹具：研究成果阅读'})['id']
 report='# 研究成果：受控浏览器夹具\n\n这是合成内容，只验证产品操作，不是实际论文研究。\n\n## 训练数据\n\n样本稀缺时需要说明分布差异。行内公式 $E_i=mc_j^2$。\n\n$$\\frac{a+b}{2}$$\n\n\\[\\sum_{i=1}^n x_i\\]\n\n| 数据 | 说明 |\n| --- | --- |\n| 训练集 | 合成夹具 |\n\n```python\nprint("可阅读的代码")\n```\n\n![本轮图示](figure.png)\n\n![缺失图示](missing.png)\n\n![外部图示](https://external.invalid/figure.png)\n\n[来源说明](README.md)'
 run=completed_run(client,item,report)
 folder=Path(temp)/'.runtime/executions/personal'/run['id']/'repo';folder.mkdir(parents=True)
 # Larger PNG: valid compressed RGBA image created without image dependencies.
 import zlib,struct
 def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
 width,height=320,120
 rows=b''.join(b'\x00'+bytes([40,100,80,255])*width for _ in range(height))
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
 (folder/'figure.png').write_bytes(png);(folder/'README.md').write_text('合成夹具的来源说明')
 config=uvicorn.Config(app,host='127.0.0.1',port=8012,log_level='error',lifespan='off');server=uvicorn.Server(config)
 thread=threading.Thread(target=server.run,daemon=True);thread.start()
 html=ROOT/'web/w3-verification.html'
 html.write_text('''<!doctype html><html lang="zh"><meta charset="utf-8"><title>W3 受控夹具</title><style>body{max-width:960px;margin:30px auto;font-family:system-ui}button,input,textarea,select{font:inherit;padding:8px}textarea{width:100%;box-sizing:border-box}section{margin-bottom:40px}.lw-stack{display:flex;flex-direction:column;gap:14px}.lw-between,.lw-inline{display:flex;justify-content:space-between;gap:12px}.lw-notice{padding:12px;background:#eef7f1}.lw-diff{white-space:pre-wrap}.lw-label{display:flex;flex-direction:column}pre{background:#f3f4f6;padding:16px}.lw-btn{cursor:pointer}</style><div id="app"></div><script type="module">import {createApp,h,ref} from 'vue';import Output from '/src/features/lifeweave/components/ResearchOutputPanel.vue';import Review from '/src/features/lifeweave/components/ResearchKnowledgeReview.vue';createApp({setup(){const n=ref(0);return()=>h('main',[h(Output,{workspace:'personal',itemId:''' +json.dumps(item)+''','onCandidate-created':()=>n.value++}),h(Review,{workspace:'personal',itemId:''' +json.dumps(item)+''',refreshKey:n.value})])}}).mount('#app')</script></html>''')
 vite=subprocess.Popen(['npm','run','dev','--','--port','5193','--strictPort'],cwd=ROOT/'web',stdout=open(Path(temp)/'vite.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
 try:
  import urllib.request
  for _ in range(80):
   try:urllib.request.urlopen('http://127.0.0.1:5193/w3-verification.html',timeout=.5);break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True, executable_path="/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome");page=browser.new_page(viewport={'width':1200,'height':1100});errors=[];external=[]
   page.on('pageerror',lambda e:(errors.append(str(e)),print('PAGEERROR',str(e),flush=True)))
   page.on('console',lambda m:print('CONSOLE',m.type,m.text,flush=True) if m.type=='error' else None)
   page.on('request',lambda r:external.append(r.url) if 'external.invalid' in r.url else None)
   def proxy(route):
    response=route.fetch(url=route.request.url.replace('http://127.0.0.1:5193','http://127.0.0.1:8012'),headers={**route.request.headers,'host':'127.0.0.1:5193'})
    route.fulfill(response=response)
   page.route('http://127.0.0.1:5193/api/**',proxy)
   page.goto('http://127.0.0.1:5193/w3-verification.html');page.get_by_role('heading',name='研究成果：受控浏览器夹具').wait_for()
   img=page.get_by_role('img',name='本轮图示');img.scroll_into_view_if_needed();page.wait_for_function("document.querySelector('img')?.naturalWidth === 320")
   page.get_by_text('缺失图示（加载失败；请核对本轮资产）',exact=True).wait_for()
   assert page.locator('.katex').count()==3
   assert not external and not errors
   image_result=img.evaluate('(e)=>({src:e.src,complete:e.complete,width:e.naturalWidth,height:e.naturalHeight})')
   page.screenshot(path=str(EVIDENCE/'outputs-reading-fixture.png'),full_page=True)
   # Select an actual paragraph and persist a referenced feedback through the form.
   paragraph=page.locator('article p').filter(has_text='样本稀缺时').first
   paragraph.evaluate('e=>{const r=document.createRange();r.selectNodeContents(e);const s=window.getSelection();s.removeAllRanges();s.addRange(r);e.dispatchEvent(new MouseEvent("mouseup",{bubbles:true}))}')
   page.get_by_label('对这份成果的反馈').fill('请补充训练数据的取样边界。')
   page.get_by_role('button',name='保存反馈，供下一轮使用').click();page.get_by_text('反馈已保存，下一轮委托会读取这条反馈。',exact=True).wait_for()
   records=state.lifeweave_service.execution_feedback('personal',item)
   assert records[0]['runId']==run['id'] and '样本稀缺' in records[0]['body'] and records[0]['anchor']
   # Create and explicitly accept a candidate in the actual Vue review component.
   page.get_by_role('button',name='从当前成果提出知识修订').click()
   page.get_by_label('知识文件路径').fill('研究/浏览器夹具.md');page.get_by_label('建议正文').fill('# 可复用研究笔记\n\n样本稀缺时需要保留训练分布依据。')
   page.get_by_role('button',name='保存候选，查看差异').click()
   page.get_by_text('知识候选已保存，请在下方比较差异后决定是否接受。',exact=True).wait_for()
   page.locator('summary').filter(has_text='研究/浏览器夹具.md').click()
   page.get_by_role('button',name='接受并更新知识原文').click()
   page.get_by_role('link',name='阅读已接受知识').wait_for()
   document=state.library.document('personal','local','研究/浏览器夹具.md')
   assert '可复用研究笔记' in document['content'] and run['id'] in document['content']
   page.screenshot(path=str(EVIDENCE/'outputs-reviewed-fixture.png'),full_page=True)
   results={'kind':'controlled-fixture-not-real-AI','image':image_result,'formulaCount':page.locator('.katex').count(),'externalImageRequests':external,'browserErrors':errors,'expectedMissingImageStatus':404,'proxy':'Vite frontend API requests forwarded to isolated backend preserving original Host','feedback':{'runId':records[0]['runId'],'anchor':records[0]['anchor'],'body':records[0]['body']},'knowledge':{'path':document['path'],'version':document['version'],'content':document['content']},'api':'http://127.0.0.1:8012','ui':'http://127.0.0.1:5193/w3-verification.html','database':'disposable, removed after verification'}
   (EVIDENCE/'outputs-browser-fixture.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
   browser.close()
 finally:
  html.unlink(missing_ok=True);os.killpg(vite.pid,signal.SIGTERM);vite.wait(timeout=10);server.should_exit=True;thread.join(timeout=10)
  try:next(generator)
  except StopIteration:pass

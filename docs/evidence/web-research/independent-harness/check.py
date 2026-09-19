import json,time,base64
from pathlib import Path
from uuid import uuid4
import httpx,psycopg
from psycopg.rows import dict_row
from playwright.sync_api import sync_playwright
R=Path('/home/yyh/project/lifeweave');H=R/'.runtime/independent-web-review';E=R/'docs/evidence/web-research';E.mkdir(parents=True,exist_ok=True)
m=json.loads((H/'manifest.json').read_text());c=httpx.Client(base_url='http://127.0.0.1:8013');base='/api/lifeweave/personal';checks=[]
def record(name,ok,detail):
 checks.append({'name':name,'result':'pass' if ok else 'fail','detail':detail});print(name,checks[-1]['result'],str(detail)[:250],flush=True)
def api(method,path,body=None,status=200):
 r=c.request(method,base+path,json=body);assert r.status_code==status,(path,r.status_code,r.text);return r.json()
def post(path,body,status=201):return api('POST',path,body,status)
def done(cid,tid):
 for i in range(100):
  t=next(t for t in api('GET',f'/conversations/{cid}')['turns'] if t['id']==tid)
  if t['status'] not in ('queued','processing'):return t
  time.sleep(.1)
 raise RuntimeError('turn stuck')
def turn(cid,text,mode='auto'):
 t=post(f'/conversations/{cid}/turns',{'requestId':uuid4().hex,'body':text,'mode':mode},202);return done(cid,t['id'])
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',headless=True)
 page=browser.new_page(viewport={'width':1365,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8013/lifeweave');page.get_by_label('说说你现在想做什么').wait_for()
 record('首次入口',page.url.endswith('/personal/conversation'),page.url)
 page.get_by_label('说说你现在想做什么').fill('独立复核：植物光照有什么影响？');page.get_by_role('button',name='发送',exact=True).click();page.get_by_text('独立受控协议结果；不是实际 AI 回答。',exact=True).wait_for()
 conv=api('GET','/conversations')['items'][0];cid=conv['id'];ans=api('GET',f'/conversations/{cid}')['turns'][0]
 state=api('GET','/state');record('问答不建事项和运行',not state['items'] and ans['status']=='completed',{'turn':ans['id'],'items':len(state['items'])})
 page.get_by_label('说说你现在想做什么').fill('只保存阳台植物观察的想法');page.get_by_label('本次范围').select_option('record');page.get_by_role('button',name='发送',exact=True).click();page.get_by_text('已保存想法，未安排执行',exact=True).wait_for()
 ts=api('GET',f'/conversations/{cid}')['turns'];saved=ts[-1];record('记录不执行',saved['receipts'][0]['kind']=='idea' and not saved['runId'],saved['id'])
 original={'requestId':saved['requestId'],'body':saved['body'],'mode':saved['mode']}
 again=post(f'/conversations/{cid}/turns',original,202)
 # Browser omitted optional null values; model request canonicalizes defaults.
 record('同一原请求幂等',again['id']==saved['id'] and len(api('GET',f'/conversations/{cid}')['turns'])==2,again['id'])
 conflict=c.post(base+f'/conversations/{cid}/turns',json={**original,'body':'更换内容'})
 record('同请求内容冲突',conflict.status_code==409,conflict.status_code)
 page.reload();page.get_by_text('已保存想法，未安排执行',exact=True).wait_for();record('刷新保留记录',True,cid)
 # Same request IDs in team must stay a separate owner; own personal IDs inaccessible.
 team=c.get('/api/lifeweave/team/conversations/'+cid)
 record('跨空间对话隔离',team.status_code==404 and c.get('/api/lifeweave/team/conversations').json()['total']==0,team.status_code)
 item=post('/items',{'itemType':'research','title':'阳台采光独立复核','initialContext':{'goal':'旧目标：观察植物朝向'}});iid=item['id']
 assoc=post('/conversations',{'requestId':uuid4().hex,'itemId':iid});t=turn(assoc['id'],'请改目标：比较窗户方向')
 prop=next(r for r in t['receipts'] if r['kind']=='context');before=api('GET','/items/'+iid)
 run=post('/runs',{'itemId':iid,'instruction':'仅固定旧目标输入，不执行','engine':'codex'},202);rid=run['id']
 newer=post('/items/'+iid+'/context/proposals',{'baseVersion':1,'title':'并发另提目标','proposedContent':{'goal':'另一个更晚目标'}})
 post('/context-proposals/'+newer['id']+'/accept',{'version':1},200)
 reject=c.post(base+'/context-proposals/'+prop['id']+'/accept',json={'version':1})
 record('目标提案不自动接受且冲突不覆盖',before['context']['content']['goal'].startswith('旧目标') and reject.status_code==409 and api('GET','/items/'+iid)['context']['content']['goal']=='另一个更晚目标',{'proposal':prop['id'],'status':reject.status_code})
 conn=psycopg.connect(host=str(R/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname=m['database'],row_factory=dict_row,autocommit=True)
 frozen=conn.execute('SELECT context_snapshot,prompt_snapshot FROM workbench.t_lifeweave_run WHERE id=%s',(rid,)).fetchone();record('旧运行仍保留旧目标', '旧目标' in json.dumps(frozen,ensure_ascii=False),rid)
 # Explicitly synthetic output fixture; only output/state consumers are under review here.
 report='# 阳台采光的受控成果\n\n训练数据说明：观测方位和时长，不足以证明品种差异。\n\n$$E = \\frac{1}{n}\\sum_{i=1}^{n} x_i$$\n\n![采光示意](figure.png)\n\n| 朝向 | 小时 |\n| --- | --- |\n| 南 | 4 |\n\n```python\nprint(4)\n```\n\n[官方引用](https://example.org/research)\n\n'+('长成果段落：保留完整内容。\n\n'*150)+'完整末尾标识-END'
 conn.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded',result=%s,finished_at=now() WHERE id=%s",(report,rid))
 folder=H/'.runtime/executions/personal'/rid/'repo';folder.mkdir(parents=True)
 (folder/'figure.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
 page.goto(f'http://127.0.0.1:8013/lifeweave/personal/items/{iid}/outputs');panel=page.get_by_role('region',name='研究成果');panel.get_by_text('完整末尾标识-END',exact=False).wait_for();panel.locator('img').scroll_into_view_if_needed();page.wait_for_function("document.querySelector('.research-output img')?.naturalWidth > 0")
 record('完整成果公式图片正式消费者',panel.locator('.katex').count()>0 and panel.locator('table').count()==1 and panel.locator('code').count()>0 and c.get(base+f'/runs/{rid}/research-output/download').text==report,{'length':len(report),'math':panel.locator('.katex').count(),'imageNaturalWidth':panel.locator('img').evaluate('(e)=>e.naturalWidth')})
 panel.locator('.lw-markdown p').first.evaluate("el=>{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r);el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));}")
 panel.get_by_label('对这份成果的反馈').fill('解释应补充测量时段，不要改变事项。');panel.get_by_role('button',name='保存反馈，供下一轮使用').click();panel.get_by_text('反馈已保存，下一轮委托会读取这条反馈。').wait_for()
 feedback=api('GET','/items/'+iid+'/continuation')['feedback'][-1]
 next_run=post('/runs',{'itemId':iid,'instruction':'继续同一事项，修订测量说明','engine':'codex'},202)
 snapshot=conn.execute('SELECT environment_snapshot,prompt_snapshot FROM workbench.t_lifeweave_run WHERE id=%s',(next_run['id'],)).fetchone()
 record('选段反馈关联与下轮读取',feedback['runId']==rid and rid in feedback['anchor'] and '补充测量时段' in snapshot['prompt_snapshot'] and '完整末尾标识-END' in snapshot['prompt_snapshot'],{'feedback':feedback['id'],'anchor':feedback['anchor'],'nextRun':next_run['id']})
 post('/runs/'+next_run['id']+'/cancel',{},200)
 # Generate a candidate through web, accept through web, follow knowledge link.
 panel.get_by_role('button',name='从当前成果提出知识修订').click();panel.get_by_label('知识文件路径').fill('生活/独立采光.md');panel.get_by_label('建议正文').fill('# 阳台采光\n\n朝向和日照时长需要分开记录。独立来源事实值：WINDOW-42。');panel.get_by_role('button',name='保存候选，查看差异').click()
 review=page.get_by_role('region',name='知识候选审阅');review.get_by_text('生活/独立采光.md · 等待审阅',exact=True).click();review.get_by_role('button',name='接受并更新知识原文').click();review.get_by_text('生活/独立采光.md · 已接受',exact=True).wait_for()
 review.get_by_role('link',name='阅读已接受知识').click();page.get_by_text('朝向和日照时长需要分开记录。独立来源事实值：WINDOW-42。',exact=True).wait_for()
 doc=api('GET','/library/document?path=生活/独立采光.md');record('知识接受更新与正式阅读',rid in doc['content'] and (H/'personal/生活/独立采光.md').read_text()==doc['content'],{'path':doc['path'],'version':doc['version']})
 other=post('/items',{'itemType':'personal','title':'另一个非论文任务：阳台采光种植','initialContext':{'goal':'用已有朝向与日照知识规划记录'}})
 otherconv=post('/conversations',{'requestId':uuid4().hex,'itemId':other['id']});delegated=turn(otherconv['id'],'委托：阳台采光的朝向观察记录')
 sr=conn.execute('SELECT capability_snapshot,prompt_snapshot FROM workbench.t_lifeweave_run WHERE id=%s',(delegated['runId'],)).fetchone()
 record('另任务自动选材并固定当前知识', 'WINDOW-42' in json.dumps(sr,ensure_ascii=False) and '生活/独立采光.md' in json.dumps(sr,ensure_ascii=False),{'run':delegated['runId'],'sourceVersion':doc['version']})
 candidate={'runId':rid,'path':doc['path'],'content':'不该覆盖的内容','baseVersion':doc['version'],'reason':'独立拒绝测试','requestId':uuid4().hex}
 rej=post('/items/'+iid+'/knowledge-candidates',candidate);post('/library/revisions/'+rej['id']+'/decision',{'accept':False},200)
 record('拒绝保持原文',api('GET','/library/document?path=生活/独立采光.md')['version']==doc['version'],rej['id'])
 change=post('/items/'+iid+'/knowledge-candidates',{**candidate,'requestId':uuid4().hex});(H/'personal/生活/独立采光.md').write_text(doc['content']+'\n外部先到的新事实')
 conflict=c.post(base+'/library/revisions/'+change['id']+'/decision',json={'accept':True});record('知识源变化冲突',conflict.status_code==409 and '外部先到的新事实' in (H/'personal/生活/独立采光.md').read_text(),conflict.status_code)
 cross=c.get('/api/lifeweave/team/items/'+iid+'/research-output'); cross_doc=c.get('/api/lifeweave/team/library/document',params={'path':doc['path']});cross_asset=c.get('/api/lifeweave/team/runs/'+rid+'/assets',params={'path':'figure.png'})
 record('跨空间成果知识资产隔离',[cross.status_code,cross_doc.status_code,cross_asset.status_code]==[404,404,404],[cross.status_code,cross_doc.status_code,cross_asset.status_code])
 page.goto('http://127.0.0.1:8013/lifeweave/personal/conversation');page.get_by_label('说说你现在想做什么').wait_for();page.get_by_label('说说你现在想做什么').fill('受控解释失败：保留这个请求');page.get_by_role('button',name='发送',exact=True).click();page.get_by_text('独立验证：解释器故障',exact=True).wait_for();page.get_by_role('button',name='将原文带回输入框').click();record('解释失败原话可重试',page.get_by_label('说说你现在想做什么').input_value().startswith('受控解释失败'),page.url)
 page.goto('http://127.0.0.1:8013/lifeweave/personal/conversation');page.get_by_label('说说你现在想做什么').fill('等待受控中断：取消后仍有原话');page.get_by_role('button',name='发送',exact=True).click();page.get_by_role('button',name='取消本次处理').wait_for();page.get_by_role('button',name='取消本次处理').click();page.get_by_text('本轮处理已停止，原话已保存',exact=True).wait_for();record('取消保留原话',True,page.url)
 page.screenshot(path=str(E/'independent-cancel.png'),full_page=True)
 record('浏览器脚本错误',not errors,errors)
 (H/'ids.json').write_text(json.dumps({'item':iid,'run':rid,'conversation':cid,'delegatedRun':delegated['runId'],'other':other['id']},ensure_ascii=False))
 conn.close();browser.close()
(E/'independent-checks.json').write_text(json.dumps({'manifest':m,'checks':checks},ensure_ascii=False,indent=2))

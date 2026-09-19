import json,time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
R=Path('/home/yyh/project/lifeweave');H=R/'.runtime/independent-web-review';E=R/'docs/evidence/web-research';c=httpx.Client(base_url='http://127.0.0.1:8013');checks=[]
def note(n,ok,d):checks.append({'name':n,'result':'pass' if ok else 'fail','detail':d});print(n,checks[-1]['result'],d,flush=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome');ctx=b.new_context();page=ctx.new_page();page.goto('http://127.0.0.1:8013/lifeweave/personal/conversation');page.get_by_label('说说你现在想做什么').wait_for()
 seen=[]
 def lost_response(route):
  req=route.request
  if req.method=='POST':
   response=route.fetch();seen.append({'request':req.post_data_json,'status':response.status,'body':response.json()});route.abort('failed')
  else:route.continue_()
 page.route('**/conversations/*/turns',lost_response)
 text='响应丢失的独立只记录请求'
 page.get_by_label('说说你现在想做什么').fill(text);page.get_by_label('本次范围').select_option('record');page.get_by_role('button',name='发送',exact=True).click();page.get_by_role('button',name='核对并重试原请求').wait_for()
 page.unroute('**/conversations/*/turns',lost_response);page.reload();page.get_by_role('button',name='核对并重试原请求').wait_for()
 note('响应丢失刷新保留原文与模式',page.get_by_label('说说你现在想做什么').input_value()==text and page.get_by_label('本次范围').input_value()=='record',seen[0]['body']['id'])
 page.get_by_label('切换工作空间').select_option('team');page.wait_for_url('**/team/conversation');page.get_by_label('说说你现在想做什么').wait_for();note('未确认请求不带入团队',page.get_by_label('说说你现在想做什么').input_value()=='' and page.get_by_role('button',name='核对并重试原请求').count()==0,page.url)
 page.get_by_label('切换工作空间').select_option('personal');page.wait_for_url('**/personal/conversation');page.get_by_role('button',name='核对并重试原请求').wait_for();page.get_by_role('button',name='核对并重试原请求').click();page.get_by_text('已保存想法，未安排执行',exact=True).wait_for()
 cid=seen[0]['body']['conversationId'];rows=c.get('/api/lifeweave/personal/conversations/'+cid).json()['turns'];note('未知结果重试同一身份无重复',len(rows)==1 and rows[0]['id']==seen[0]['body']['id'],{'turns':len(rows),'requestId':rows[0]['requestId']})
 page.screenshot(path=str(E/'independent-uncertain.png'),full_page=True)
 # Mobile first-use composition and horizontal overflow.
 mobile=b.new_page(viewport={'width':390,'height':844});mobile.goto('http://127.0.0.1:8013/lifeweave/personal/conversation');mobile.get_by_label('说说你现在想做什么').wait_for();note('手机首进没有水平溢出',mobile.evaluate('document.documentElement.scrollWidth<=innerWidth'),mobile.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})'))
 # Keep an in-progress conversation to validate actual server restart recovery.
 mobile.get_by_label('说说你现在想做什么').fill('等待受控中断：独立服务重启验收');mobile.get_by_role('button',name='发送',exact=True).click();mobile.get_by_role('button',name='取消本次处理').wait_for();(H/'restart.json').write_text(json.dumps({'url':mobile.url,'body':'等待受控中断：独立服务重启验收'}))
 b.close()
(E/'independent-edge-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))

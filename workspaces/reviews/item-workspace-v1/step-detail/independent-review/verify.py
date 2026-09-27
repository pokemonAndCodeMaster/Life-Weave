import hashlib,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('/tmp/lw-step-detail-independent-review')
BASE='http://127.0.0.1:8010'
result={'started':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'mobile':{},'development':{},'blocked_writes':[]}

def store(): (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
def guard(route):
 if route.request.method not in ('GET','HEAD','OPTIONS'):
  result['blocked_writes'].append({'method':route.request.method,'url':route.request.url});route.abort()
 else:route.continue_()
def size(page):return page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth,body:document.body.scrollWidth,x:scrollX,y:scrollY})')
def snap(page,name):page.screenshot(path=str(OUT/name));return name
with sync_playwright() as p:
 b=p.chromium.launch(headless=True)
 ctx=b.new_context(viewport={'width':390,'height':844},device_scale_factor=1)
 ctx.route('**/*',guard)
 page=ctx.new_page()
 net=[];errors=[]
 page.on('request',lambda req:net.append({'time':time.time(),'method':req.method,'url':req.url}))
 page.on('pageerror',lambda err:errors.append(str(err)))
 page.goto(BASE+'/lifeweave/personal/items/item-de7785d0790445d8/overview',wait_until='networkidle')
 page.locator('[data-step-id]:visible').filter(has_text='研究').first.click()
 page.locator('#work-step-detail .output-reader .lw-markdown code').filter(has_text='0ee2542').wait_for()
 m=result['mobile'];m['url']=page.url;m['initial_size']=size(page)
 h=page.locator('#work-step-detail .output-reader .lw-markdown code').filter(has_text='0ee2542').first
 h.scroll_into_view_if_needed()
 m['hash']=h.evaluate('e=>({text:e.textContent,length:e.textContent.length,rects:[...e.getClientRects()].map(r=>r.toJSON()),overflowWrap:getComputedStyle(e).overflowWrap,whiteSpace:getComputedStyle(e).whiteSpace})')
 m['hash']['screenshot']=snap(page,'mobile-hash.png');m['hash']['size']=size(page)
 m['formulas']=[];m['tables']=[];m['images']=[]
 for kind,selector in [('formulas','.katex-display'),('tables','table')]:
  loc=page.locator('#work-step-detail .output-reader '+selector)
  for i in range(loc.count()):
   e=loc.nth(i);e.scroll_into_view_if_needed()
   data=e.evaluate('e=>({clientWidth:e.clientWidth,scrollWidth:e.scrollWidth,rect:e.getBoundingClientRect().toJSON(),overflowX:getComputedStyle(e).overflowX,text:(e.querySelector("annotation")?.textContent||e.textContent).slice(0,1000)})')
   data['before_size']=size(page)
   data['scrolled']=e.evaluate('e=>{e.scrollLeft=e.scrollWidth;return {left:e.scrollLeft,max:e.scrollWidth-e.clientWidth}}')
   data['after_size']=size(page)
   if i in [0,loc.count()-1] or (data['scrollWidth']>data['clientWidth'] and not any(x['scrollWidth']>x['clientWidth'] for x in m[kind])):
    data['screenshot']=snap(page,f'mobile-{kind}-{i}-right.png')
    e.evaluate('e=>e.scrollLeft=0');data['screenshot_left']=snap(page,f'mobile-{kind}-{i}-left.png')
   m[kind].append(data)
 for i in range(page.locator('#work-step-detail .output-reader img').count()):
  im=page.locator('#work-step-detail .output-reader img').nth(i);im.scroll_into_view_if_needed()
  page.wait_for_function('e=>e.complete',arg=im.element_handle(),timeout=15000)
  data=im.evaluate('e=>({src:e.src,complete:e.complete,naturalWidth:e.naturalWidth,naturalHeight:e.naturalHeight,rect:e.getBoundingClientRect().toJSON()})')
  data['size']=size(page);data['screenshot']=snap(page,f'mobile-image-{i}.png');m['images'].append(data)
 page.locator('#work-step-detail').evaluate('e=>e.scrollIntoView({block:"end"})')
 m['end_size']=size(page);m['end_screenshot']=snap(page,'mobile-end.png');m['errors']=errors;m['network']=net
 m['pass']=all(s['document']==390 and s['body']==390 for s in [m['initial_size'],m['hash']['size'],m['end_size']]+[x['before_size'] for k in ['formulas','tables'] for x in m[k]]+[x['after_size'] for k in ['formulas','tables'] for x in m[k]]+[x['size'] for x in m['images']]) and m['hash']['text']=='0ee2542eb28e50948cae8561332365d5f76e29d4' and all(x['naturalWidth']>0 for x in m['images'])
 store();ctx.close()
 for tab in ['overview','outputs']:
  ctx=b.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1);ctx.route('**/*',guard)
  page=ctx.new_page();net=[];responses=[];errors=[]
  page.on('request',lambda req:net.append({'time':time.time(),'method':req.method,'url':req.url}))
  page.on('response',lambda res:responses.append({'time':time.time(),'status':res.status,'url':res.url}))
  page.on('pageerror',lambda err:errors.append(str(err)))
  item='item-62fe9c309d994457'
  page.goto(BASE+f'/lifeweave/personal/items/{item}/{tab}',wait_until='networkidle')
  if tab=='overview':page.locator('[data-step-id]:visible').filter(has_text='实施与交付').first.click()
  else:
   entries=page.locator('.index-entry');result['development']['output_entries']=entries.all_inner_texts()
   delivery_entry=entries.filter(has_text='代码交付').first
   if delivery_entry.count():delivery_entry.click()
  page.get_by_role('button',name='查看实际 Git 差异',exact=True).click()
  page.locator('.diff-preview').wait_for();page.locator('.diff-preview').scroll_into_view_if_needed()
  page.locator('.diff-preview').evaluate('e=>e.scrollTop=180')
  before=page.evaluate('''()=>{const r=document.querySelector('.output-reader');window.__review={reader:r,markdown:r.querySelector('.lw-markdown'),paragraph:r.querySelector('.lw-markdown p'),diff:r.querySelector('.diff-preview'),details:r.querySelector('.diff-preview').parentElement,removed:[]};window.__review.observer=new MutationObserver(ms=>{for(const m of ms) for(const n of m.removedNodes) if(n.nodeType===1)window.__review.removed.push({tag:n.tagName,cls:n.className,text:n.textContent.slice(0,100)})});window.__review.observer.observe(r,{childList:true,subtree:true});return {detailsOpen:window.__review.details.open,bodyChars:window.__review.markdown?.textContent.length,diffChars:window.__review.diff.textContent.length,scroll:window.__review.diff.scrollTop,text:window.__review.markdown?.textContent}}''')
  before['body_sha256']=hashlib.sha256((before.pop('text') or '').encode()).hexdigest()
  start=time.time();before_requests=len(net)
  entry={'url':page.url,'before':before,'before_screenshot':snap(page,f'development-{tab}-before.png'),'request_count_before':before_requests}
  with page.expect_response(lambda r:r.request.method=='GET' and r.url.endswith(f'/items/{item}/work-view'),timeout=20000) as poll:
   pass
  res=poll.value;entry['poll']={'status':res.status,'url':res.url,'elapsed_seconds':time.time()-start,'body_sha256':hashlib.sha256(res.body()).hexdigest()}
  page.wait_for_timeout(1200)
  entry['after']=page.evaluate('''()=>{const s=window.__review,r=document.querySelector('.output-reader');return {readerSame:r===s.reader,markdownSame:r?.querySelector('.lw-markdown')===s.markdown,paragraphSame:r?.querySelector('.lw-markdown p')===s.paragraph,diffSame:r?.querySelector('.diff-preview')===s.diff,diffConnected:s.diff.isConnected,detailsOpen:s.details.isConnected&&s.details.open,bodyChars:r?.querySelector('.lw-markdown')?.textContent.length,diffChars:r?.querySelector('.diff-preview')?.textContent.length,scroll:r?.querySelector('.diff-preview')?.scrollTop,removed:s.removed,text:r?.querySelector('.lw-markdown')?.textContent}}''')
  entry['after']['body_sha256']=hashlib.sha256((entry['after'].pop('text') or '').encode()).hexdigest()
  entry['after_screenshot']=snap(page,f'development-{tab}-after.png');entry['network']=net;entry['responses']=responses;entry['requests_after_open']=net[before_requests:];entry['errors']=errors
  a=entry['after'];entry['pass']=res.status==200 and all(a[k] for k in ['readerSame','markdownSame','paragraphSame','diffSame','diffConnected','detailsOpen']) and a['body_sha256']==before['body_sha256'] and not any('/delivery' in x['url'] or '/runs/' in x['url'] for x in entry['requests_after_open'])
  result['development'][tab]=entry;store();ctx.close()
 b.close()
print(json.dumps({'mobile_pass':result['mobile']['pass'],'mobile_stats':{'formulas':len(m['formulas']),'tables':len(m['tables']),'images':len(m['images'])},'overview_pass':result['development']['overview']['pass'],'outputs_pass':result['development']['outputs']['pass'],'overview_after':result['development']['overview']['after'],'outputs_after':result['development']['outputs']['after'],'blocked_writes':result['blocked_writes'],'evidence':str(OUT/'results.json')},ensure_ascii=False,indent=2))

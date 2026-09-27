from playwright.sync_api import sync_playwright, expect
from pathlib import Path
import json, zipfile
base='http://127.0.0.1:8010'
out=Path('/home/yyh/project/lifeweave/workspaces/reviews/item-workspace-v1/step-detail')
checks={};writes=[];errors=[]
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page(viewport={'width':1440,'height':1080},accept_downloads=True)
 page.set_default_timeout(10000)
 page.on('request',lambda r:writes.append(r.method+' '+r.url) if r.method in ['POST','PUT','DELETE','PATCH'] else None)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/lifeweave/personal/items/item-de7785d0790445d8/overview')
 expect(page.get_by_role('button',name='概览',exact=True)).to_be_visible()
 expect(page.locator('.node-detail')).to_have_count(0)
 page.locator('.graph-node').first.focus();page.keyboard.press('Enter')
 detail=page.get_by_role('region',name='所选步骤')
 expect(detail.locator('.output-reader .lw-markdown')).to_contain_text('GSSM')
 expect(detail.locator('h3').first).to_be_focused()
 expect(detail.locator('.research-history')).to_have_count(0)
 assert '?step=' in page.url
 page.screenshot(path=str(out/'gssm-step.png'))
 img=detail.locator('img').first;img.scroll_into_view_if_needed()
 expect(img).to_be_visible()
 page.wait_for_function("() => [...document.querySelectorAll('.node-detail img')].every(i=>i.complete && i.naturalWidth>0)")
 checks['gssm']={'inlineBodyChars':len(detail.locator('.research-output article').inner_text()),'images':detail.locator('img').count(),'imageWidths':detail.locator('img').evaluate_all('(images)=>images.map(i=>i.naturalWidth)')}
 page.screenshot(path=str(out/'gssm-image.png'))
 with page.expect_download() as download:
  detail.get_by_role('link',name='下载完整包（含图片）').click()
 path=download.value.path()
 with zipfile.ZipFile(path) as z:
  names=z.namelist(); pictures=[n for n in names if Path(n).suffix.lower() in ['.png','.jpg','.jpeg','.svg','.webp']]
  assert pictures
  checks['gssm']['zipFiles']=len(names);checks['gssm']['zipPictures']=len(pictures)
 detail.get_by_role('button',name='在成果页阅读 ↗').click()
 expect(page.locator('.workspace-outputs .research-history')).to_be_visible()
 page.get_by_role('button',name='概览',exact=True).click()
 expect(detail.locator('h3').first).to_have_text('委托研究与整理')
 page.reload();expect(detail.locator('h3').first).to_have_text('委托研究与整理')
 detail.get_by_role('button',name='收起详情').click()
 expect(page.locator('.node-detail')).to_have_count(0)
 expect(page.locator('.graph-node').first).to_be_focused()
 checks['navigation']='键盘打开、聚焦、成果页返回、刷新选中、收起还原焦点均通过'
 page.set_viewport_size({'width':390,'height':844})
 page.locator('.mobile-node').first.click()
 expect(detail.locator('.research-output article')).to_contain_text('GSSM')
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 page.screenshot(path=str(out/'mobile-step.png'));checks['mobile390']='无页面横向溢出，节点正文可读'
 page.set_viewport_size({'width':1440,'height':1080})
 page.goto(base+'/lifeweave/personal/items/item-62fe9c309d994457/overview')
 page.locator('.graph-node').filter(has_text='形成方案').click()
 expect(detail.locator('.output-reader .lw-markdown')).not_to_be_empty()
 expect(detail.locator('.delivery')).to_have_count(0)
 plan_length=len(detail.locator('.output-reader .lw-markdown').inner_text())
 page.locator('.graph-node').filter(has_text='实施与交付').click()
 expect(detail.locator('.delivery')).to_be_visible()
 with page.expect_download() as download:
  detail.get_by_role('button',name='下载完整交付 ZIP',exact=True).click()
 with zipfile.ZipFile(download.value.path()) as z:
  names=z.namelist();assert any(n.endswith('manifest.json') for n in names)
  manifest=json.loads(z.read(next(n for n in names if n.endswith('manifest.json'))))
  checks['development']={'planChars':plan_length,'zipFiles':len(names),'manifestFiles':len(manifest['files'])}
 detail.get_by_role('button',name='查看实际 Git 差异').click();expect(detail.locator('.diff-preview')).to_contain_text('diff --git')
 detail.locator('h3').first.scroll_into_view_if_needed();page.screenshot(path=str(out/'development-step.png'))
 detail.locator('.output-choices button').filter(has_text='实施运行结果').click()
 expect(detail.locator('.delivery')).to_have_count(0)
 expect(detail.locator('.output-reader .lw-markdown')).not_to_be_empty()
 checks['development']['selection']='两个产物切换，正文和交付不串；真实差异可读'
 page.goto(base+'/lifeweave/personal/items/item-7547b65b4f704829/overview?step=list')
 expect(detail.locator('.output-empty')).to_contain_text('标记为已完成，但没有关联成果')
 page.locator('.graph-node').filter(has_text='真实页面验证').click()
 expect(detail.locator('.output-reader .lw-markdown')).to_contain_text('事项工作区第一版')
 page.screenshot(path=str(out/'manual-step.png'))
 detail.get_by_role('button',name='讨论这一步',exact=True).click()
 page.wait_for_url('**/conversation?**')
 assert 'mode=discuss' in page.url
 draft=json.loads(page.evaluate("sessionStorage.getItem('lifeweave:quote:personal:item-7547b65b4f704829')"))
 assert 'validation' in draft['anchor'] and 'artifact:result-' in draft['text']
 textarea=page.locator('#conversation-body')
 expect(textarea).to_have_value(draft['text'])
 checks['manual']='无产物说明、人工 Markdown 正文、讨论草稿中的步骤及成果引用均核对；未发送'
 checks['writes']=writes;checks['pageErrors']=errors
 assert not writes and not errors
 (out/'browser-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
 print(json.dumps(checks,ensure_ascii=False,indent=2));b.close()

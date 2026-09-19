import json
from pathlib import Path
from playwright.sync_api import sync_playwright
E=Path('docs/evidence/web-research');d=json.loads((E/'knowledge-reuse.json').read_text());e={}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome');page=b.new_page();page.goto('http://127.0.0.1:8011/lifeweave/personal/knowledge?source=local&path='+d['acceptedKnowledge']['path']);link=page.get_by_role('link',name='来源记录',exact=True);link.wait_for();e['href']=link.get_attribute('href')
 with page.expect_response(lambda r:'/library/document?' in r.url) as response:link.click()
 r=response.value;e['status']=r.status;e['url']=r.url;e['response']=r.text();e['pageURL']=page.url;page.screenshot(path=str(E/'independent-knowledge-link-failure.png'),full_page=True);b.close()
(E/'independent-knowledge-link-failure.json').write_text(json.dumps(e,ensure_ascii=False,indent=2));print(json.dumps(e,ensure_ascii=False,indent=2))

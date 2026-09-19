import json,httpx,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path('/home/yyh/project/lifeweave');H=R/'.runtime/independent-web-review';E=R/'docs/evidence/web-research';ids=json.loads((H/'ids.json').read_text());rid=ids['run'];repo=H/'.runtime/executions/personal'/rid/'repo';(repo/'.runtime/research').mkdir(parents=True,exist_ok=True);(repo/'.runtime/private').mkdir(exist_ok=True);(repo/'.runtime/research/readable.json').write_text('{"kind":"independent-owned-fixture","value":42}');(repo/'.runtime/private/secret.json').write_text('{"dummy":"NOT A REAL CREDENTIAL"}');(repo/'.runtime/research/alias.json').symlink_to(repo/'.runtime/private/secret.json');c=httpx.Client(base_url='http://127.0.0.1:8013');checks=[]
for path,status in [('.runtime/research/readable.json',200),('.runtime/private/secret.json',400),('.runtime/research/alias.json',400),('../outside.md',400),('/etc/passwd',400),('.runtime/research/../private/secret.json',400)]:
 resp=c.get(f'/api/lifeweave/personal/runs/{rid}/source',params={'path':path});checks.append({'path':path,'expected':status,'status':resp.status_code,'result':'pass' if resp.status_code==status else 'fail'})
 if resp.status_code==200:assert resp.json()['value']==42
cross=c.get(f'/api/lifeweave/team/runs/{rid}/source',params={'path':'.runtime/research/readable.json'});checks.append({'name':'跨空间来源隔离','status':cross.status_code,'result':'pass' if cross.status_code==404 else 'fail'})
real=json.loads((E/'real-browser.json').read_text());rr=real['revisionRunId'];out=httpx.get(f'http://127.0.0.1:8011/api/lifeweave/personal/items/{real["itemId"]}/research-output').json()['current'];checks.append({'name':'修复未改写真实成果','result':'pass' if out['version']==real['result']['version'] else 'fail','version':out['version']})
for filename in ('sources.md','manifest.json'):
 resp=httpx.get(f'http://127.0.0.1:8011/api/lifeweave/personal/runs/{rr}/source',params={'path':f'.runtime/research/{rr}/{filename}'})
 check={'name':'真实成果来源 '+filename,'status':resp.status_code,'result':'pass' if resp.status_code==200 else 'fail'}
 if filename.endswith('.json') and resp.status_code==200:check['parsedJSON']=resp.json()
 checks.append(check)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome');page=b.new_page();page.goto('http://127.0.0.1:8011/lifeweave/personal/items/'+real['itemId']+'/outputs');panel=page.get_by_role('region',name='研究成果');panel.get_by_role('link',name='核对清单').wait_for()
 with page.expect_popup() as popup:panel.get_by_role('link',name='核对清单').click()
 tab=popup.value;tab.wait_for_load_state();manifest=json.loads(tab.locator('body').inner_text());checks.append({'name':'成熟解析器校验真实manifest','result':'pass' if isinstance(manifest,dict) else 'fail','keys':list(manifest)});b.close()
(E/'independent-source-fix-checks.json').write_text(json.dumps({'candidate':'d69b257','checks':checks},ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False,indent=2))
f=E/'independent-source-link-original-failure.json';d=json.loads(f.read_text());d.pop('observedAt',None);f.write_text(json.dumps(d,ensure_ascii=False,indent=2))

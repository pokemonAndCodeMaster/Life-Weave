"""Real browser checks against the isolated service, never production writes."""
import json,re,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8012'
AGENT='browser-validation-'+str(int(time.time()))
with sync_playwright() as play:
    browser=play.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(10000)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/lifeweave/personal/agents',wait_until='networkidle')
    page.get_by_role('button',name='注册 Agent',exact=True).click()
    page.get_by_label('稳定 ID').fill(AGENT)
    page.get_by_label('名称',exact=True).fill('浏览器验证助手')
    page.get_by_role('combobox',name=re.compile('^能力')).select_option('general')
    page.get_by_label('用途说明').fill('隔离数据库中的真实注册与配置回读验证。')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/agents')) as registered:
        page.get_by_role('button',name='保存配置',exact=True).click()
    assert registered.value.status==201,registered.value.text()
    registration=registered.value.json()
    print('register',registered.value.status,flush=True)
    page.reload(wait_until='networkidle')
    expect(page.get_by_role('heading',name='浏览器验证助手',exact=True)).to_be_visible()
    card=page.locator('.agent-card').filter(has=page.get_by_role('heading',name='浏览器验证助手',exact=True))
    card.get_by_role('button',name='编辑配置').click()
    page.get_by_label('名称',exact=True).fill('浏览器验证助手·已编辑')
    with page.expect_response(lambda r:r.request.method=='PATCH' and ('/agents/'+AGENT) in r.url) as updated:
        page.get_by_role('button',name='保存配置',exact=True).click()
    assert updated.value.status==200,updated.value.text()
    update=updated.value.json()
    print('edit',updated.value.status,flush=True)
    page.reload(wait_until='networkidle')
    expect(page.get_by_role('heading',name='浏览器验证助手·已编辑').first).to_be_visible()
    page.get_by_role('button',name='执行记录',exact=True).first.click()
    expect(page.locator('.execution-rows li').first).to_be_visible(timeout=30000)
    expect(page.get_by_role('heading',name='Agent 中心')).to_be_visible()
    text=page.locator('main').inner_text()
    page.screenshot(path=str(OUT/'execution-list-isolated.png'),full_page=True)
    (OUT/'browser-registration.json').write_text(json.dumps({'registered':registration,'updated':update,'executionListText':text,'pageErrors':errors,'database':'isolated'},ensure_ascii=False,indent=2))
    print(text[-1500:],flush=True)
    browser.close()

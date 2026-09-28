"""Exercise the real built UI and HTTP service on the isolated database."""
import json
import re
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:8012'
OUT = Path(__file__).resolve().parent
PARENT = 'item-c0f13d85b5c145fd'

def call(path, body=None, method=None):
    request = urllib.request.Request(BASE + '/api/lifeweave/personal' + path,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={'Content-Type':'application/json'}, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)

for item_id, intro in json.loads((OUT.parent/'overview-plan.json').read_text()).items():
    item = call('/items/' + item_id)
    call('/items/' + item_id + '/overview', {'version':item['version'], **intro}, 'PUT')

binding = call('/work-bindings/resolve', {'requestId':'isolated-browser-journey-' + str(int(time.time())),
    'decision':'child', 'parentId':PARENT, 'title':'隔离页面验证：共用 Agent 派发 '+str(int(time.time())),
    'goal':'验证页面派发、归属继承和执行详情；隔离服务关闭执行节点，不声称真实模型完成。',
    'itemType':'other'})
item_id = binding['item']['id'] if 'item' in binding else binding['itemId']
catalog = call('/item-organization/catalog')
parent = next(item for item in catalog['items'] if item['id'] == PARENT)
child = next(item for item in catalog['items'] if item['id'] == item_id)
assert child['parentId'] == PARENT
assert child['topicIds'] == parent['topicIds'] and child['domainIds'] == parent['domainIds']
result = {'environment':'isolated database; workers disabled', 'child':child, 'checks':[]}

with sync_playwright() as play:
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(12000)
    errors=[]; page.on('pageerror', lambda error:errors.append(str(error)))
    page.goto(BASE+'/lifeweave/personal/items', wait_until='networkidle')
    expect(page.get_by_label('分组方式')).to_have_value('topic')
    expect(page.get_by_role('button',name='展开 自动驾驶论文持续研读')).to_be_visible()
    page.get_by_role('button',name='展开 自动驾驶论文持续研读').click()
    expect(page.locator('a[href*="item-de7785d0790445d8"]').first).to_be_visible()
    page.screenshot(path=str(OUT/'organized-items-final.png'),full_page=True)
    page.get_by_role('button',name='筛选',exact=True).click()
    page.get_by_label('筛选领域').select_option('研究与学习')
    expect(page.locator('.lw-table-footer')).to_contain_text('3 项事项')
    result['checks'].append('专题默认分组、论文父项展开、领域筛选得到三项含父项')

    page.goto(BASE+'/lifeweave/personal/items/'+PARENT+'/overview',wait_until='networkidle')
    overview=page.locator('.work-overview')
    for name in ('背景','要做什么','预期结果','真实进展','实际产出'):
        expect(overview.get_by_role('heading',name=name,exact=True)).to_be_visible()
    expect(overview).to_contain_text('事项的介绍、分类和 Agent 执行入口分散')
    page.screenshot(path=str(OUT/'overview-final.png'),full_page=True)
    overview.get_by_role('button',name='编辑介绍').click()
    intent='隔离浏览器编辑：同一目标下验证派发与阅读'
    overview.get_by_label('要做什么',exact=True).fill(intent)
    overview.get_by_role('button',name='保存介绍').click()
    expect(overview).to_contain_text(intent)
    page.reload(wait_until='networkidle')
    expect(page.locator('.work-overview')).to_contain_text(intent)
    page.goto(BASE+'/lifeweave/personal/items/item-7547b65b4f704829/overview',wait_until='networkidle')
    expect(page.locator('.work-overview .outputs button').first).to_be_visible()
    page.locator('.work-overview .outputs button').first.click()
    expect(page).to_have_url(re.compile('/outputs'))
    result['checks'].append('五项概述、上一轮固定产物在站内打开、编辑介绍后刷新持久化')

    page.goto(BASE+'/lifeweave/personal/agents',wait_until='networkidle')
    page.get_by_label('给事项派任务').select_option(item_id)
    page.get_by_role('button',name='派任务',exact=True).click()
    launch=page.get_by_role('region',name='委托 Agent')
    launch.get_by_role('combobox',name=re.compile('^Agent')).select_option('general')
    launch.get_by_label('本次任务').fill('仅验证已登记任务能入队；隔离服务不启动模型。')
    with page.expect_response(lambda response: response.request.method=='POST' and response.url.endswith('/agent-dispatch')) as dispatched:
        launch.get_by_role('button',name='开始委托',exact=True).click()
    assert dispatched.value.status==202, dispatched.value.text()
    execution=dispatched.value.json(); result['execution']=execution
    expect(page.get_by_role('region',name='执行详情')).to_be_visible()
    expect(page.get_by_role('heading',name='本次输入')).to_be_visible()
    expect(page.get_by_role('note')).to_contain_text('轨迹')
    page.screenshot(path=str(OUT/'queued-execution-final.png'),full_page=True)
    detail=call('/agent-executions/'+execution['kind']+'/'+execution['id'])
    assert detail['configuration']['agentId']=='general'
    assert detail['events']
    result['checks'].append('Agent 中心真实 POST 共用派发、进入同一详情、固定配置与平台入队事件')
    result['detail']=detail
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'execution-narrow-final.png'),full_page=True)
    result['narrowOverflow']=page.evaluate('document.documentElement.scrollWidth > innerWidth')
    assert not result['narrowOverflow']
    result['pageErrors']=errors
    assert not errors,errors
    browser.close()
(OUT/'browser-journey.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'checks':result['checks'],'itemId':item_id,'executionId':execution['id']},ensure_ascii=False))

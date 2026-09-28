"""Read-only browser verification of deployed real records and fixed results."""
import json,time,urllib.request,urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

BASE='http://127.0.0.1:8010'
OUT=Path(__file__).resolve().parent/'production'
def get(path):
    return json.load(urllib.request.urlopen(BASE+'/api/lifeweave/personal'+path,timeout=60))

scenarios=[
    ('external_session','external-ee630a9a0ff794aa5f3d8f8ef4429298','artifact:'),
    ('managed_development','dev-e8f9f45f61889ee6e151d434c9ef3525','delivery:'),
    ('managed_run','gzrun-20260919-130600-2cabbf3e','run:'),
]
evidence={'checks':[],'listingTimings':[]}
for attempt in range(2):
    start=time.perf_counter();listing=get('/agent-executions?limit=8')
    evidence['listingTimings'].append({'seconds':round(time.perf_counter()-start,3),'rows':len(listing['items']),'total':listing['total']})

with sync_playwright() as play:
    browser=play.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(30000)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    for kind,identity,prefix in scenarios:
        detail=get('/agent-executions/'+kind+'/'+identity)
        item=detail['execution']['itemId'];view=get('/items/'+item+'/work-view')
        output=next(o for o in detail['outputs'] if str(o.get('id','')).startswith(prefix))
        expected=next(o for o in view['outputs'] if o['id']==output['id'])
        page.goto(BASE+'/lifeweave/personal/agent-executions/'+kind+'/'+identity,wait_until='domcontentloaded')
        region=page.get_by_role('region',name='实际产出')
        expect(region).to_be_visible()
        link=region.locator('a').filter(has_text='在事项中阅读')
        expect(link.first).to_be_visible()
        target=link.locator('xpath=.')
        # Select by exact encoded output query rather than list position.
        anchors=region.locator('a').all()
        for anchor in anchors:
            href=anchor.get_attribute('href') or ''
            if urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get('output')==[output['id']]:
                anchor.click();break
        else: raise AssertionError('missing fixed output link '+output['id'])
        expect(page.locator('.index-entry.active strong')).to_have_text(expected['title'])
        evidence['checks'].append({'kind':kind,'executionId':identity,'outputId':output['id'],'title':expected['title'],'url':page.url})
        if kind=='managed_development':page.screenshot(path=str(OUT/'live-fixed-delivery.png'),full_page=True)

    page.goto(BASE+'/lifeweave/personal/agent-executions/managed_development/dev-e8f9f45f61889ee6e151d434c9ef3525',wait_until='networkidle')
    expect(page.locator('.detail-status')).to_contain_text('成果待验收')
    expect(page.get_by_role('region',name='执行步骤').locator('li')).to_have_count(3)
    expect(page.get_by_text('查看完整固定输入',exact=True)).to_be_visible()
    assert not page.locator('.raw-record').first.evaluate('(element)=>element.open')
    result_top=page.get_by_role('region',name='实际产出').bounding_box()['y']
    assert result_top<1000,result_top
    page.get_by_text('展开阅读正文',exact=True).first.click()
    expect(page.locator('.output-reading[open] .lw-markdown, .output-reading[open] .markdown-body').first).to_be_visible()
    page.get_by_text('展开阅读正文',exact=True).first.click()
    page.screenshot(path=str(OUT/'live-execution-completed.png'),full_page=True)
    evidence['firstOutputY']=result_top

    page.goto(BASE+'/lifeweave/personal/items/item-80ad795359af474a/overview',wait_until='networkidle')
    expect(page.locator('.work-overview')).to_contain_text('3 / 3 步完成')
    page.screenshot(path=str(OUT/'live-step-graph.png'),full_page=True)
    page.goto(BASE+'/lifeweave/personal/agents?tab=executions',wait_until='networkidle')
    expect(page.locator('.execution-rows li').first).to_be_visible()
    page.screenshot(path=str(OUT/'agent-executions-final.png'),full_page=True)
    page.goto(BASE+'/lifeweave/personal/items',wait_until='networkidle')
    expect(page.get_by_label('分组方式')).to_have_value('topic')
    page.screenshot(path=str(OUT/'items-final.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.goto(BASE+'/lifeweave/personal/agents',wait_until='networkidle')
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.screenshot(path=str(OUT/'agent-center-narrow.png'),full_page=True)
    evidence['pageErrors']=errors
    assert not errors,errors
    browser.close()
(OUT/'browser-final.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
print(json.dumps(evidence,ensure_ascii=False))

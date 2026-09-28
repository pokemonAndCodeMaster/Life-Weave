"""Explicit, bounded real model verification launched from the production UI."""
import json
import os
import re
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE='http://127.0.0.1:8010'
OUT=Path(__file__).resolve().parent/'production'
MODEL=os.getenv('LIFEWEAVE_SMOKE_MODEL','')
SUFFIX='-default' if not MODEL else '-named'
def call(path, body=None):
    req=urllib.request.Request(BASE+'/api/lifeweave/personal'+path,
        data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,
        headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=60))

bound=call('/work-bindings/resolve',{'requestId':'agent-center-live-development-20260928',
    'decision':'child','parentId':'item-c0f13d85b5c145fd',
    'title':'Agent 中心真实开发链验证', 'itemType':'requirement',
    'goal':'从新 Agent 中心发起一个有界真实开发委托，观察方案、独立审阅、隔离实施和固定差异；保留已采集过程，不把技术验证当成用户接受。'})
item_id=bound['itemId']
instruction=('本次只修改这个极小验证仓的 README.md：加一段中文“运行示例”，写出 python hello.py 的运行命令和准确输出 Hello, LifeWeave!。'
    '先读 README.md 与 hello.py，按开发流程形成短而完整的方案、独立审阅后再实施，实际运行命令验证输出。'
    '保留原介绍。不联网，不安装依赖，不改 hello.py，不添加其他文件，不修改LifeWeave主仓，不改上级事项目标。'
    '这一有界案例只用于验证新的 Agent 中心到实际开发执行链，不代表用户已验收整个平台。')
with sync_playwright() as play:
    browser=play.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.set_default_timeout(30000)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/lifeweave/personal/agents?itemId='+item_id,wait_until='networkidle')
    launch=page.get_by_role('region',name='委托 Agent')
    launch.get_by_role('combobox',name=re.compile('^Agent')).select_option('development')
    launch.get_by_label('本次任务').fill(instruction)
    launch.get_by_label('项目 Git 目录').fill(str(Path('.runtime/agent-center-smoke-target').resolve()))
    launch.get_by_role('combobox',name=re.compile('^执行范围')).select_option('implement')
    launch.get_by_role('combobox',name=re.compile('^方案检查')).select_option('independent')
    launch.get_by_label('模型（可选）').fill(MODEL)
    launch.get_by_text('方法、知识与运行设置',exact=True).click()
    launch.get_by_label('本次明确不带知识').check()
    # The fixture is a separate committed repository, so the generic method is
    # sufficient; unrelated project docs would cause irrelevant context drift.
    with page.expect_response(lambda response:response.request.method=='POST' and response.url.endswith('/agent-dispatch')) as response:
        launch.get_by_role('button',name='开始委托',exact=True).click()
    assert response.value.status==202,response.value.text()
    execution=response.value.json()
    expect(page.get_by_role('region',name='执行详情')).to_be_visible()
    page.screenshot(path=str(OUT/('live-development-start'+SUFFIX+'.png')),full_page=True)
    (OUT/('live-development'+SUFFIX+'.json')).write_text(json.dumps({'binding':bound,'execution':execution,'instruction':instruction,
        'expectedFiles':['README.md'],'modelRequested':MODEL or None,'browserErrors':errors},ensure_ascii=False,indent=2))
    print(json.dumps({'itemId':item_id,'execution':execution},ensure_ascii=False),flush=True)
    browser.close()

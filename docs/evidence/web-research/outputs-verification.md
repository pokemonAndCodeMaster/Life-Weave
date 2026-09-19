# 成果与知识纵切：受控验证

2026-09-19。这里是产品操作夹具，不是真实 AI 研究结果。测试只使用新建临时 PostgreSQL 数据库、临时知识和运行目录；终止结果由 fixture 明确写入，不调用模型。未修改或重启 8010 的日常服务。

已验证：

- 真实 Chromium 显示运行目录中 PNG，`naturalWidth=320`、`naturalHeight=120`；行内和块级公式实际排版。截图已查看。
- 缺失图片返回 404，页面显示加载失败；外部图片只显示原出处链接，没有自动发起请求。API 拒绝伪图片、路径穿越、跨空间和跨运行目录符号链接。
- 从正文选段，反馈包含运行身份、成果版本、引用和用户纠偏，保存到既有执行反馈。公式引用恢复为 LaTeX，避免复制视觉布局碎片。
- 从成果提出候选，页面显示差异，显式接受后真实 Markdown 正文更新并保留来源。独立 API 测试另覆盖拒绝、源版本变化后的冲突、重新合并，以及新事项推荐命中当前知识版本。
- 同一请求重试不重复生成候选；写入修订后注入失败，修订与来源关联一起回滚。前端反馈、候选、重合并重试复用请求身份；旧事项的异步响应不清空新事项草稿。
- 成果读取优先最新成功运行，历史运行、失败部分输出和人工成果保留。

证据：`outputs-reading-fixture.png`、`outputs-reviewed-fixture.png`、`outputs-browser-fixture.json`。截图使用实际产品组件与临时页面，不能单独作为完整应用导航、重启接续或真实模型执行的验收依据。主线集成另行验证。

复现：

```bash
LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest -q tests/test_research_outputs.py
npm --prefix web test -- --run src/features/lifeweave/components/ResearchOutputPanel.test.ts src/features/lifeweave/components/MarkdownBody.test.ts
npm --prefix web run type-check
.venv/bin/python docs/evidence/web-research/outputs-browser-fixture.py
```

浏览器脚本使用空闲端口 8012/5193 和本机已安装的 Chromium 1208，完成后停止自身进程、删除临时数据库与目录。它不会安装浏览器；其他机器需按实际已安装路径调整 executable_path。预期缺失图片会留下浏览器 404 网络日志；页面脚本错误为零。

边界：只支持本轮本机已存在的 PNG/JPEG/GIF/WebP，不自动抓取外部图片，也没有远端节点资产传输。知识候选不会自动接受。长历史按页完整读取，目前没有大量运行正文的性能验收。

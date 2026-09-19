# 知识阅读提示独立交付复核

**pass**。含 NUL 的受控 PDF 提取结果，经真实 HTTP worker、PostgreSQL、事项成果、网页提出候选、网页接受、正式知识阅读及实际下载 HTML 后，字符投影说明仍然可见。原始执行下载保留 NUL 原始字节及匹配的哈希。相邻的普通字符知识与多运行同名引用检查均通过。本结论仅覆盖本次提示合并差异，不代表重新验收全部 G1 或论文研究内容。

这是未参与实现的新上下文亲自执行的复核；没有调用真实模型，没有更改实现、`review.md` 或用户日常数据。

| 关闭条件 | 结果 | 亲自执行的动作与观察 | 证据与处理 |
| --- | --- | --- | --- |
| 提示贯穿成果、候选、正式阅读和 HTML | pass | 真实 HTTP worker 写入含 `A\u0000B` 的报告；浏览器从事项成果提出候选、展开建议全文、接受、打开正式知识、下载阅读版并在 Chromium 打开该 HTML。四个位置均有原始 NUL、可读投影与原文保留的解释。 | [事项截图](knowledge-notice-final-output.png)、[候选截图](knowledge-notice-final-nul-candidate.png)、[正式阅读截图](knowledge-notice-final-nul-accepted.png)、[导出截图](knowledge-notice-final-nul-exported.png)、[实际下载 HTML](knowledge-notice-final-nul-reading.html)。无需处理。 |
| 原始执行文本仍为原始字节且 hash 一致 | pass | 浏览器点击“下载原始执行文本”，下载字节与执行器输入完全相等；包含真实 NUL。实际下载 SHA-256 为 `20e12e4e04b3b492c50831b0f87caf5d7343e5290bd9512010a968c8605796e6`，与 HTTP `X-Artifact-Version`、ETag 一致。另点“下载正文”，哈希与成果版本一致。 | [原始字节文件](knowledge-notice-final-browser-original.txt)、[可读正文](knowledge-notice-final-readable.md)、[观察及响应头](knowledge-notice-final-observations.json)。无需处理。 |
| 原文与版本没有额外静默改写 | pass | 提交前读取网页建议正文；候选仅增加已明确展示的来源段。接受前文件不存在；接受后文件、候选和 API 正文逐字一致。原文下载与正式版本 SHA-256 一致；阅读和导出后重读文件、正文与版本均不变。合并第二来源时也逐项验证。 | [首份知识候选及正式正文](knowledge-notice-final-nul-knowledge.json)、[实际原文下载](knowledge-notice-final-nul-accepted.md)、[合并后知识](knowledge-notice-final-overlap-knowledge.json)。无需处理。 |
| 来源链接、图片映射不丢 | pass | 含 NUL 与普通两份知识的候选/正式映射一致，链接和图片都指向正确 run。正式页面及下载 HTML 中实际点击来源链接，在新标签读到各自固定来源内容；两处图片均真正解码，`naturalWidth=1`，映射未丢。图片是明确的 1×1 固定夹具，不以图像外观替代映射验证。 | [浏览器点击与下载轨迹](knowledge-notice-final-browser-trace.zip)、[详细检查](knowledge-notice-final-observations.json)。无需处理。 |
| 多运行歧义提示与 NUL 提示同时保留 | pass | 第二个无 NUL 成果通过网页“读取已有知识并准备合并”加入第一份知识，两个运行均引用 `source.md` 和 `figure.png`。候选、正式知识、下载 HTML 保留一条 NUL 说明及两条歧义说明；冲突映射为空，没有悄悄选择某个 run。 | [合并候选](knowledge-notice-final-overlap-candidate.png)、[合并正式阅读](knowledge-notice-final-overlap-accepted.png)、[合并 HTML 实际打开](knowledge-notice-final-overlap-exported.png)。无需处理。 |
| 无 NUL 普通知识没有伪警告 | pass | 第二个真实 worker 结果只有普通字符、字面 `\u0000` 与可见 `␀`。单独走网页候选、接受、阅读及 HTML 下载，warnings 为空，没有 NUL 解释；原文与映射仍正确。 | [普通候选与正式正文](knowledge-notice-final-normal-knowledge.json)、[普通 HTML](knowledge-notice-final-normal-reading.html)、[截图](knowledge-notice-final-normal-exported.png)。无需处理。 |

读取的批准身份为 `10d326d` 下的根目录 `LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md`，尤其 W3、G1 的 A04/A06/A07，以及同版本 `workspaces/reviews/lifeweave-next-stage/review.md` 的 G1 成果/知识链路。候选基线 `5993005`，当前 `464306a6bbc5534dd604dae7e86a8a14d44f1519`；两者仅相差 `research_references.merge_references` 的 warnings 合并与对应数据库回归。当前已有文档等未提交修改保留，不作为批准事实。

定向读取了 `AGENTS.md`、独立交付复核协议、上述批准材料、Diff、`research_outputs.py`、`research_references.py`、Library、worker 接口和页面中的候选、正式阅读、Markdown、HTML 导出消费者。服务与脚本启动遵循 `docs/development.md`；旧独立脚本只用于确认环境入口，没有沿用旧结论。

本次运行命令：

```bash
.venv/bin/python docs/evidence/web-research/knowledge-notice-final-probe.py > docs/evidence/web-research/knowledge-notice-final-run.log 2>&1
npm --prefix web audit --omit=dev --json > docs/evidence/web-research/knowledge-notice-final-dependency-audit.json
```

[复核脚本](knowledge-notice-final-probe.py)创建随机数据库 `test_notice_final_4414ecd17c12`，使用本仓 PostgreSQL socket、55440 和 `lifeweave` 用户；Uvicorn 仅监听 8015，知识和执行目录独立。`LIFEWEAVE_LOCAL_WORKER=0`，真实模型命令设为 `/bin/false`，手动运行真实 worker 并注入固定结果执行器；报告数据没有手工 SQL 写入。复用候选现有 `web/dist`。8016 未使用，8010/8011 未操作。

[最终观察](knowledge-notice-final-observations.json)记录 54 项通过、无页面未捕获错误、主浏览器无失败 HTTP 响应；[服务/执行日志](knowledge-notice-final-run.log)无产品异常。[本次生产前端依赖审计](knowledge-notice-final-dependency-audit.json)报告 0 个漏洞；没有重跑无关模型恢复测试，也没有将该审计扩称为完整依赖安全认证。服务线程已退出、随机库已删除、临时根已删除，终态 `ss` 确认 8015/8016 均无监听。

首轮探针因把来源链接的 `target=_blank` 当作当前页跳转，等待超时，结果为 `not_proven`；[异常记录](knowledge-notice-final-first-attempt.json)和[日志](knowledge-notice-final-first-attempt.log)保留。只修正审查脚本以等待实际新标签，随后以新的随机库完整重跑得到本报告的 pass；没有修改产品来迁就验证。

证据边界：输入是受控 PDF 提取字符夹具，不是本次新解析真实 PDF 或验证论文语义；真实执行的是 worker HTTP 协议、数据库、浏览器操作和下载。网页接受由审查代理在测试空间点击，不代表用户接受正式研究内容。HTML 阅读版中的来源、图片和样式仍依赖原工作台在线，并非自包含离线包；本次打开及点击时服务在线，归档后已按要求清理测试服务和数据库。

## 追加范围：普通文字链接指向 PNG

**pass，实际加载版本 `69ba22f4c7d6902358f69cb938d1123d922e2505`。** 此项在原 464306a 复核完成后追加，不能把上文旧版本的检查当成图片链接修复证据。独立新进程重新加载该版本，读取 `464306a..69ba22f` 的 `/source` 路由差异及既有 `ResearchOutputs.asset`，在另一个随机测试库重新执行 worker 和浏览器检查。

| 新关闭条件 | 结果 | 亲自执行的动作与观察 | 证据与处理 |
| --- | --- | --- | --- |
| 普通 PNG 链接在全部四个消费者可用 | pass | 固定 worker 报告同时包含 `[普通图链接](figure.png)` 和嵌入图片。分别在事项成果、展开的知识候选、接受后的正式知识、实际下载后打开的 HTML 点击普通链接；浏览器真实新标签打开 `/source?path=figure.png`，图片解码 `naturalWidth=1`。含 NUL 与普通字符的两份报告均通过。 | [本次轨迹](knowledge-notice-final-image-browser-trace.zip)、[成果点击](knowledge-notice-final-image-nul-output-image-click.png)、[候选点击](knowledge-notice-final-image-nul-candidate-image-click.png)、[正式知识点击](knowledge-notice-final-image-nul-formal-image-click.png)、[HTML 点击](knowledge-notice-final-image-nul-downloaded-HTML-image-click.png)。无需处理。 |
| 复用图片读取责任，不改正文或来源映射 | pass | `/source` 图片响应与 `/assets`、固定 PNG 原始字节完全相等，`Content-Type=image/png` 且 `nosniff`；候选、正式知识、下载原文的正文及版本均一致。候选与正式映射保留 run 身份，普通文本来源点击仍正常。 | [新版本逐项观察及响应头](knowledge-notice-final-image-observations.json)、[新知识数据](knowledge-notice-final-image-nul-knowledge.json)。无需处理。 |
| 图片范围与类型保护 | pass | 对两个 run 分别实际请求：跨个人/团队空间返回 404；内容为文本的 `fake.png` 返回 409；`../figure.png` 与指向 `/etc/passwd` 的 `escape.png` 均返回 400，没有取得越界字节。 | [新版本边界响应](knowledge-notice-final-image-observations.json)。这些预期拒绝与浏览器正常操作中的错误分开记录。无需处理。 |
| 原 NUL 提示及同名引用歧义不回归 | pass | 在新版本完整重走候选、接受、下载，NUL 提示与无 NUL 反例保持正确；合并两个 run 后普通文本引用、PNG 文字链接、PNG 嵌入图片的三条歧义提示与一条 NUL 提示同时可见，无自动选择来源。 | [新合并知识](knowledge-notice-final-image-overlap-knowledge.json)、[新合并 HTML](knowledge-notice-final-image-overlap-reading.html)。无需处理。 |

命令为 `.venv/bin/python docs/evidence/web-research/knowledge-notice-final-image-probe.py > docs/evidence/web-research/knowledge-notice-final-image-run.log 2>&1`。[独立探针](knowledge-notice-final-image-probe.py)、[日志](knowledge-notice-final-image-run.log)和[新观察记录](knowledge-notice-final-image-observations.json)保留实际 Git 身份、随机数据库和每个动作结果。测试服务仍仅使用 8015，结束后服务、数据库和临时根均删除，8015/8016 无监听。

日常 8010 仅做过一次只读成果 API 查阅来定位真实报告中的 PNG 路径；没有写入、停止服务或在该实例进行本项浏览器验收。本追加项的实际加载版本由独立测试进程启动时固定，不将调用者的部署声明当作日常服务版本实测。真实论文链接的线上点击复核由主代理另行提供；本项证明的是新版本下完整产品链路与邻近保护。

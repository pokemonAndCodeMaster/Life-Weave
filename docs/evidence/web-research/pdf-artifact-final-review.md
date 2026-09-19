# PDF 字符存储与原始成果下载：独立交付复核

**fail — 候选 `5993005` 的知识候选和已接受知识丢失 NUL 阅读说明。**

在真实 Chromium 中，事项成果页可见“原始执行文本含不可显示的 NUL 字符”的说明，原始执行文本和阅读正文均可下载且字节正确。但从该成果提出知识候选，展开“阅读建议全文”，再点击“接受并更新知识原文”并进入知识页后，两处都不再显示说明；对应 API 的 `references.warnings` 都是空数组。知识正文仍包含替代字符 `␀`，读者失去其含义说明。本次复核只读实现，没有修改实现或审查单。

| 关闭条件 | 结果 | 亲自执行的动作 | 观察结果与证据 | 需要怎样处理 |
| --- | --- | --- | --- | --- |
| 完整 Worker 两种客户端；NUL 事件不终止；原始 JSON、字面转义及键碰撞保留 | pass | 自建确定性执行器，分别使用完整 `LifeWeaveWorker.execute_once()`、`ServiceWorkerClient` 和真实网络 `HttpWorkerClient`，后端为独立 PostgreSQL | 两轮 succeeded；事件 summary 可读；base64 还原事件与输入对象完全一致；嵌套数组、字面 `\\u0000`、NUL 键与字面 `␀` 键两个值均保留。见 [Service 实录](pdf-artifact-final-service-run.json)、[HTTP 实录](pdf-artifact-final-http-run.json) | 无 |
| 最终 result/result_payload 的 NUL 可恢复；原始下载和阅读下载各自版本一致；非 NUL 不变 | pass | 夹具有意让原始 result 带额外首尾文本，result_payload.report 只含研究正文；两路完整运行后经 HTTP 下载；再运行非 NUL 对照 | 原始下载精确等于 result 字节，未混为 report；`X-Artifact-Version=sha256:<实际字节哈希>`，ETag 为同一值加引号。阅读下载精确等于投影正文，其 ETag/版本等于其自己的哈希；非 NUL 无额外提示或原始下载入口。浏览器两种下载亦精确相等。见 [观测及响应头](pdf-artifact-final-observations.json)、[对照](pdf-artifact-final-http-control-run.json)、[浏览器原始下载](pdf-artifact-final-browser-raw.txt) | 无 |
| 浏览器成果页提示、原始下载；候选和接受后 warning 延续且来源/版本一致 | **fail** | 浏览器打开成果页，下载两种文本；提出 `审查/PDF字符证据.md` 候选，展开阅读，接受并打开知识页；下载知识并点击来源 | 成果页提示可见，下载正常。候选/已接受知识 API `warnings=[]`，阅读区也无 NUL 提示。原研究 runId、runVersion、相对来源链接、来源原文及知识原文件/下载版本都一致。见 [成果页](pdf-artifact-final-output.png)、[候选页](pdf-artifact-final-candidate.png)、[接受后页面](pdf-artifact-final-accepted.png)、[知识响应与浏览器正文](pdf-artifact-final-knowledge.json) | 修复引用合并时的警告传递，再从新进程复核候选阅读与已接受知识两个消费者 |
| 旧 environment 元数据、租约、跨空间和输入来源保护不退化 | pass（所测反例） | 先 running 上报无关字段 NUL，留下旧存储元数据，再成功上报不同的无 NUL 结果；伪造输入来源；无效租约上报 NUL 事件/结果；跨空间读运行/原始下载/研究投影及写事件 | 后续结果仍为正确 clean 文本且不出现错误阅读说明；selectedInputs/researchSupport/feedbackSnapshot/inputRecommendations 未被 worker 替换；错误租约请求被拒且事件未落库；跨空间读取 404、worker token 被拒。见 [边界实录](pdf-artifact-final-boundary.json)、[逐项状态](pdf-artifact-final-observations.json) | 无；这不是未覆盖鉴权路径的全面认证 |

根因定位：`src/lifeweave/research_outputs.py:108–113` 已把存储说明放入 `mapping['warnings']`，但 `src/lifeweave/research_references.py:26–40` 的 `merge_references()` 只遍历 links/images，丢弃了上游 warnings。它目前只留下自身生成的链接冲突警告。本次失败来自亲自取得的 API/页面结果，源码用于解释已观察的失败。

批准与候选身份：

- 批准来源：`10d326d` 的根目录 `LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md`，重点读取 G1/A04/A06/A07/A08/A09、W3 与验证标准；同提交 `workspaces/reviews/lifeweave-next-stage/review.md` 的“网页研究可用版”G1 工程方案。没有把候选审查单中的开发者完成说明作为事实。
- 原始基线 `032a029`；本轮针对差异 `7ee164b..5993005`，候选完整身份 `5993005f5a941935fc5e9e9a701b7e7c7cbde506`，启动前读取 HEAD。实现源码无未提交修改；已有及并行文档改动未修改或回滚。
- 已读取真实 owner：runtime worker、service、repository 事件存储路径、storage_text、artifact router、research_outputs、research_references、library 与网页成果/候选/知识消费者；按目标仓 AGENTS 与独立交付复核协议执行。

复现入口与环境：

```bash
cd /home/yyh/project/lifeweave
.venv/bin/python docs/evidence/web-research/pdf-artifact-final-probe.py > docs/evidence/web-research/pdf-artifact-final-run.log 2>&1
cd web
npm audit --omit=dev --json > ../docs/evidence/web-research/pdf-artifact-final-dependency-audit.json
```

[独立探针源码](pdf-artifact-final-probe.py)创建随机库 `test_pdf_final_1bb2f9b643dd`，所有知识、执行器、运行、对话、配置根隔离于 `/tmp/pdf-artifact-final-yszc0tr6`；新 Uvicorn 服务监听 `127.0.0.1:8015`，只复用候选源码和已构建 web/dist。浏览器使用已安装 Chromium 1208，运行无真实模型、付费调用或认证材料。页面写入只发生在自有夹具知识库。没有请求、写入或停止 8010/8011。

最终一轮 48 项观测中，4 项失败均是同一 NUL 说明在候选/接受后的 API 与浏览器丢失；其余所列具体观测通过。最终服务日志无 ERROR/Traceback，浏览器无未捕获异常。生产前端依赖审计为 0 已知漏洞，见 [审计输出](pdf-artifact-final-dependency-audit.json)；未宣称全仓依赖或完整 G1 再认证。

首次探针因 Playwright 默认浏览器版本未安装退出，改为显式使用本机已安装浏览器；第二次因探针 URL 缺斜杠退出，修正探针后重新以全新库完整执行，未修改产品代码。每次退出均删除自有数据库与临时目录。最终已确认数据库不再存在、临时根删除、8015 无监听。完整证据见 [运行日志](pdf-artifact-final-run.log)、[结构化观测](pdf-artifact-final-observations.json)、[浏览器轨迹](pdf-artifact-final-browser-trace.zip)。

# 来源编码修复独立复核：032a029

**结果：pass，限本次来源链修复及所列反例。** 前次复核发现的原成果复杂图片失败、知识来源编码失配和 `:2` 被当作文件名三个阻断，本次均从正式页面亲自复验通过。原成果、待审候选、正式知识、修订历史、下载 HTML 和下一运行快照保持同一来源归属。没有发现会推翻已有本机 G1 验收的新增回归；这不代表重新执行全部真实 AI 任务，也不代表 G2 或具体论文成果完成。

复核者未参与施工。批准身份为 `10d326d` 中根目录《LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md》第 13.1 节 A01—A09，以及同提交 `workspaces/reviews/lifeweave-next-stage/review.md` 末尾施工方案。候选为 `032a02971078efeb5bffce22018fd49ee345fcd9`，Diff 基线 `10d326d`。开始时存在 README、文档和 review.md 的未提交编辑，本复核未修改它们、产品实现或批准方案。

## 本次亲自取得的结果

受控成果包含普通、空格、中文、括号、已编码空格、引用式、百分号与字面 `%20` 文件名，共九张图片；文本来源另含 `:2`、锚点和引用式链接。所有文件真实写入所属隔离 run，使用正常 API 提交知识候选，然后从正式事项页展开、接受、跳转知识和下载。合成成果仅用于确定性反例，不冒充模型生成质量。

| 关闭条件 | 结果 | 亲自执行的动作 | 观察与证据 | 需要怎样处理 |
|---|---|---|---|---|
| A04：原成果复杂图片显示 | pass | 新 Chromium 打开事项成果，滚动使全部图片加载 | 九张图全部 `complete=true`、`naturalWidth=1`，没有加载失败提示；空格、中文、`%20` 和引用式原失败均消失。[DOM与尺寸](encoding-final-review.json) `candidate_browser`；[页面](encoding-final-candidate.png) | 无 |
| A04/A06：文本来源编码与行号 | pass | 在原成果、候选、正式知识、修订历史和下载 HTML 分别实际点击来源；共 35 次受控点击 | 每次弹页正文包含正确 run 身份与 `Independent review content.`；`:2` 请求目标为 `research/source.md`。空格/中文不再落入知识相对路径；`100%25.md` 对应 `100%.md`，`literal%2520.md` 对应字面文件名 `literal%20.md`。[点击结果](encoding-final-review.json) `candidate_actual_clicks`、`actual_clicks`、`revision_actual_clicks`、`download_actual_clicks` | 无；锚点/行号用于找到文件，未宣称浏览器定位到具体行 |
| A06：候选、正式知识、修订阅读保持来源和图片 | pass | 事项候选展开后页面接受；打开正式知识；从“修订与历史”重新展开已接受修订 | 三个知识消费者各九图实际可见，来源回到相同固定 run；代码块保持 Markdown 字面量。来源映射由 `ResearchOutputs.document_references` 生成，经 Library 传给页面共同的 MarkdownBody。[正式知识](encoding-final-accepted.png)、[各消费者记录](encoding-final-review.json) | 无 |
| A04/A06：下载内容可读且原文不变 | pass | 下载原文与 HTML，从 `file://` 打开 HTML，加载图并点击来源 | 原文逐字等于候选与正式正文；HTML 九图真正显示，复杂来源点击读到正确正文，依赖原工作台可访问的说明可见。[下载HTML](encoding-final-controlled-reading.html)、[原文](encoding-final-controlled-original.md)、JSON `raw_unchanged` | 不是离线资产包；受控服务回收后其临时来源不可访问，证据采于回收前 |
| A04/A06：已经采纳的真实旧知识无需重写 | pass | 8011 只读打开 `研究/阳台采光因果解释.md`，实际点击“来源记录”；下载后再从 HTML 点击 | 两次均读到 `gzrun-20260919-091738-82581407` 的真实来源、材料版本和范围；正式版本仍为 `5de064f9225d0e4fba0aace4fcf5e113188f326444637e66edc7c9f471533615`，原文下载相等。[真实页面](encoding-final-real-knowledge.png)、JSON `real_accepted_source`、`real_html_source` | 无 |
| A07：新任务拿到相同当前版本与来源 | pass（准备与传递） | 新建第二个研究事项，推荐找到已采纳知识；正式 `/runs` 入队，读取固定输入及 prompt；调用正式 worker 材料写入方法 | 推荐、固定输入、材料 manifest 的映射相等，版本与正式知识相等，prompt 包含全部引用目标。行号映射不再错误传下去。[快照与manifest](encoding-final-review.json) `downstream*`、`checks` | 本次不调用模型；模型是否正确采用复杂来源仍为 not_proven，既有真实内容复用证据见下表 |
| 多 run 同名引用不误归属 | pass | 第二 run 提交包含两轮正文的合并候选，页面展开 | 冲突链接/图片映射为空，页面显示“多个来源使用相同相对引用”；待审候选未改变正式旧文及其引用。[歧义结果](encoding-final-review.json) `ambiguous`、`ambiguity_visible`、`stable_formal_after_draft` | 用户仍需从各自成果查看歧义来源，不宣称自动消歧 |
| 普通知识链接、代码与外链保持语义 | pass | 点击新增 `other.md`；检查各 Markdown 消费者 DOM | 到达 `研究/other.md` 并出现“普通知识目标”；代码示例不变，未生成代码图；外链仍指 `https://example.org/`，未访问外站。[记录](encoding-final-review.json) `ordinary_knowledge_target`、`checks.code_literal_preserved` | 无 |
| 隐藏文件、跨 run/空间、绝对路径保护 | pass（所列反例） | 请求 `.env`、隐藏 research 子文件、`..`、绝对路径、跨 run 与 team 下 personal run | 来源非法路径 400，资产非法路径 409，跨空间 404；明确允许的 `.runtime/research/allowed.md` 返回 200。没有通过放开私密目录解决编码。[HTTP结果](encoding-final-review.json) `path_guards`、`cross_workspace` | 无 |

## 其余批准条件与既有证据边界

本次核对原始记录和本次 Diff，未用之前报告中的“pass”覆盖前次反例，也未把未重跑动作写成亲自执行。`032a029` 产品改动只有引用解析与 MarkdownBody，另有对应测试；下列原有运行/事务/恢复证据未被本次修复改变。

| 关闭条件 | 结果 | 本次核对或执行 | 证据及边界 | 需要怎样处理 |
|---|---|---|---|---|
| A01：问答、只记录、明确委托 | pass（既有证据范围） | 核对真实问答 `receipts=[]`、自然只记录唯一 idea 且无 item/run、研究委托实际 run；本次仅只读重新打开复用会话 | [真实问答](knowledge-reuse.json)、[只记录](record-auto.json)、[委托](real-browser.json)；[原独立受控动作](independent-checks.json)证明幂等/分流边界 | 本次未新调用语义模型 |
| A02：目标一致与旧输入 | pass（既有证据范围） | 核对目标修改提案无新 run，接受后 v2 目标与 continuation 一致；原独立旧版本接受 409、旧 run 保留旧目标 | [真实目标记录](context-change.json)、[原独立动作](independent-checks.json) | 本次未修改真实目标 |
| A03：自动选材与实际使用 | pass（已有生活研究切片） | 核对两轮真实 events 的成功读取 SKILL.md，首轮读取冻结知识；新受控任务的推荐和输入本次亲测一致 | [真实执行事件](real-execution-events.json)、[本次快照](encoding-final-review.json) | 不证明通用语义召回或具体论文研究质量 |
| A05：定位反馈与同事项修订 | pass（既有证据范围） | 核对 feedback 的旧 run/版本/选段，修订结果保留原解释并增加标明“假设”的浇水反例 | [真实两轮成果与反馈](real-browser.json)、[原独立选段记录](independent-checks.json) | 本次未发起新修订模型运行 |
| A06：拒绝/源版本冲突不覆盖 | pass（既有事务证据；本次采纳亲测） | 原独立记录含拒绝原文不变及过期接受 409；本次亲自页面接受并验证未审另一候选不改正式文 | [原独立动作](independent-checks.json)、[本次记录](encoding-final-review.json) | 本次未重做拒绝/冲突全套 |
| A07：另一新问题真实复用 | pass（已有内容复用） | 只读新浏览器会话中实际回答含浇水反例；核对 sources 版本与正式版本；复杂来源准备链本次亲测 | [真实复用](knowledge-reuse.json)、本次 JSON `real_reuse_text` 与 `downstream` | 复杂来源被新模型实际采用为 not_proven；本次无模型调用 |
| A08：新会话与重启接续 | pass（新浏览器亲测；重启沿用受控证据） | 本次新 Chromium 打开持久知识/复用会话；核对独立重启记录中处理中 turn 明确失败、旧事项与反馈仍在 | [重启记录](independent-follow-checks.json) | 本次未重启 8011 |
| A09：取消、失败与不确定结果 | pass（已有受控边界） | 核对取消保留原话、解释失败、响应丢失刷新、跨空间切换与同请求重试只有一个 turn | [原独立动作](independent-checks.json)、[不确定结果记录](independent-edge-checks.json) | 非真实外部写入的网络故障验收；本次未新增外部写入 |

## 身份、执行与副作用

- 遵循 [独立交付复核协议](/home/yyh/project/omni-brain/.agents/skills/review-work/references/independent-delivery-check.md)，并参考 `vue-best-practices`、`web-design-guidelines` 检查实际 Vue 消费者。定向读取 ResearchOutputs、research_references、Library、TaskSources、runtime prompt/worker manifest、MarkdownBody、ResearchOutputPanel、ResearchKnowledgeReview、KnowledgePage、readingExport 与候选 Diff。
- 命令：`.venv/bin/python docs/evidence/web-research/encoding-final-harness.py`。脚本基于前次可重放 harness 增加本次百分号、括号、引用式来源与真实点击，不沿用旧执行结果。[本次脚本](encoding-final-harness.py)、[本次完整JSON](encoding-final-review.json)。
- 新建数据库 `test_lifeweave_encoding_0037440f33cc`，临时根 `/tmp/lifeweave-encoding-review-gqvj0rm7`，8014 自有 uvicorn 线程，`LIFEWEAVE_LOCAL_WORKER=0`。除结束状态与合成成果夹具外，使用真实 PostgreSQL、正式 API、正式页面接受和下载；不冒充真实执行器成功。
- Chromium `/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome`，全新上下文。受控五个阅读消费者共观察 45 个图片实例，全部 `naturalWidth>0`；35 次受控来源实际点击全部正文正确。浏览器 `pageerror=[]`。不能以此替代未覆盖的全站可访问性或性能验收。
- 8011 为调用者拥有，仅 GET 和浏览器只读，未停止或写入。8010 日常 Qwen 研究未访问、写入或停止。本次没有任何真实 AI 调用。
- 自有 uvicorn 已正常停止，8014 端口可重新绑定，临时根已不存在；数据库已 DROP 并通过 `pg_database` 只读查询确认不存在。没有使用 `pkill` 或停止他人进程。
- 亲自执行 `web/` 中 `npm audit --omit=dev --json`，生产依赖已知漏洞零。[结果](encoding-final-dependency-audit.json)。未执行 Python 全依赖审计；未以已报告的 64 Python / 29 前端测试及构建结果作为本报告的业务证明。

此前 [reference-fresh-review.md](reference-fresh-review.md) 保留为 `cd8c709` 的失败事实，本报告仅针对上述候选关闭其三个编码阻断。没有待开发者处理的新增阻断。

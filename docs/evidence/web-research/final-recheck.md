# G1 独立最终复核：d69b257

结论：**fail**。真实研究和反馈修订可在新浏览器阅读，原报告来源接口修复有效；但同一成果采纳为知识后，其相对来源链接失去运行归属，正常知识入口点击“来源记录”报 409。该问题直接影响已承诺的来源可读与知识再用，不能用测试通过覆盖。

本复核员未参与实现。批准依据为 Git `10d326d` 中根目录《LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md》第 13.1 节 A01—A09，以及 `workspaces/reviews/lifeweave-next-stage/review.md` 最后施工方案；候选为 `d69b2577cbc4ca95008ce116f8dd94da8586c383`，Diff 基线为 `10d326d`。工作树已有文档改动未修改。本次只新增独立证据。

## 会改变接受结论的失败

1. 新 Chromium 打开 `http://127.0.0.1:8011/lifeweave/personal/knowledge?source=local&path=研究/阳台采光因果解释.md`。
2. 正文来自真实研究修订稿，保留“来源记录” `.runtime/research/gzrun-20260919-091738-82581407/sources.md`。
3. 点击该链接，KnowledgePage 的 `follow` 把它解析成知识路径 `研究/.runtime/research/.../sources.md`，发往 library/document，得到 **409**。页面显示 `Request failed with status code 409`。
4. 与之对照，从对话当前成果点击同一“来源记录”，会打开正确 run source API，返回 200 且正文可读。

定位：`src/lifeweave/research_outputs.py:propose_from_run` 复制内容并追加 provenance，没有保存相对引用基准；`web/src/features/lifeweave/pages/KnowledgePage.vue:follow` 及不传 sourceBase/assetBase 的 MarkdownBody 按知识文件处理。`ResearchKnowledgeReview.vue` 也直接渲染候选正文，应一起检查其链接/图片。建议让知识候选、正式知识和修订预览保留正确的运行引用身份；修复后必须从这三个实际消费者点读，并保留既有知识间相对链接行为。不要扩大私密路径白名单。

证据：[失败截图](final-recheck-knowledge-failure.png)、[真实 HTTP 409](final-recheck-knowledge-http.json)、[知识正文与链接](final-recheck-knowledge.json)。

## A01—A09 对照

| 条件 | 结果 | 本次亲自执行和观察 | 仍需处理 |
|---|---|---|---|
| A01 问答/只记录/委托 | pass（结合既有真实执行证据） | 新浏览器看到委托真实对象及另会话问答无关联事项；重跑临时数据库分流/去重测试，问答不建项、只记录不解释/执行、重复请求返回原动作。真实分流提交由主代理先前操作，本次未冒充再次调用模型。 | 无新增发现 |
| A02 当前目标一致、旧输入保留 | pass | 只读 API 当前目标为日常因果判断清单；真实旧 run 保留原研究上下文。重新执行并通过旧上下文处理冲突测试。对照 `context-change.json` 中用户界面采纳回执。 | 无新增发现 |
| A03 自动材料/方法实际使用 | pass（本研究切片） | 直接从运行 events API 读两轮事件，存在完成的读取方法 SKILL.md 命令；首轮读取已冻结知识。真实报告明确区分事实、假设、推断及来源。 | 本研究是临时生活观察，不能冒称真实论文精读完成或泛化认证 |
| A04 长文/公式/图片/引用 | **fail** | 新 Chromium 对话可读长文、表格、公式；点击原报告来源 200。下游知识页面同一来源点击 409。图片边界测试通过，但本真实研究无图片，不冒称本次亲见真实研究图片。 | 修复知识端引用基准后再验；已有受控 PNG 浏览器证据与真实研究分别标识 |
| A05 定位反馈并修订全文 | pass | 新浏览器真实修订报告包含新增浇水反例、三项分解，并保留原观察/潜在结果/原始长势/局限；明确列出反馈身份。重新执行输入快照测试证实 feedback anchor/前轮成果进入新运行且旧成果不变。 | 无新增发现 |
| A06 知识接受/拒绝/冲突 | **fail（引用完整性）** | 亲读已接受正文，真实采纳文存在；重跑临时数据库接受/拒绝/冲突/合并及原子回滚测试均通过。但接受正文无法跟随其来源链接，不能认作完整来源保留。 | 同 A04；不应绕过受审流程改原文救场 |
| A07 新问题复用 | pass（内容复用） | 新 Chromium 打开另会话，回答实际采用已接受知识中的浇水反例，正确区分假设和实际观察，注明两篇全文快照；来源页正文与回答一致。 | A04/A06 来源链接问题仍限制整体接受 |
| A08 新会话/重启接续 | pass（新浏览器接续） | 全新浏览器直接进入持久会话，能读目标关联、两轮当前/历史成果、反馈修订和下一步目标提案；只读 continuation 当前目标与运行一致。受控恢复测试通过。 | 本次未停止/重启主代理 8011，不冒称亲自重启 |
| A09 取消/失败/不确定结果 | pass（受控边界） | 临时数据库测试亲自重跑：取消后重复请求不重新执行，解释失败无业务回执，启动恢复把未完成轮次标中断；新成果失败保留历史成果。 | 非真实外部网络写入验收；该路径未新增外部写入 |

## 本次执行与边界

- 实际读取源码：conversation router/models/tests、ResearchOutputs、run source 路由、MarkdownBody、KnowledgePage、ResearchKnowledgeReview、真实执行事件 API、相关知识及上下文 API。
- Chromium：本机 Chromium 1208，Playwright 新上下文，真实入口为主代理拥有的 8011；所有访问均为 GET/浏览器只读，未修改其数据库、知识或运行目录。
- `LIFEWEAVE_TEST_DB=1 .venv/bin/pytest -q tests/test_conversations.py tests/test_research_outputs.py`：**10 passed**，随机临时 PostgreSQL 库自动清理。语义解释和结束状态为受控夹具，不当作真实模型。
- 真实来源保护反例：`.env`、`.codex/auth.json`、隐藏 research 子文件、父级穿越、绝对路径、跨 run 路径均 400；跨空间 run 为 404；专用 research 来源为 200。见 [路径反例](final-recheck-paths.json)。源码另检查解析后的路径和 repo 根目录未越界；新增修复未发现放开隐藏认证或跨 run 数据。
- [新浏览器观察](final-recheck-browser.json)、[真实输入/方法事件读取](final-recheck-inputs.json)；新浏览器主要对话与再用页无 pageerror。知识引用点击有预期捕获的失败 409。
- 未停止任何既有服务，未接触 8010 日常库或 8013 独立复核服务，未改实现、方案或用户知识原文。

G2 的时间块、持续发现、方法对照，多人权限和远程 ChatGPT 均不在本次 G1 通过声明中；GSSM 身份不明不阻塞本复核。

# 网页研究可用版独立交付复核

**结果：pass（最终代码候选 `cd8c709`，限本机 G1 网页研究可用范围）。** 本复核先后发现成果页来源 400、已接受知识来源 409 两项阻塞，分别由 `d69b257`、`cd8c709` 修复后亲自复验通过。真实委托、同事项反馈修订、受审知识与另一任务复用、重启和不确定请求恢复均有业务后果证据；不据此宣称 G2、多用户部署或具体论文成果已完成。

复核者没有参与本轮施工，先从批准前提交 `10d326d` 读取根目录《LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md》的 G1/A01—A09，以及该提交 `workspaces/reviews/lifeweave-next-stage/review.md` 最后施工方案。没有把工作树新增完成说明当作批准事实。最初代码候选 `0e574e4c27b03fdb60a1a819c964e824b265128f`，随后复验 `d69b257` 的来源读取修复和 `cd8c709` 的知识引用修复；Diff 基线均为 `10d326d`。

**证据边界：** 8013 是本复核者创建的独立 PostgreSQL 临时库和知识根，使用明确标注的受控解释器，禁用本机 worker。该环境亲自操作真实 HTTP、数据库和 Chromium，验证产品动作与失败边界；成果正文是显式合成 fixture，不能证明真实模型质量。8011 的真实 Codex 两轮运行由主代理通过产品发起，本复核者只读重开页面、来源、执行轨迹和知识回答检查其后果，没有发起或伪造真实 AI 运行。下面区分这两种证据；验证者在临时库操作“接受”不等于用户接受正式成果。

| 关闭条件 | 结果 | 亲自执行的动作 | 观察结果与证据 | 需要怎样处理 |
| --- | --- | --- | --- | --- |
| A01 问答、只记录、委托及幂等 | pass | 新 Chromium 从 `/lifeweave` 首进；问答；选择只记录；同请求重发、换内容重发；核对真实自然问答和委托回执 | 问答无事项，记录仅 idea；重复返回同一 turn，换内容 409；真实知识问答 `receipts=[]`，真实委托有 run。见 [独立动作](independent-checks.json)、[真实问答](knowledge-reuse.json)、[真实委托](real-browser.json)、[真实自然只记录](record-auto.json)：`mode=auto`、唯一 idea 回执、无 item/run | 不把受控解释器记成语义质量证明 |
| A02 目标提案、冲突和旧输入 | pass | 从关联对话提出目标；接受另一提案后用旧版本接受；读取新事项和旧 run | 提案未自动改变目标，过时接受 409；当前目标一致，旧 run 保留旧目标。对照主代理真实自然目标提案/页面接受证据：[独立动作](independent-checks.json)、[真实目标变更](context-change.json) | 无 |
| A03 自动选材、版本、真实使用 | pass | 在第二个非论文事项发起受控委托并检查固定输入；逐条核对真实执行事件与正文 | 自动带入独立已接受知识的当前版本。真实 Codex `cat SKILL.md` 成功，首轮 `cat` 发布知识成功，后续产物与实际材料相符；不是只有 selectedInputs。见 [真实执行事件](real-execution-events.json) | 仅证明本次真实研究范围，不宣称通用语义召回质量 |
| A04 完整正文、公式、图片、引用 | pass | 阅读长 fixture 末尾、表格代码、实际 PNG、下载；打开真实修订稿来源及 JSON 核对清单 | PNG `naturalWidth=1`，不是只查 img 存在；真实稿 35 个 KaTeX 节点。原来源 400 修复后 200；JSON 的 5 个文件逐个 HTTP 读取，字节数及 SHA-256 均吻合。见 [修复复验](independent-source-fix-checks.json)、[清单校验](independent-manifest-checks.json) | 保留原失败记录，不改写真实报告 |
| A05 同事项选段反馈与完整修订 | pass | 在成果正文选中训练数据段，保存反馈；检查下一 run；重开真实第二轮成果 | anchor 包含旧 run/版本/段落，新输入含反馈及完整前轮正文；真实修订稿增加明确标为假设的浇水反例，仍保留观察、反事实、原长势反例和边界。见 [独立动作](independent-checks.json)、[两轮真实结果](real-browser.json) | 无 |
| A06 知识接受、拒绝、冲突 | pass（原引用阻塞已修复） | 从成果提出知识，经网页接受并打开知识正文；拒绝另一候选；外部编辑后接受过期候选 | 接受写入唯一原文并含 run 来源；拒绝不改；过期接受 409 且新原文保留。原知识来源失败经 `cd8c709` 修复；亲自验证候选预览和已接受知识均显示真实 PNG、来源回到固定 run，代码块及普通同目录链接不变。见 [动作证据](independent-checks.json)、[下游修复复验](independent-downstream-checks.json) | 无 |
| A07 另一任务复用当前知识并注明来源 | pass（原引用阻塞已修复） | 创建另一非论文事项，自动选材入队；重开真实新问题回答，核对来源版本与已接受版本 | 独立输入实际含 `WINDOW-42`；真实回答采用浇水反例并注明两篇知识，接受版本与 sources 版本一致。修复前已接受的原文/版本完全不变，正式知识页来源现为 200；下一运行材料快照亦携带同一固定引用映射。见 [真实复用](knowledge-reuse.json)、[下游修复复验](independent-downstream-checks.json) | 无 |
| A08 刷新、新浏览器、服务重启 | pass | 刷新原对话；新浏览器打开旧事；SIGKILL 自己服务处理中进程并同库重启 | 原话可恢复；中断 turn 标失败且不自动重发；目标、反馈、旧成果仍可读。见 [重启复验](independent-follow-checks.json) | 无 |
| A09 取消、失败、不确定结果 | pass | 页面取消受控处理中 turn；引发解释错误；服务器已保存 turn 后丢 HTTP 响应，刷新、切团队再切回并重试原请求 | 取消/失败保留原话；未确认请求保留内容、模式和 requestId，个人请求未进入团队，最终只有一个 turn。见 [不确定结果](independent-edge-checks.json) | 无 |

原始阻塞及复验：

1. `0e574e4` 的真实修订稿两条 `.runtime/research/...` 来源在成果页请求 `/runs/<id>/source`，均返回 400。复核者亲自 HTTP 观察见 [原失败](independent-source-link-original-failure.json)。施工方 `d69b257` 仅开放受控研究子目录并检查解析后路径；本复核者再次用浏览器点来源/核对清单，200，原成果哈希不变。自行构造的其它隐藏目录、符号链接映射到隐藏文件、绝对路径、`..` 及跨空间路径仍被拒绝。[复验明细](independent-source-fix-checks.json)
2. `d69b257` 下，从真实知识复用回答打开 `研究/阳台采光因果解释.md`，再点“来源记录”，请求变成 `/library/document?path=研究/.runtime/research/<run>/sources.md`，返回 409。原因是成果内容被作为知识正文保存后，`KnowledgePage`/`MarkdownBody` 未持有原 run 的引用上下文，相对 Markdown 链接被解释成知识目录。此为第二个独立发现的阻塞，见 [失败请求](independent-knowledge-link-failure.json) 与 [页面](independent-knowledge-link-failure.png)。`cd8c709` 利用既有候选的 run/version 归属生成引用映射，成熟 Markdown AST 仅识别实际引用；原始知识不改写。复核者亲自验证旧真实知识恢复、新图文候选预览及接受后知识均可读，带空格 PNG 的 `naturalWidth=1`，来源内容为正确 `SOURCE-51`；代码块 `[example](relative.md)` 原样保留，另一篇普通知识 `SIBLING-91` 仍能打开。[复验明细](independent-downstream-checks.json)
3. 追加两轮成果同名 `research/source.md` 的反例：合并候选及接受后的知识均显示相同冲突警告并移除歧义自动映射，没有把第一轮来源静默换成第二轮；两个阅读消费者使用同一结果。实际下载并从 `file://` 打开 HTML 阅读版后，图片仍显示、来源 200，原 Markdown 下载逐字相等。HTML明确依赖原工作台可访问，未声称完整离线资产包。[冲突与导出复验](independent-overlap-checks.json)

本次运行入口及副作用：

- 安全入口为 `.venv/bin/python`，受控 harness 位于本复核者 `.runtime/independent-web-review/`；只创建随机库 `test_lifeweave_review_2995015394b8`，8013，知识与执行目录同名隔离根。`LIFEWEAVE_LOCAL_WORKER=0`，无真实模型调用、日常库改写或外部写入。
- Chromium 为 `/home/yyh/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome`，Python Playwright 亲自执行页面操作；桌面与 390px 手机首进无水平溢出，无页面脚本错误。恢复验证使用明确归本复核者拥有的 PID `824091`，没有操作 8010 或主代理 8011。
- `web/` 执行 `npm audit --omit=dev --json`，生产依赖已知漏洞 0。没有为复核修改产品代码、批准方案或根 review.md。
- 源码定向读取覆盖 Conversations/Repository/Interpreter、TaskSources、Runtime 输入/回报/来源读取、ResearchOutputs、Library，以及对话/成果/知识正式前端消费者。Vue 与页面部分参考 `vue-best-practices`、`web-design-guidelines`，未修改组件。
- 已停止最后一个自有服务 PID `843146`，删除随机临时数据库并核对不存在，回收自有 `.runtime/independent-web-review/`。8010、8011 未被本复核者停止或改写。见 [环境与回收](independent-environment.json)。主要复核脚本保留于 [independent-harness](independent-harness/)，其受控 fixture 不代表真实模型；需要重放时在新的临时库重建。
- 执行命令包括 `PYTHONPATH=. .venv/bin/python <harness>/application.py`（8013）、随后 `check.py`、`edge.py`、`follow.py`、`source_check.py`、`downstream_check.py`、`overlap_check.py`。后两项新增验证在 `cd8c709` 重启自有服务后执行；没有用旧服务冒充最终候选。真实 AI 部分读取并核对 `real-browser.json`、`real-execution-events.json`、`context-change.json`、`knowledge-reuse.json`、`record-auto.json`，并经主代理最新只读 8011 服务亲自打开来源和知识。

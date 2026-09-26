# 当前完成情况

核对日期：2026-09-27。本页描述当前可用范围。历史阶段的测试数量、失败与修复记录保留在[历史状态](history/status-through-20260926.md)和[证据目录](evidence/README.md)，不作为当前能力的累计完成率。

LifeWeave 是一套本机单用户工作台。个人和团队是隔离的内容空间，不是多人账号。已有真实研究、持续事项、人工主导的能力试验；开发自用、自动进化和远程团队使用尚未形成完整体验。

| 用户现在能做什么 | 证据与适用范围 | 仍不能依赖什么 |
| --- | --- | --- |
| 在网页记录、讨论、安排和继续事项，保存背景、反馈与成果 | 两篇论文研究经过真实网页与 Codex 运行；[研究证据](evidence/web-research/README.md) | 自主多 Agent 编排、可靠长期排程与自动提醒 |
| 阅读研究正文、公式、图片和引用；下载含资产的 ZIP；继续讨论两篇研究 | [归档与跨文章证据](evidence/research-archive/README.md) | 报告成功不等于论文结论正确或用户已接受；所有事项与知识并未同步到远端 |
| 只读阅读项目当前文档，按来源筛选、阅读全文并在委托中固定实际选用版本 | 项目规范清单见 [当前来源](current-sources.json)；历史引用可跳转 GitHub 仓库档案；[候选环境实际阅读](evidence/project-development/README.md) | 历史正文不作为当前知识搜索结果；没有自动事实本体、跨来源知识图或大规模语义索引 |
| 管理本地 Markdown、提交修订、比较和接受；查看同源 Markdown 引用 | [知识关系证据](evidence/personal-platform-evolution/README.md) | 外部来源的修订不能直接在产品里覆盖原仓正文 |
| 创建 Skill/Agent/Harness 候选，围绕事项运行评测、看轨迹和工作样例，并按同标准再评 | 两次内部窄任务真实 Codex 运行；临时数据库和页面验证见[评测证据](evidence/personal-platform-evolution/README.md) | 不能自动创建、优化、合并能力；实施者判定通过不等于用户验收或跨领域有效 |
| 在个人、团队空间调整首页五张卡片 | [桌面与手机页面证据](evidence/personal-platform-evolution/README.md) | 任意组件、拖拽或自然语言改布局 |
| 使用正式 CLI 查找、接续、反馈事项；已有本机 Codex 会话可主动关联并上报阶段，明确绑定且 Hook 受信任后可记录部分原生工具/生命周期元数据 | [真实 Hook 烟测](evidence/development-agent/hook-smoke.md)、[使用步骤](../README.md#在新的本机-agent-会话接续) | 原始命令和输出不上传；只读沙箱可能阻断本机 HTTP，Hook 可能被跳过，未绑定会话不追踪；人工上报不能冒充原生事件 |
| 在需求/修复事项中提交开发委托，分开查看只读方案、独立审阅或自检、可写实施的 Run 和隔离工作树差异 | [正式 LifeWeave 仓网页委托](evidence/development-agent/live-project-run.md)、[Codex 小仓执行](evidence/development-agent/README.md)、[OpenCode 小仓成功及后续反例](evidence/development-agent/opencode-chain.md)及数据库/HTTP 回归；前端类型检查和构建通过 | 正式仓只核验有界 CLI 增量；OpenCode 后续只读阶段被发现写入隔离树，现已从开发页暂停，待修复回归；复杂工程质量、外部会话自动逐工具采集仍未验证，结果不会自动合入原仓 |
| 查看开发插件目录、按空间停用新调用，在事项展开实际调用和同事项 Run，并对真实插件调用作显式评测 | [插件实现说明](plugin-system.md)；正式 Codex 自用委托经过方案、独立审阅、隔离实施与页面核查；数据库和 Vue 回归覆盖空间隔离、版本、异常事件和评价 | 第二任务复用与用户业务验收尚未完成；人工评价不能由技术执行成功自动代替 |
| 在项目知识页查看带来源版本的实现／验证关系，逐篇请求 Notion 镜像并查看上次回读状态 | `docs/knowledge-relations.json` 的显式关系及版本核对；单篇发布沿用原镜像器的版本冲突、远端冲突与全文回读检查 | 当前仅登记了插件说明的两条关系，其他文档无断言；产品后端 Notion 凭据未配置，不能报告线上自动发布成功 |

Codex 已有正式仓的真实成功记录。OpenCode 曾用 `--model opencode/mimo-v2.5-free` 和本机账号副本完成小仓三阶段及 7 项 unittest，但下一次只读方案的子代理写入了隔离树，故该开发选项当前暂停；成功一次不代表权限边界可靠。执行快照记录的是传给 CLI 的模型参数，尚无来自上游提供方的模型身份回执。运行事件可查看，但不等于 Agent 内部每步工具调用均可观察。选 Git 仓库时固定提交并在独立目录运行，未提交改动不会自动带入，代码产物也不会自动合回原仓。

启用后的新研究报告继续自动归档到 GitHub；Linear 仅保留历史只读。Notion 单向镜像已实现配置、项目文档逐篇扫描、报告投递与 Markdown 回读；同版本复查也读取远端并检查冲突。但后台令牌及根页面尚未配置，故没有真实 Notion 自动镜像完成证据。用户完成浏览器授权后，本机 Codex 新会话通过直接的 `mcp__notion__notion_fetch` 读出项目入口标题；[读取记录](evidence/development-agent/notion-mcp-smoke.md)证明交互式 Notion MCP 可用，与后台镜像授权不同。本机停机时不能生成或上传新报告。飞书入口、远程 ChatGPT、多成员身份、各自模型连接、时间容量与日历、周期评测及正式自动知识回写均未实现。[归档维护说明](research-archive.md)区分远端已确认版本与本地待传状态。

当前服务已让项目知识可找、可读，原文变更后的新版本能被下一次读取；外部开发报告也能通过同一事项接续。[正式服务的桌面与手机核查](evidence/project-development/README.md)覆盖这两条阅读路径。正式事项 `item-58363ef3851142d8` 已记录 GitHub 提交、测试、页面证据和后续档案导航修复，目前待用户使用验收。本轮以后绑定的 Codex 会话可以用受信任 Hook 记录支持的事件；更早的代码改动只有 Git 差异与主动上报，无法补造实时 trace。后续重点是在真实复杂开发中从任务起点绑定、核对工具覆盖和验证反馈怎样改善下一轮。阶段和验收条件见[建设路线](roadmap.md)。

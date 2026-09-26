# 插件目录与开发过程：首个可运行切片

日期：2026-09-27。设计依据是 [Notion 阶段计划](https://app.notion.com/p/3e7af682864481d6a5f3c7f7b8542bc0)与[阶段 1 施工方案](../workspaces/reviews/plugin-foundation-stage1/review.md)。本文只描述当前代码已经接入的边界；后续阶段仍按该方案推进。

## 使用者怎样看

打开“能力与评测 → 插件目录”，可见每项能力的身份、版本、依赖、可运行原因和本空间启停状态。点“查看近期使用”能从插件回到实际事项。停用阻止该空间的新调用，不删除历史；已在执行中的外部进程不会被强行中止。Codex 可用性首先取决于本机 CLI，真正账号和模型仍以运行结果为证。OpenCode 在开发委托中继续暂停。

事项的每次实际调用可展开固定插件版本、实现摘要、开始结束时间和受限的输入输出引用。能定位到 Run 的调用可继续看同一事项的阶段与原生事件；插件调用 API 只返回受限结构字段、知识数量和来源版本，不传提示词、命令、路径、未知引用字段和自由文本错误，页面再做一次白名单显示，不把原始事件摘要直接显示出来。嵌套调用的后续记录使用实际时钟，早期同事务记录的时间粒度不足，不能据其计算耗时。Worker 已报告 Run 终态但缺少执行器结束事件时，调用标为“中断／结束未观测”，不从 Run 成功反推插件成功。

已结束的调用可从事项打开“评价这次调用”，填写本次任务与通过标准，再由人判断。开发主调用在阶段 Run 结束且通过该阶段检查后才从“已受理”变为成功；未通过检查则记录失败。评测固定插件 ID、版本、实现摘要、调用和可选 Run；一个 Run 可分别评价组合插件和执行器插件，失败和改进建议保留。带 Run 的“通过”仍须同一次 Run 的人工接受证据；无 Run 的脚本调用须真实成功结束并由人说明通过理由。目录详情可反查该插件的显式评测和改进；调用成功本身不构成评测通过。

在需求或修复事项的“开发 Agent”页发起委托后，展开“插件计划与实际调用”。计划与绑定在委托创建时固定，实际调用只由服务端真正进入对应操作或受信任执行机进入 `executor.run` 边界时记下。一个条目有计划但没有调用，页面显示“尚无实际调用”，不推断执行器内部发生了什么。旧委托没有插件计划，会明确显示历史边界。开发页继续使用原 Run 和原生事件；插件过程接口故障时不遮断原有记录。

目前可见的组合是 `lifeweave.development` → `lifeweave.context` → `lifeweave.knowledge` 的推荐和选定正文读取、`lifeweave.method.<原方法ID>` 的版本固定，以及 `lifeweave.execution.codex` 和 `lifeweave.checks.repository`。方法的“已绑定”仅证明材料被选入快照，不证明模型遵循全部步骤。Run 环境中的 `contextPack` 含编译器版本、背景版本、来源版本和最终提示词 SHA-256；提示词正文仍由原 Run 快照保存。推荐会扫描受管来源并记录候选引用；选中的正文另存于原能力快照。

## 实现与数据归属

- [core.py](../src/lifeweave_plugins/core.py) 管内置描述、依赖校验、实现摘要与调用边界；[service.py](../src/lifeweave_plugins/service.py) 管空间状态、固定计划、绑定核验和计划／实际投影。
- [013_plugin_foundation.sql](../migrations/013_plugin_foundation.sql) 新增固定计划、调用与空间启停三张表；[014_plugin_evaluations.sql](../migrations/014_plugin_evaluations.sql) 让原评测表按真实插件调用记录判断，并允许同一 Run 有多个评测目标；[015_development_call_completion.sql](../migrations/015_development_call_completion.sql) 用旧委托的终态与实际阶段进展保守补齐组合调用结果。既有事项、开发委托、Run、事件和知识正文仍由原模块负责。项目知识原文继续在 Git，本地知识原文继续在 Markdown，Notion 仍是镜像。
- [development.py](../src/lifeweave/development.py) 仍决定方案、审阅、自检、实施与只读检查何时推进；插件绑定不接管业务状态机。[Runtime](../src/lifeweave_runtime/service.py) 在创建 Run 时固定上下文和真实所选材料；[Worker](../src/lifeweave_runtime/worker.py) 紧贴执行器调用上报开始／结束事件。受信任租约、Run 事件和插件调用记录共同构成受管边界证据。
- `GET /api/lifeweave/{space}/plugins`、`GET /plugins/{id}`、`PUT /plugins/{id}/enabled`、`GET /plugins/{id}/calls` 与 `GET /items/{itemId}/plugin-process` 是读取和控制入口。插件评测沿用 `POST /evaluations`、`POST /evaluations/{id}/assess`，并由 `GET /plugins/{id}/evaluations` 反查。启停请求带期望配置版本；版本冲突返回 409。没有任意插件代码安装或通用执行 POST。

## 当前边界与后续验收

开发主链、调用阅读与插件级显式评测已接通。项目知识页可展示人工登记且固定源文、代码版本的“由什么实现／验证”关系；版本变化会标为待复核，普通 Markdown 链接不会被当成语义断言。关系只在本地版本匹配时标已核对；只有 GitHub main 确认同一提交才给不可变远端链接。受管项目文档可逐篇请求 Notion 发布，要求当前原文版本匹配、正文已提交并推到 GitHub main，再以不可变提交链接标明来源，发布后完整回读；未配置后台授权时明确显示未发布。知识修订、Markdown 链接和 Notion 发布仍在原入口运行，尚未全部成为统一插件操作。`lifeweave.evaluation` 在目录中仍标“不可运行”，因为评测自身尚未被统一 Host 包装成可调用插件。后台 Notion 镜像令牌仍未配置；本机 Codex 的交互式 Notion 授权不能替代它。

受管 Worker 的开始／结束事件证明它跨过执行适配器调用边界，不证明模型内部每条工具命令都被完整观察。外部本机 Codex 会话、未绑定 Hook 和第三方内部行为维持原有限定。执行结果和检查通过不等于用户已经接受工作。计划绑定的版本或实现摘要漂移会拒绝新调用；原计划和已发生的调用保留，需重新委托。单次页面调用最多返回 200 条，达到上限时未匹配步骤标为“无法判定”。

回归使用一次性 PostgreSQL 测试库检查旧入口、空间隔离、停用、固定绑定和插件评测；Vue 类型检查、组件测试和构建检查目录、开发与评价页面。真实委托 `dev-ac40c6a24079a273e873eede1d84e5a6` 已沿同一事项完成方案、独立审阅、隔离实施及页面核对，固定了方法与两篇项目知识，并产生真实 Codex 调用；主仓集成另以 Git 提交为准。第二个不同任务的复用与真实用户判断仍需继续验证，不能由测试库代替。

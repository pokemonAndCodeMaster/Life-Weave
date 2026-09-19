# 架构与关键实现

## 系统怎样分工

LifeWeave 是一个独立的模块化单体：Vue 页面处理交互，FastAPI 接收操作并协调业务模块，PostgreSQL 保存工作事实，Markdown 保存知识正文，本机执行节点调用已经安装的 CLI。启动应用不需要运行 Omni-Brain 或连接质检数据库。

```mermaid
flowchart TD
    UI[Vue 页面：对话、事项、知识、委托、回顾] --> API[FastAPI：校验输入与空间范围]
    API --> Conversation[对话服务：持久原话、语义解释、原子动作回执]
    Conversation --> Work
    Conversation --> Runtime
    Conversation --> Library
    API --> Work[工作服务：背景、计划、证据、回顾]
    API --> Library[知识服务：原文与修订]
    API --> Runtime[运行服务：固定输入、排队、结果]
    API --> Links[连接服务：Linear 与 Skills]
    Work --> DB[(PostgreSQL)]
    Library --> DB
    Library --> Files[Markdown 原文]
    Runtime --> DB
    Runtime --> Worker[执行节点：领取任务与报告过程]
    Worker --> CLI[Codex / OpenCode]
    CLI --> Isolated[每轮隔离目录和结果文件]
    Links --> Linear[Linear API]
    Links --> Sources[已有知识与 Skills 目录]
```

程序集成入口在 [src/api/app.py](../src/api/app.py)。它创建数据库连接、工作服务、知识服务、执行器和外部连接；启动时恢复过期租约并启动已启用的本机节点，退出时关闭节点和连接池。生产构建的 Vue 静态文件也由这个进程提供。

当前 Python、Vue、数据库与执行材料统一使用 LifeWeave 命名；历史入口兼容见 [命名说明](naming.md)。

| 职责 | 主要代码入口 |
| --- | --- |
| 页面路由与整体导航 | [router/index.ts](../web/src/app/router/index.ts)、[LifeWeaveShell.vue](../web/src/features/lifeweave/components/LifeWeaveShell.vue) |
| 自然入口与持久对话 | [conversations.py](../src/lifeweave/conversations.py)、[conversation_interpreter.py](../src/lifeweave/conversation_interpreter.py)、[ConversationPage.vue](../web/src/features/lifeweave/pages/ConversationPage.vue) |
| 成果、定位反馈与知识来源 | [research_outputs.py](../src/lifeweave/research_outputs.py)、[research_references.py](../src/lifeweave/research_references.py)、[ResearchOutputPanel.vue](../web/src/features/lifeweave/components/ResearchOutputPanel.vue) |
| 跨页面工作状态和操作 | [useLifeWeaveWorkspace.ts](../web/src/features/lifeweave/composables/useLifeWeaveWorkspace.ts)、[API 客户端](../web/src/features/lifeweave/api/lifeweave.ts) |
| 工作规则与数据库读写 | [工作服务](../src/lifeweave/service.py)、[工作 Repository](../src/lifeweave/repository.py)、[请求模型](../src/lifeweave/models.py) |
| 知识全文与候选修改 | [library.py](../src/lifeweave_knowledge/library.py)、[KnowledgePage.vue](../web/src/features/lifeweave/pages/KnowledgePage.vue) |
| 委托创建、重试和记录 | [运行服务](../src/lifeweave_runtime/service.py)、[运行 Repository](../src/lifeweave_runtime/repository.py) |
| 本机节点与 CLI 执行 | [local_workers.py](../src/lifeweave_runtime/local_workers.py)、[worker.py](../src/lifeweave_runtime/worker.py)、[执行器接口](../src/agent_runtime/executor.py) |
| 方法材料与 Linear | [task_sources.py](../src/integrations/task_sources.py)、[linear.py](../src/integrations/linear.py) |

## 数据分别保存在哪里

PostgreSQL 的 `workbench` schema 保存以下对象。完整字段以 [migrations](../migrations) 为准；此表解释职责，不复制所有列。

| 数据组 | 保存内容 | 事实边界 |
| --- | --- | --- |
| item / entity / relation | 事项、想法、专题、资源、成果及关联 | 事项保存执行安排；资料可以被引用，不必变成事项 |
| conversation / conversation_turn / personal_model | 对话、原话、解释状态、动作回执、明确方向与偏好 | 同一请求去重；对话不自动变成事项，偏好不自动推断 |
| research_knowledge_candidate | 研究运行与知识修订、运行内容版本及请求身份 | 关联现有修订，不复制第二份正式知识 |
| context / context_version / context_proposal | 当前背景指针、背景版本、修改提案 | 当前指针指向已接受版本；候选不是当前事实 |
| evidence / discussion / activity | 核验依据、讨论、进展记录 | 证据接受与事项完成分开，保留原因和来源 |
| meeting / snapshot / note / preference | 回顾配置、冻结内容、会议记录、偏好 | 冻结内容用于解释历史，不随当前背景更新 |
| machine / run / run_event | 执行节点、输入快照、尝试、事件、结果 | 运行状态是技术事实，不自动替代业务接受 |
| document_revision / library_source | Markdown 候选、源指纹、外部目录登记 | 正式知识原文仍在文件中 |
| linear_binding / linear_publication | 来源关联、远端快照、发送预览和核对状态 | 本地事项和 Linear 状态不做自动覆盖 |
| capability / capability_verification | 已复用的能力候选与验证记录 | 属于维护中心的能力治理入口，不代表所有 Skills 已验证 |

`.runtime/knowledge/{personal,team}` 保存本机知识原文；外部资料仍留在登记目录。`.runtime/executions/{space}/{run}/` 保存该轮工作目录、账号运行副本和产物。方法连接配置、本机节点设置、Linear 连接配置也在 `.runtime/`，不会提交到 Git。

结构化业务对象常用 JSONB 保存有差异的内容，避免为每种学习或生活事项提前设计独立表。代价是字段语义主要由 Service 和页面适配器约束；扩展公共字段时需要同时检查输入校验、持久化与多个页面，不能只改显示名称。

## 一次事项修改怎样生效

页面通过共享 API 客户端发送明确空间和对象 ID。Router 用 Pydantic 校验请求，Service 检查业务规则，Repository 执行 SQL。普通编辑带当前版本，数据库更新使用期望版本条件；版本过时返回冲突，而不是覆盖新内容。

背景修订另有提案流程。接受提案时更新版本和当前指针，之后列表、详情及实时回顾加载已接受内容。列表不能只读取事项初始 `payload`，否则新目标只在详情显示；这曾是实际发现并修复的问题。回顾会把当前目标、范围等放入阅读投影，冻结则保存当次投影。

子事项的委托背景从 [current_context_snapshot](../src/lifeweave/service.py) 组装，包含共享背景与本次局部目标。修改这个方法时，必须检查根事项和子事项，防止 AI 只得到父目标或只得到孤立的子标题。

## 一次 AI 委托怎样完成

```mermaid
sequenceDiagram
    participant U as 用户
    participant A as 工作台 API
    participant D as 数据库
    participant W as 执行节点
    participant C as CLI
    U->>A: 选择事项、任务、执行器与材料
    A->>D: 保存事项/背景/材料快照并排队
    W->>D: 领取任务、取得租约
    W->>W: 准备隔离目录和账号运行环境
    W->>C: 传入固定任务，执行
    C-->>W: 过程事件与结果
    W->>D: 报告状态、会话、结果与产物依据
    U->>A: 阅读正文、审阅证据、接受事项
```

创建委托时，[运行服务](../src/lifeweave_runtime/service.py) 读取事项的当前背景，把输入固定到运行记录。不指定工程时使用空白任务目录；指定工程时读取 Git 提交身份，执行节点创建独立 worktree，未提交修改不会自动进入。改动产物也不会自动合并回原仓。

一次可显式选择一项 Skill 和最多 10 篇知识。`TaskSources` 固定正文、来源指纹和方法支持文件；重试时保留这些已选输入。方法及支持文件合计最多 100 个文件、1 MB，选定材料主正文（含 Skill 主文件）合计最多 2 MB；具体限制和失败提示见 [snapshot 实现](../src/integrations/task_sources.py)。这与维护中心的能力发布机制是两个来源入口，运行时共同形成材料快照。

执行节点按租约领取任务，记录心跳、事件序号和报告。执行器适配层把统一请求转为 Codex/OpenCode CLI 参数，解析过程与结果。本机两空间各有可选节点；团队使用当前本机账号必须显式启用。远程/Docker 协议存在，但本机部署没有提供已经验收的远程集群。

失败、取消和不可用状态保存到同一运行记录。界面的“按当前背景再试”建立关联的新尝试，并取当前背景；它不是恢复原生 CLI 会话。运行的原生会话 ID 用于追溯。源码链接只读取该轮受控目录内允许类型的文本文件，不把任意路径开放给浏览器。

## 知识修改为什么不会静默替换正文

[Library](../src/lifeweave_knowledge/library.py) 每次读取实际文件并计算指纹。提出修改时保存基准指纹、原文、候选正文和原因，页面显示差异；接受时锁定修订记录，重新核对文件指纹，再替换文件并更新状态。若用户已在编辑器里修改了源文件，接受会报冲突。

本机受管原文使用临时文件和原子替换；数据库操作发生 Python 异常时尝试恢复原文。文件系统与数据库不是同一个事务，进程或机器恰在两者之间崩溃的恢复仍有限，不能宣称分布式原子提交。外部来源的修订可以下载，但不能通过该入口覆盖原仓。

路径读取会核验所属空间、登记来源和根目录，拒绝越界及不允许的隐藏/raw 路径。页面用 Marked 渲染、DOMPurify 清理 HTML，并对中文相对 Markdown 链接做一次解码和根范围校验；源码行号链接先转换成受控读取地址，再清理 HTML。

## Linear 的读写怎样保持可解释

首次引入用空间与远端 ID 计算稳定本地 ID，在事务内创建事项、初始背景和来源关联。重复引入只更新远端快照，保留本地编辑与安排。

发送结果先保存固定正文预览，真正发送时使用固定评论 ID。成功后回读正文比对；若网络返回不确定，下一次先核对同一评论，不盲目再发一条。不能确认时保留不确定状态并让用户核查。此发送路径有模拟远端测试，尚没有真实发送证据。

## 当前架构的适用范围

接口按空间检查数据，应用校验本机 Host 和写入 Origin，凭证不回传到页面；这不构成多人身份认证。默认只监听本机。CLI 的权限模式与隔离目录也不等于已经验证的多租户安全沙箱。

这种结构优先让单机使用和调试简单，并保留未来拆出执行节点的接口。真正引入多用户、远程访问或高并发前，需要增加相应身份、权限、调度、存储和故障验证，不能仅把监听地址改成公网。

## 新会话接续、材料推荐与纠偏

`src/lifeweave/continuation.py` 从事项、已接受背景、待审提案、讨论、证据和所有分页运行记录生成当前接续输出；不把输出保存成另一份规范正文。`scripts/lifeweave.py` 是正式本机客户端，网页与它共用业务 API；宿主 Agent 理解自然表达，产品保存和读取事实。

`TaskSources.recommend` 使用可解释文本匹配返回候选、命中理由和版本。网页预选最多一个方法、十篇知识并允许调整；CLI 提供推荐、全文阅读与显式委托。创建运行时再次计算当前推荐，记录在 `environment_snapshot.inputRecommendations`，实际选择保存在 `selectedInputs`，实际内容以 `capability_snapshot` 为准。重试固定原材料和原推荐，并标明来自旧运行；不把来源更新后的推荐版本冒充原材料版本。worker 的 `materializedCapabilities` 证明材料写入，实际步骤仍需执行事件支持。

纠偏复用 discussion，明确保存类型、原文、上下文版本与可选 run/内容位置。请求身份去重，错用同一身份提交不同内容报 409。新建或重试从同一事项读取纠偏，并固定到 prompt 与 `environment_snapshot.feedbackSnapshot`；已有输入不变。普通讨论不自动成为纠偏，纠偏也不自动采纳为新目标；旧历史讨论保持原分类。

源码与默认数据库都已使用 LifeWeave 命名。SQL 005 只原位改标识，外键和数据身份保持；迁移总账在应用迁移前由 `src.cli` 改名。安装级数据库/角色通过私有集群专用脚本原位迁移，命令与回退边界见开发说明。

## 网页自然对话与研究成果

网页 `/lifeweave/{space}/conversation` 是新的默认入口。`conversation_repository.py` 保存原话、每轮状态、引用位置和请求身份；`conversation_interpreter.py` 调用一次输出结构化决定的 Codex；`conversations.py` 校验决定并调用原有业务服务。普通回答不建事项；只记录模式直接保存想法，不调用模型。讨论与执行可以沿当前目标继续，也可以明确进入新主题。目标改动形成待审提案，知识改动形成待审修订。

解释器使用隔离账号运行副本，只保留模型与 provider 配置，禁用继承的连接器、工具、规则和 Skills；它不负责实施动作。研究委托仍走原有执行节点和受控目录。团队解释沿用显式启用本机账号的门槛。这里没有新建通用 Agent 编排器，也不声称 CLI 隔离已经达到多租户安全边界。

SQL 006 增加对话、消息与明确方向/偏好；SQL 007 增加成果来源与知识候选关联。所有已有表和原始产物保留。对话动作与本轮回执在同一 PostgreSQL 事务提交；请求身份复用不会重复建事项或委托。每个对话只允许一轮未完成处理。停止解释、解释失败和启动后发现中断都会保留原话及状态，不自动重放动作；网络结果不确定时页面使用同一请求身份核对。

语义解释读取当前事项、最多20个相关候选、最近20轮历史、5次运行摘要、最多10篇知识（共40000字符，单篇20000字符）及当前偏好；记录实际版本与截断情况。这是有界上下文，不是全量记忆或语义检索。解释器另外读取当前成果及最多5篇显式选择的研究：当前最多60000字符，其他每篇最多20000字符，总预算120000字符，并为每篇选择保留额度、记录截断。运行摘要每条2000字符，对话最近20轮的提问/回复各1500字符；解释器最终还有240000字符输入上限，过量报错并保留原话。研究运行额外固定完整的前轮当前成果、明确方向/偏好和反馈，以及本轮选入的其他研究快照；worker 后续报告不能改写这些输入。模型解释期间当前背景版本变更会拒绝旧的执行/目标/知识建议。

`ResearchOutputs` 把所有运行版本及人工成果作为阅读投影，不复制一份独立可编辑报告正文。当前成果优先取最新成功运行；失败的部分结果保留在版本列表。后续修订产生新成功运行，旧版本不变。阅读组件使用 Marked、DOMPurify 和 KaTeX；本轮 PNG/JPEG/GIF/WebP 通过限定运行目录的资产接口读取并校验内容与大小。外部图保留原图入口，失效图片明确显示缺口。纯文本下载保存完整 Markdown；`research_bundle.py` 通过 Markdown AST 收集本轮安全路径下的图片与引用，生成含原文、便携正文、资产及哈希清单的 ZIP。

选段反馈保存成果运行、内容位置、原话与当前背景版本；下一轮沿同一事项读取。`ResearchOutputs.propose_from_run` 校验成功成果与事项归属，在同一事务保存知识修订及来源关联；接受、拒绝和版本冲突仍由现有 Library 负责。候选不是当前知识，后续消费者只读取已接受文件。内置 `methods/paper-research/SKILL.md` 是一套可独立加载的研究方法，和用户登记的方法一起参加现有文本匹配推荐；它要求核对论文身份、保存一手来源、解释数据与实验、交付完整正文并按反馈修订。

这里尚没有完成可用时间和休息的时间块编排、持续后台机会发现、方法版本对照回归、远程 ChatGPT 接入或双向 Linear 同步。网页研究的证据与边界由当前状态及本轮验证记录维护。

知识内的成果来源由 `research_references.py` 用 Mistune 的 Markdown AST 识别，再由既有候选关联中的运行与版本派生 `references` 阅读映射。Library 的原文与哈希不变；同一个映射供待审全文、已接受知识、解释器、研究输入和 worker 材料清单使用。普通相对知识链接、代码块字面内容和外链不改写。不同运行使用相同相对目标时不默认采用最新运行，页面提示歧义并保留各来源成果入口。知识可下载原始 Markdown，或下载使用解析后来源的 HTML 阅读版；后者的图片、来源及样式仍依赖原工作台可访问，不是完整离线资产包。


执行输出可能含 PDF 提取产生的 NUL，而 PostgreSQL 的 text/JSONB 无法保存这种字符。Runtime 的 `storage_text.py` 只在出现 NUL 时生成可读投影（显示为 `␀`），在事件 payload 或运行环境的 `_lifeweaveTextStorage` 中保留完整原始 JSON 的 base64。原始材料和执行器产物保持原样；该元数据属于技术来源证据，不是用户知识或自动接受结论。

受影响成果页解释字符替换，并提供原始执行文本入口。`/artifacts/result` 从经过当前投影一致性校验的原始记录还原正文，与执行器产物哈希相符；`/research-output/download` 返回当前阅读正文，使用该投影自己的哈希。知识候选、正式知识及其 HTML 阅读版通过同一来源映射保留提示，不将阅读投影冒充原始产物。


论文还可能用普通 Markdown 文字链接引用本轮图片。`/source` 对 PNG/JPEG/GIF/WebP 委托既有 `ResearchOutputs.asset` 校验并返回正确媒体类型，因此报告、知识映射与 HTML 阅读版共享同一读取行为；不为修链接改写原成果，也不扩大到任意二进制文件。

## 成果的异地归档

`research_archive.py` 复用同一个便携包。每空间设置及逐运行归档状态保存在 `.runtime/research-archives`，进程间文件锁串行保护归档 checkout；后台每20秒扫描已启用空间，新成功正文进入归档，失败5分钟后重试。GitHub 用独立 checkout 写 `research-archive`，Linear 上传图片、引用材料和 ZIP，再创建关联项目的完整版本文档。每目标独立确认与重试，固定运行和正文身份避免重复创建，远端冲突不覆盖。

GitHub 以分支提交回读确认；Linear 附件校验字节 SHA-256，正文按完整解析结构核对（允许排版规范化，保留文字、代码、链接、图片、表格顺序）。Linear 不按工作台的 KaTeX 方式解释数学：发布投影将公式转为 LaTeX 代码，防止矩阵中的等号/减号被误认标题；原 Markdown 不变。确认是当次快照证明，并非持续监测人对远端的后续修改。细节、设置和恢复边界见 [归档与跨文章讨论](research-archive.md)。

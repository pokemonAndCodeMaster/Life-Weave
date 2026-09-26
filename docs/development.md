# 开发与运行维护

## 先把项目跑起来

实际工程：`/home/yyh/project/lifeweave`。Linux/WSL 环境需要 Python 3.10+、Node.js 22+、npm 和 PostgreSQL 16 服务端命令。

```bash
cd /home/yyh/project/lifeweave
python scripts/workbench.py setup
python scripts/workbench.py start
python scripts/workbench.py status
```

`setup` 安装本目录 Python 与前端依赖、构建页面、初始化本项目 PostgreSQL 并应用迁移。已有安装无需每次 setup。应用地址为 **http://127.0.0.1:8010**，API 文档在 `/docs`。前端单独开发可运行 `npm --prefix web run dev`，地址 `127.0.0.1:5180`，API 仍由 8010 提供。

不要在正式日常数据库运行清空或示例重建脚本。应用与 PostgreSQL 都由本目录负责，旧工程兼容链接不表示另一个安装。

## 读代码的顺序

先读 [产品设计](product.md) 与 [架构](architecture.md)，再从一个操作开始：

1. 事项编辑：`ItemDetailPage.vue` / `WorkPlanEditor.vue` → API 客户端 → `src/lifeweave/router.py` → Service / Repository。
2. 委托：`LifeWeaveModalHost.vue` → `src/lifeweave_runtime/service.py` → `worker.py` → `src/agent_runtime/`。
3. 知识修订：`KnowledgePage.vue` → `library_router.py` → `library.py` → 文件与修订记录。
4. 回顾：`MeetingPage.vue` → 工作服务的投影/冻结/导出方法。

Vue 使用 TypeScript 和 Composition API；前后端输入字段主要通过模型别名转换，不能在新页面自行猜测 snake_case/camelCase。后端业务字段变化要检查多个页面和冻结快照语义；数据库迁移只能新增，不能改已应用文件。

## 配置和凭证

数据库和日志配置由 ConfigManager 读取 [config/base.yaml](../config/base.yaml)、根目录可选 `.env` 和进程环境，进程环境优先。**知识根、执行器、节点启用选项和 `scripts/postgres.sh` 只读取进程环境，不自动加载 `.env`。** 涉及它们的配置请先 `export` 再运行启动命令；修改 PostgreSQL 参数也应使用进程环境，让数据库脚本与后端取得相同配置。

`.env` 应保持本机私有。`LIFEWEAVE_*` 是新前缀，旧 `GONGZUO_*` 仍兼容；在同一配置来源中新变量优先。`LIFEWEAVE_PG_BIN` 仅用于数据库生命周期脚本，后端不会据此启动其他数据库程序。

| 变量 | 默认 / 作用 |
| --- | --- |
| `LIFEWEAVE_DB_HOST` | `.runtime/postgres/socket`，相对工程根解析 |
| `LIFEWEAVE_DB_PORT` | `55440` |
| `LIFEWEAVE_DB_NAME` / `LIFEWEAVE_DB_USER` | 都为 `lifeweave`；本机既有数据库与角色已原位迁移 |
| `LIFEWEAVE_DB_PASSWORD` | 默认空；本机 socket 受私有目录约束 |
| `LIFEWEAVE_PG_BIN` | `/usr/lib/postgresql/16/bin` |
| `LIFEWEAVE_LOG_LEVEL` | `INFO` |
| `LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT` / `LIFEWEAVE_TEAM_KNOWLEDGE_ROOT` | `.runtime/knowledge/personal` 与 `team` |
| `LIFEWEAVE_LOCAL_WORKER` | `1`；设 `0` 使应用启动时不自动启动本机节点，用于受控测试 |
| `CODEX_COMMAND` / `OPENCODE_COMMAND` | 本机 CLI 命令，可指定路径 |
| `LINEAR_API_KEY` / `LINEAR_API_KEY_FILE` | 可选；也可在页面登记权限为 600 的凭证文件 |

远程执行节点另外支持 `LIFEWEAVE_WORKER_TOKEN`、`LIFEWEAVE_TEAM_ENV_ALLOWLIST`、`LIFEWEAVE_TEAM_CODEX_HOME` 和 `LIFEWEAVE_TEAM_OPENCODE_*`。精确参数见 `python -m src.lifeweave_runtime.worker --help`；存在这些参数不代表已经完成远程部署测试。普通本机使用应通过设置启用节点，不需要手工抄令牌。

`.runtime/` 为私有运行目录：Linear 配置、本机节点身份和 CLI 账号副本不得入 Git。原有 Skills 目录和外部知识登记是来源引用，不能假定换一台电脑仍存在这些绝对路径。

## 运行验证

```bash
LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest -q
npm --prefix web run type-check
npm --prefix web test
npm --prefix web run build
```

未设置 `LIFEWEAVE_TEST_DB=1` 时，真实 PostgreSQL 集成测试跳过。启用后创建随机临时数据库，测试完成删除，不使用日常数据库；测试依赖本项目默认 socket、端口和管理员角色。非默认 PostgreSQL 配置需要对应调整测试连接。

涉及页面时，用真实浏览器从新页面进入，检查请求、错误和业务结果。比如背景修订要看列表、详情、回顾与导出；改路由要同时看直接进入、刷新、旧链接和团队空间。测试 AI 调度可用合成执行器，真实账号调用应明确记录，不能混称为同一证据。

## 备份与恢复

先等待或取消正在执行的工作，再操作：

```bash
python scripts/workbench.py stop
python scripts/workbench.py backup
python scripts/workbench.py start
```

备份生成 `.runtime/backups/lifeweave-时间.dump` 和 `knowledge-时间.tar.gz`。旧备份仍用当时文件名。备份要求应用停止，使默认数据库和默认知识目录处于静止状态。

恢复时把 dump 用 PostgreSQL `pg_restore` 导入**新的数据库**，知识包解压到另一个目录，再通过配置指向它们。验证数据后再切换，不直接覆盖现用库。首轮已实际恢复并核对正文，见 [恢复证据](evidence/backup-restore.json)。

该脚本只打包默认 `.runtime/knowledge`；自定义知识根、外部知识、连接配置、CLI 账号和运行产物目录需要另行备份。仅有数据库 dump 不能恢复所有原文和 AI worktree。

## 常见问题从哪里查

| 现象 | 首先检查 |
| --- | --- |
| 页面打不开 | `status`、`.runtime/server.log`、8010 是否被占用；确认从本工程启动 |
| 页面接口不存在，或旧客户端报 308 | 新接口 `/api/lifeweave/…`；检查前端构建。旧 API 使用 308，客户端需跟随重定向，或直接改为新前缀；Python 3.10 urllib 默认不跟随 |
| 委托一直排队 | 设置页是否启用本空间节点、执行器是否已安装、维护中心节点状态 |
| CLI 已安装但运行失败 | 该轮错误和过程；安装检测不等于账号、模型和上游服务可用 |
| 知识修改冲突 | 源文件是否在提交候选之后被编辑；重新读取并比较，不强制覆盖 |
| 改名后旧结果文件打不开 | 检查旧目录符号链接与该轮 worktree；不要删除兼容链接 |

当前命令只停止本项目 PID，不使用按名称批量杀进程。`stop` 保留数据库进程，数据库本身的管理脚本是 `scripts/postgres.sh`。

## 改名后的维护原则

当前目录、包名、对外路由和文案统一为 LifeWeave。当前数据库、内部模块和组件已使用新名。只有历史记录、旧路由/环境变量/请求头以及旧迁移是兼容层，不对用户原文与不可变运行输入做全仓替换。旧路径符号链接承接已有 venv、Git worktree 与运行记录，删除它之前必须逐类迁移和验证。

本轮迁移前创建了数据库/知识备份与内容指纹。产品代码可按 Git 版本回退；若要把目录退回旧名，必须先停应用和 PostgreSQL，确认新路径无占用，移除兼容链接后再移动同一目录。不要运行 `git reset --hard` 或覆盖用户数据来完成回退。

文档维护分工：行为与理由进入 `product.md` / `architecture.md`；新结果和未完成项进入 `status.md`；命令配置进入本页；真实日志和截图进入证据目录。历史证据保留版本，不在旧截图说明中伪造新的验证时间。

## 让当前 Codex 会话接续开发事项

项目规范在“知识与材料”选择 **LifeWeave 项目** 即可阅读，来源是[当前文档清单](current-sources.json)，外部原仓只读。正式 CLI 也能无须已有聊天记录查找和读取：

```bash
python scripts/lifeweave.py knowledge --source lifeweave-project
python scripts/lifeweave.py read-knowledge lifeweave-project:docs/status.md
python scripts/lifeweave.py discover '要继续的开发目标'
python scripts/lifeweave.py continue item-实际编号
```

已经在 Codex 会话中直接开发时，可在同一事项中主动登记当前 Git 状态和阶段；先看[开发方法](../methods/lifeweave-development/SKILL.md)。服务会返回 `sessionId`。同一 `--request-id` 仅用于网络不确定时重试同一请求，不得拿它提交另一份内容：

```bash
python scripts/lifeweave.py external-start item-实际编号 --repo /path/to/git/repository --summary '本次要改什么' --knowledge lifeweave-project:docs/architecture.md
python scripts/lifeweave.py external-report item-实际编号 external-返回编号 verification '检查了实际用户路径' --check '实际命令与观察结果'
python scripts/lifeweave.py external-list item-实际编号
```

阶段只记录真正发生的动作。Git 提交和差异由服务读取；检查文字与选择的材料由当前会话主动上报。若本机 Codex 对 `/home/yyh/.codex/hooks.json` 完成信任审查，`external-start` 会利用 `CODEX_SESSION_ID` 将当前原生会话与事项绑定，之后支持的 `PostToolUse`、`Stop`、`Interrupt` 元数据自动进入同一推进记录。已有外部记录可在**同一个** Codex 会话内运行 `external-bind item-编号 external-编号 --repo /path/to/repository` 后开始采集。Hook 不保存原始命令、工具参数/输出；未绑定或未受信任、沙箱阻断本机 HTTP、Hook 被跳过时都不能宣称捕获完整过程。[真实烟测](evidence/development-agent/hook-smoke.md)记录成功与失败边界。

事项页“推进记录”和 `continue item-实际编号` 都可回读阶段；页面将原生 Hook 与主动上报分别标明。原始 Git 差异可从外部会话的“查看当前 Git 差异”读取，它反映当前仓库相对起始提交的所有变化，可能包含其他会话的改动，不能自动归功于该 Agent。服务不可用时，先保留真实代码和测试结果，恢复后再标明观测缺口。项目文档在原仓修改后，知识页和新 CLI 读取会取得新指纹，不需要复制第二份正式正文。

## 从首版安装迁移内部名称

本机已完成迁移。另一个仍使用默认旧数据库的安装，应先在旧代码版本停止应用、备份数据库与知识，再更新代码，运行：

```bash
.venv/bin/python scripts/migrate_storage_names.py --apply
.venv/bin/python -m src.cli
python scripts/workbench.py start
```

脚本只处理本工程私有 socket 上默认旧数据库/角色，检查没有业务连接后原位重命名；重复运行无变化。自定义数据库继续由环境配置指定，SQL 005 仍迁移其内部表名。旧 `.env` 中若显式指定默认旧数据库或角色，需更新为 `LIFEWEAVE_DB_NAME=lifeweave`、`LIFEWEAVE_DB_USER=lifeweave`。回退时先停服务，将备份恢复到独立数据库，用迁移前代码验证后再切换；不能仅回退代码连接已改名的表。

## 网页研究入口的维护

新增对话入口从 `ConversationPage.vue` → `useConversation.ts` → `conversation_router.py` → `Conversations` 读取和实施。语义解释依赖本机已登录的 Codex，使用与研究运行相同的账号来源但独立运行目录；`tomli` / `tomli-w` 用于解析并生成仅包含模型/provider设置的配置。每轮解释超时240秒，失败时原话保留；重新发送属于新的解释，不自动恢复原生会话。

成果阅读与知识关联从 `ResearchOutputPanel.vue` / `ResearchKnowledgeReview.vue` → `research_outputs.py` → 现有 Runtime / Library。公式使用 KaTeX；新增依赖需要重新安装并构建前端。服务启动会应用006/007追加迁移；升级前等待活动运行结束，停止、备份后再启动。当前部署仍是单进程本机模式，不能同时用两个应用进程指向同一日常库来做升级验证，因为启动恢复会改变未完成消息状态。

完整回归使用 `LIFEWEAVE_TEST_DB=1 .venv/bin/pytest -q`，不能仅执行旧 `test_live_database.py` 就声称新对话和成果已验证。`test_conversations.py` 使用真实数据库/HTTP但控制模型的语义决定；真正的模型和网页证据单独记录，测试数量不能代替自然交互结果。


若 PDF 工具输出触发 `\u0000 cannot be converted to text`，旧失败尝试会保留。升级到带 `storage_text.py` 的版本后，从运行页“按当前背景再试”建立新尝试。事件或运行环境中的 `_lifeweaveTextStorage.originalJsonBase64` 可按 base64 → JSON 还原受影响原数据；页面中的 `␀` 是存储投影。不要用批量删除源文控制字符或手改运行状态掩盖失败。

## 自动归档维护

在设置页配置 GitHub HTTPS 仓地址并启用；实际 Git 传输使用本机已有 SSH 认证，须事先能非交互访问对应仓。若要自动镜像至 Notion，还需在“Notion 知识镜像”填写已授权的根页面和仅本机可读、权限为 `600` 的集成令牌文件。Codex 中的 Notion OAuth 与该后台令牌是两条连接。状态、上传断点与归档 checkout 在 `.runtime/research-archives/{space}`；Notion 配置与回读状态在 `.runtime/notion-mirror/{space}`，均应随私有运行配置备份，不提交凭证。`LIFEWEAVE_ARCHIVE_WORKER=0` 可关闭报告后台扫描；默认跟随本机 worker 启用。停止服务会等待当前归档请求结束，先看归档状态再维护。

失败在成果页按目标显示，5分钟后自动重试或点立即归档。更换 GitHub 目标后，已有 checkout 不会自动改 remote，页面明确报错；停止服务并将该空间的 `git/` 目录移到备份位置，再启服务重试，服务会为新目标建立 checkout。不要删除逐运行的 `bundle/` 与 `state.json`。首次启用前的旧成果不批量回填，用户逐项触发；曾失败的记录启动后恢复扫描。详见 [归档与跨文章讨论](research-archive.md)。

## 开发 Agent 的受管委托

在需求或修复事项中打开“开发 Agent”，写明交付目标并选择 Git 目录。先检查当前仓库提交；未提交内容不会进入隔离工作树，必须显式勾选确认才能在脏工作树上委托。平台固定事项背景、所选方法与知识版本，依次执行只读方案、独立只读审阅（或小改动自检）和可写实施。只有审阅明确通过且原提交、背景及知识版本未改变时才进入实施。各阶段有独立 Run、真实事件和错误；结果页可读隔离工作树的 Git 差异，但不会自动合入原仓。

网页对话中的明确开发委托若提供项目目录，会自动建立同样的方案 Run；没提供目录时只登记事项并提示到“开发 Agent”补齐目录。单纯讨论、记录和研究保持原路径。本机 Codex 直接开发时，使用上述 `external-start` / `external-report` 关联同一事项；当前只能主动上报阶段和服务观测 Git，尚不能自动捕获该会话每条工具命令。

开发页当前默认且只开放 Codex。OpenCode 曾在当前空间完成一次指定模型小仓开发，但随后发现只读方案中的子代理能修改隔离工作树，故开发入口临时关闭；修正后的权限与阶段 Git 检查正在回归。通用 AI 委托的执行器设置与开发链开放状态分别判断，不能用一次成功证明模型长期可用。这不是 API Key 配置、团队空间或复杂项目质量的验收。全过程见[OpenCode 成功记录与反例](evidence/development-agent/opencode-chain.md)。

## 在网页中使用当前项目知识开发

接手开发时，沿同一需求事项核对输入、调用与结果；插件记录的详细边界见[插件目录与开发过程](plugin-system.md)。以下步骤对应当前网页入口。

1. **找到事项与当前知识。** 在对应的个人或团队空间打开需求事项，进入“开发 Agent”。需要了解项目时，先到“知识与材料”，在“知识范围”选择“LifeWeave 项目”，阅读相关正文，核对正文下方的路径与版本。这里打开文章只用于阅读，不会改变开发委托输入；读完回到原事项。
2. **核对默认材料并发起委托。** 填写“这次要交付什么”，检查“项目 Git 目录”、表单下方的“固定方法”和“本轮默认项目知识”数量。当前开发页没有逐篇知识选择框：保持推荐目录时，默认带入 `docs/product.md`、`docs/architecture.md`、`docs/status.md`、`docs/development.md` 四篇；改成其他目录后默认零篇，不能把在知识页读过的文章当作已选入。核对仓库当前提交及未提交改动排除提示，确认复选框所述边界，选择“方案检查”中的“独立审阅（复杂改动）”或“方案自检（小改动）”，再点“开始开发委托”。运行从当前提交创建隔离工作树，未提交正文不会作为代码改动带入。
3. **核对本轮固定版本。** 在“本事项的开发委托”找到刚创建的记录，查看 `Git` 提交、上下文版本及审阅方式；展开“固定输入与版本”，逐项核对方法、知识来源路径与版本。此处 Git 和材料版本显示哈希前 12 位。需要完整值时，可在浏览器开发者工具的网络响应中查看 `GET /api/lifeweave/{space}/items/{itemId}/development` 返回的 `repositoryRevision`、`contextVersionId` 和 `inputVersions`（`space` 为 `personal` 或 `team`）。项目提交和知识正文版本分别固定，不能假定知识一定来自该提交；后续修改原文也不会改写已创建 Run 的输入。
4. **对照计划与实际调用。** 展开“插件计划与实际调用”，再展开相应阶段的调用，查看状态、输入／输出引用、固定插件版本、实现摘要和“绑定核对”。计划列出预期步骤；调用记录说明实际进入过操作，单凭记录出现不能认定操作完成。按下表判断材料到了哪一步。

| 调用或记录 | 可以确认的事实 |
| --- | --- |
| `lifeweave.knowledge / recommend` 成功 | 服务执行了候选推荐；候选不等于全部选入，实际材料以固定输入为准。 |
| `lifeweave.knowledge / read` 成功，且输出引用有对应来源版本 | 服务读取正文并形成输入快照；可与“固定输入与版本”对照。调用详情会隐藏路径，来源路径仍在固定输入中查看。 |
| 方法插件 `lifeweave.method.… / bind` 成功，且输出引用有方法与版本 | 方法版本已固定到材料快照；不证明模型遵循了全部步骤。 |
| Run 环境中的 `materializedCapabilities` | 执行节点报告材料已写入执行目录。必要时查看 Run 接口返回的 `environmentSnapshot`；这与服务读取正文是不同证据。 |
| `lifeweave.execution.codex / run` 及执行器开始事件 | 执行节点进入执行适配器调用边界；仍需结束事件与结果判断本次调用是否成功。 |

页面没有独立的“已发送”确认状态。材料固定、写入执行目录、进入执行器调用分别证明不同阶段，均不能证明模型完整阅读或遵循材料。“尚无实际调用”不能当作已执行；条件步骤是否执行取决于所选材料和审阅方式；记录达到返回上限时，“无法判定”也不等于未执行。缺少结束事件的“中断／结束未观测”不能用 Run 成功反推调用成功。绑定核对只比较该调用与固定计划，不检查当前安装版本。

5. **查看运行、检查与实际差异。** 在调用中点“查看 Run”，核对关联开发阶段、运行状态、原生会话 ID 和事件；事件未读完时点“加载后续事件”。这里仅展示受限结构信息，需要结果正文及原始事件内容时，展开同一委托的“方案”“独立审阅”“实施与验证”。自检模式没有独立审阅 Run，对应栏显示“尚未开始”不表示漏跑。`lifeweave.checks.repository / verify_readonly` 检查只读阶段工作树，`verify_inputs` 检查进入实施前的输入未变化；调用成功并输出“只读检查通过”或“输入未变化”，都不等于业务测试通过。实施结束后点“查看实际 Git 差异”，结合结果正文中的实际命令、检查结果、错误和未完成范围判断是否满足验收。`awaiting_acceptance` 表示仍待核对与接受，受管运行不会自动合并代码，技术执行结束也不代表事项已被业务接受。
6. **按来源路径核对 Notion 镜像。** 记下本次固定知识的路径与版本，在同一空间的“知识与材料 → LifeWeave 项目”重新打开对应文章，查看正文下方“Notion 镜像”。当前开发事项页没有内嵌镜像状态，需以路径关联到同一篇知识。配置与汇总入口是“设置与连接 → Notion 知识镜像”。

| 镜像情况 | 怎样理解与核对 |
| --- | --- |
| 未配置 | 页面提示“产品后端未配置 Notion 镜像”，“发布并核对此篇”不可用。Codex 的交互式 Notion 授权不能替代后台集成凭据与根页面授权。若状态读取报错，先处理错误，不能据此断定未配置。 |
| 已配置 | 表示本空间已启用并登记了凭据文件、根页面；保存时会验证访问。这不代表每篇发布成功，也不保证凭据始终有效，仍需看单篇结果。 |
| 已确认 | 查看“上次回读确认”的源版本及“与当前原文相同／当前原文已变化”，同时检查“上次尝试失败”。须比较**委托固定版本、当前原文版本、上次确认版本**三者：镜像与当前正文相同，也可能不同于历史委托输入。旧确认不能代表新版本已同步，最近回读失败时远端当前状态仍未确认。 |

已配置且确需发布时，点“发布并核对此篇”。服务会核对当前正文与页面读取的版本一致、正文与本地 Git `HEAD` 一致，且 GitHub `main` 指向同一 `HEAD`；仅历史上推送过该文件不满足检查。通过后以不可变提交链接标明来源，发布并完整回读确认。失败保留本地原文，按提示处理后重新读取与核对，不把失败当作同步成功；Notion 始终是镜像，正式原文仍在项目仓库。单纯查看状态不需要配置或发布，也不会使已有委托改用新版本。

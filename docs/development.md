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

阶段只记录真正发生的动作。Git 提交和差异由服务读取；检查文字与选择的材料由当前会话主动上报。事项页“推进记录”和 `continue item-实际编号` 都可回读，网页“接着推进”也显示最近报告；刷新后可看到后来上报的阶段。该入口不能替代平台 Run 的自动事件，也不能证明未上报的命令；若服务不可用，先保留真实代码和测试结果，恢复后再标明观测缺口。项目文档在原仓修改后，知识页和新 CLI 读取会取得新指纹，不需要复制第二份正式正文。

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

在设置页配置 GitHub HTTPS 仓地址、Linear 项目 UUID 并启用；实际 Git 传输使用本机已有 SSH 认证，须事先能非交互访问对应仓。Linear 复用现有连接。状态、上传断点与归档 checkout 在 `.runtime/research-archives/{space}`，均应随私有运行配置备份，不提交凭证。`LIFEWEAVE_ARCHIVE_WORKER=0` 可关闭后台扫描；默认跟随本机 worker 启用。停止服务会等待当前归档请求结束，先看归档状态再维护。

失败在成果页按目标显示，5分钟后自动重试或点立即归档。更换 GitHub 目标后，已有 checkout 不会自动改 remote，页面明确报错；停止服务并将该空间的 `git/` 目录移到备份位置，再启服务重试，服务会为新目标建立 checkout。不要删除逐运行的 `bundle/` 与 `state.json`。首次启用前的旧成果不批量回填，用户逐项触发；曾失败的记录启动后恢复扫描。详见 [归档与跨文章讨论](research-archive.md)。

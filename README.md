# LifeWeave

**工作与生活，有序展开。**

LifeWeave 希望把工作、学习、爱好和生活中的想法、计划、行动与积累连接起来。当前以 LifeWeave 为暂用英文产品名，不再使用中文产品名；工程标识仍为 `lifeweave`。当前可用的是本机 AI 工作台：管理事项与背景、阅读和修订知识、委托 AI、审阅成果及回顾进展。

这是独立的本机应用与 Git 仓库。数据、依赖和进程都由本目录管理，不启动 Omni-Brain 或质检平台。部分工作模型与执行代码来自 Omni-Brain，来源和本轮交付范围见 [交付记录](docs/delivery.md)。

## 理解项目

想连续阅读全文，可直接阅读 [当前项目说明（整合版）](docs/complete-guide.md)：只汇编当前规范说明；2026-09-26 以前的 46 份全文和验证记录保留在[历史完整汇编](docs/history/complete-guide-20260926.md)。

第一次接触项目，按下面顺序阅读：

1. [产品设计](docs/product.md)：为谁解决什么问题、日常怎样使用、为什么这样组织。
2. [架构与关键实现](docs/architecture.md)：数据由谁维护，用户动作怎样穿过前后端，代码从哪里读起。
3. [当前完成情况](docs/status.md)：已经能用、实现但未实测、尚未实现的能力及证据。
4. [建设路线](docs/roadmap.md)：下一阶段按用户结果交付什么。
5. [开发与运行维护](docs/development.md)：本地启动、配置、验证、改名兼容和排障。

[文档导航](docs/README.md) 区分当前说明与历史证据；[命名说明](docs/naming.md) 解释名称与适配边界。

[个人管理平台优化讨论与演进方案](workspaces/reviews/personal-platform-evolution/review.md) 完整追踪本轮原始讨论、设计取舍和已实现范围。

## 开始使用

需要 Linux / WSL、Python 3.10+、Node.js 22+、npm，以及 PostgreSQL 16 的服务端命令。默认 PostgreSQL 命令目录为 `/usr/lib/postgresql/16/bin`，可用 `LIFEWEAVE_PG_BIN` 指定。AI 功能需要已安装并登录的 Codex 或 OpenCode CLI。

```bash
cd /home/yyh/project/lifeweave
python scripts/workbench.py setup
python scripts/workbench.py start
```

打开 **http://127.0.0.1:8010**。在 WSL 中可使用 Windows 浏览器访问该地址。默认进入个人空间；左上角可以切换团队空间。

1. 默认打开“对话”。直接提问、说出研究委托，或选“只记录”保存想法；历史对话可刷新后继续。左侧可保存明确的方向与偏好。
2. 在“计划”中安排优先级、日期和阶段。事项详情保存背景、讨论、关联材料与修改提案。
   “我的日常”可点“调整首页”，通过勾选、位置和上下移动配置卡片；个人与团队分别保存。
3. 点“委托 AI”，写清这次希望得到什么。可选择执行器、项目目录、工作方法与知识。不选项目时使用空白任务目录；选 Git 项目时使用固定提交的独立 worktree，未提交修改不会自动带入。
4. 在对话和事项页阅读完整成果，查看公式与本轮图片，选择历史版本、下载纯正文，或点“下载完整包（含图片）”取得可离线阅读的 ZIP。选中段落可保存定位反馈，再让对话继续修订。运行成功不会自动完成事项。
5. 从成果提出知识候选，或在“知识与材料”写笔记。阅读差异后接受或拒绝；当前原文变化会阻止覆盖。已接受知识可供后续对话和研究读取。
   打开一篇知识后，可在正文下查看它引用的同源 Markdown 和反向引用；断链会提示，不能误当成已有材料。
   “知识范围”选 **LifeWeave 项目**，可直接阅读当前产品、架构、状态与建设路线；这些原文只读引用本仓，不与历史汇编混排。
6. 在“周回顾 / 组会”配置关注内容、冻结当次内容、记录讨论并导出 Markdown。
7. 在“维护中心 → 能力与成长”可直接创建 Skill/Agent 候选，或从工作中的改进建议接续；创建不会自动安装或发布。在“评测任务”选择已有事项，写本次任务和通过标准；开始时可选 Git 仓库、方法与知识，所选输入固定到实际 Run。不选仓库时在空隔离目录运行。结束后查看过程、接受证据并记录判断，或把问题关联成改进建议。打开候选可看它及明确前任的工作样例、失败历史和关联委托。评测候选通过后进入已验证状态；当前候选及明确记录的前任候选若有失败，须沿原标准再评通过，才能显式发布。

“能力与评测 → 插件目录”展示当前受管开发能力、方法、执行器和脚本的身份、依赖与空间启停。需求/修复事项的“开发 Agent”可对照固定插件计划与实际调用；原方案、Run 事件和代码差异继续保留。具体观测范围及未接入能力见[插件目录与开发过程](docs/plugin-system.md)。

“就地讨论”会打开关联当前事项的 AI 对话；展开“附带其他研究成果”，可明确选入其他论文。已有知识另按问题匹配读取，实际来源及版本显示在回复下方。

在“设置与连接 → 研究成果自动归档”启用后，新成功报告会自动写入 GitHub 的 `research-archive` 分支；配置 Notion 后，正文也会进入单向镜像。两个目标分别显示回读状态，失败保留本地并重试；以前的成果可点“立即归档 / 重试”。[当前两篇 GitHub 归档](https://github.com/pokemonAndCodeMaster/Life-Weave/tree/research-archive)在本机关机后仍能访问。原有 Linear 文档仅作历史只读，不再接收新报告。代码在同仓 `main`；归档范围是成果与引用材料，不是整套运行数据库或自动采纳正式知识。详见 [归档与跨文章讨论](docs/research-archive.md)。

本机 Codex 已在正式 LifeWeave 仓的网页开发委托中跑通。OpenCode 指定模型曾完成一次三阶段小仓任务，但后续浏览器委托发现其只读方案可通过子代理写入隔离树；该委托已取消，网页 OpenCode 开发选项暂时关闭，直到权限与阶段检查通过真实回归。见[第二执行器实测与反例](docs/evidence/development-agent/opencode-chain.md)。重试是关联到原委托的新尝试，不是恢复原生 CLI 会话。

本轮已通过工作台完成 [Qwen-Drive 第一轮研究](http://127.0.0.1:8010/lifeweave/personal/items/item-810217743bbb4be2/outputs)。该入口属于当前本机安装；新安装不会预置这份个人事项。研究可用版的证据、明确边界和后续日常 Alpha 计划见 [当前完成情况](docs/status.md)。

## 连接已有积累

“设置与连接”可以添加已有 Markdown 知识目录、包含各个 `SKILL.md` 子目录的 Skills 根目录，以及 Notion 镜像连接。Linear 仅保留既有历史读取。

- 外部知识只读；修订可下载，交回原仓库处理。工作台管理的知识默认写入 `.runtime/knowledge/{personal,team}`。
- 委托时按需选择一套 Skill 和最多 10 篇知识，固定正文与方法支持文件。重试保留已选择资料的快照；要使用更新后的资料，创建新委托。Skills 需要适用于目标工程；引用原仓库专有脚本的方法仍可能需要调整。
- Notion 后台镜像使用单独的集成令牌文件和根页面授权。本机 Codex 的 Notion OAuth 只供交互式读取，不能替代后台令牌；未配置时页面如实显示“未启用”。原文留在 Git 仓或本机知识库。
- 旧 Linear 连接可读取历史事项和已归档文档；新评论、发布及研究自动归档已停止。

## 数据与运行

```bash
python scripts/workbench.py status
python scripts/workbench.py stop
python scripts/workbench.py backup
python scripts/workbench.py start
```

备份位于 `.runtime/backups/`，包括 PostgreSQL dump 和工作台知识压缩包。外部知识、CLI 账号凭证、方法连接配置和运行目录需按需另行备份。不要把包含个人数据或凭证的 `.runtime/` 提交到仓库。

恢复时先停止应用，将 dump 用 `pg_restore` 恢复到一个**新的数据库**，将知识包解压到新的知识目录，再用 `LIFEWEAVE_DB_NAME` 和 `LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT` / `LIFEWEAVE_TEAM_KNOWLEDGE_ROOT` 指向它们。先检查恢复结果，再切换日常使用环境；不覆盖现用数据库。

数据库仅监听本项目私有 Unix socket，目录 `.runtime/postgres/`，端口参数 `55440`，默认数据库和角色均为 `lifeweave`。服务日志为 `.runtime/server.log`；AI 的隔离目录、私有账号副本与产物位于 `.runtime/executions/`，运行记录保存在数据库。不要在 AI 正在执行时停止服务。

本机服务只监听 `127.0.0.1:8010`。当前身份是本机单用户，个人/团队是内容空间，**没有多人登录与成员权限系统**。不应直接暴露到公网。团队执行机和 Docker 协议保留，但默认启动个人空间的本机 worker；团队空间可以在设置中明确选择使用本机账号启用执行。远程执行需要另行部署与验证。

## 开发与验证

后端 FastAPI + PostgreSQL，前端 Vue 3 + TypeScript。前端开发服务器为 `127.0.0.1:5180`，代理到 `8010`。

```bash
.venv/bin/pytest
LIFEWEAVE_TEST_DB=1 .venv/bin/pytest tests/test_live_database.py
cd web
npm run type-check
npm test
npm run build
```

数据库集成测试在本项目 PostgreSQL 中创建随机命名的临时数据库，完成后删除；不会清空使用中的工作台数据库。实际浏览器与 AI 验证记录见 [交付记录](docs/delivery.md)。

API 文档：<http://127.0.0.1:8010/docs>，当前接口前缀 `/api/lifeweave/`，页面前缀 `/lifeweave/`。旧页面仍会跳转；旧 API 客户端须跟随 308，或改用新前缀。配置读取范围见 [运行维护](docs/development.md#配置和凭证)。数据库变更新增到 `migrations/`，启动时按摘要校验并只应用新版本。

## 在新的本机 Agent 会话接续

当前支持本机 Codex/OpenCode 等可运行命令的会话，使用同一工作台 API；不依赖开发者聊天记录。先让 Agent 阅读本节或运行帮助：

```bash
python scripts/lifeweave.py --help
python scripts/lifeweave.py discover '想继续的目标'
python scripts/lifeweave.py continue item-实际编号
python scripts/lifeweave.py development-choices item-实际编号
python scripts/lifeweave.py recommend item-实际编号
python scripts/lifeweave.py read-knowledge 'local:知识路径.md'
python scripts/lifeweave.py knowledge --source lifeweave-project
python scripts/lifeweave.py read-knowledge 'lifeweave-project:docs/status.md'
python scripts/lifeweave.py read-method method-实际编号
python scripts/lifeweave.py runs
python scripts/lifeweave.py capture '先记一个生活想法，暂时不推进'
python scripts/lifeweave.py feedback item-实际编号 '重点理解错了，先讨论适用范围'
```

`development-choices` 只读查询开发选项并打印 JSON，不启动执行。

`capture`、`create`、`discuss`、`feedback` 只保存，不启动 AI。`run` 是显式委托，会采用文本匹配推荐的输入；先查看 `recommend` 的依据，无匹配时不捏造方法，复杂适用性仍由 Agent 判断。网页的“委托 AI”也会预选推荐，可手动调整。推荐、实际输入快照与执行步骤是不同证据。

事项概览的“接着推进”可查看当前记录、下载接续 JSON、保存针对事项或具体运行的纠偏。新的运行/重试会自动固定这些反馈，已有运行保持原输入；反馈不会自动改变已接受目标。重复发送相同反馈可使用同一 `--request-id`；其他创建动作遇到超时须先读取确认，不自动重发。

命令读取本机服务，失败返回非零；`--workspace team` 切换空间。ChatGPT 远程连接、自然语言自动排程、自动发布方法改进尚未完成。完整研发方案见 [下一阶段产品方案](workspaces/reviews/lifeweave-next-stage/review.md)。

在已经打开的 Codex 会话开发代码时，可按[开发与维护说明](docs/development.md#让当前-codex-会话接续开发事项)把实际阶段与 Git 状态写回同一事项。明确绑定且 Codex 信任本机 Hook 后，受支持的工具和生命周期元数据也会自动出现在推进记录；它不上传原始命令/输出，且不能保证捕获所有步骤。受管网页委托另有完整 Run 记录。

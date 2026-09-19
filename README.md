# LifeWeave · 经纬

**工作与生活，有序展开。**

LifeWeave 希望把工作、学习、爱好和生活中的想法、计划、行动与积累连接起来。中文名“经纬”取交织成整体之意；英文工程名统一为 `lifeweave`。当前可用的是本机 AI 工作台：管理事项与背景、阅读和修订知识、委托 AI、审阅成果及回顾进展。

这是独立的本机应用与 Git 仓库。数据、依赖和进程都由本目录管理，不启动 Omni-Brain 或质检平台。部分工作模型与执行代码来自 Omni-Brain，来源和本轮交付范围见 [交付记录](docs/delivery.md)。

## 理解项目

第一次接触项目，按下面顺序阅读：

1. [产品设计](docs/product.md)：为谁解决什么问题、日常怎样使用、为什么这样组织。
2. [架构与关键实现](docs/architecture.md)：数据由谁维护，用户动作怎样穿过前后端，代码从哪里读起。
3. [当前完成情况](docs/status.md)：已经能用、实现但未实测、尚未实现的能力及证据。
4. [开发与运行维护](docs/development.md)：本地启动、配置、验证、改名兼容和排障。

[文档导航](docs/README.md) 区分当前说明与历史证据；[命名说明](docs/naming.md) 解释名称与适配边界。

## 开始使用

需要 Linux / WSL、Python 3.10+、Node.js 22+、npm，以及 PostgreSQL 16 的服务端命令。默认 PostgreSQL 命令目录为 `/usr/lib/postgresql/16/bin`，可用 `LIFEWEAVE_PG_BIN` 指定。AI 功能需要已安装并登录的 Codex 或 OpenCode CLI。

```bash
cd /home/yyh/project/lifeweave
python scripts/workbench.py setup
python scripts/workbench.py start
```

打开 **http://127.0.0.1:8010**。在 WSL 中可使用 Windows 浏览器访问该地址。默认进入个人空间；左上角可以切换团队空间。

1. 在首页记下一个想法，或在“工作事项”中新建工作，填写目标与范围。
2. 在“计划”中安排优先级、日期和阶段。事项详情保存背景、讨论、关联材料与修改提案。
3. 点“委托 AI”，写清这次希望得到什么。可选择执行器、项目目录、工作方法与知识。不选项目时使用空白任务目录；选 Git 项目时使用固定提交的独立 worktree，未提交修改不会自动带入。
4. 在“AI 委托”查看过程、失败原因与实际结果。在“成果与验证”审阅证据，然后接受事项结果。运行成功不会自动完成事项。
5. 在“知识与材料”写笔记或提出修订，阅读差异后接受。知识正文是 Markdown 文件，直接在本地修改会被版本检查识别。
6. 在“周回顾 / 组会”配置关注内容、冻结当次内容、记录讨论并导出 Markdown。

本机首次交付已实际跑通 Codex。OpenCode 可建立会话，但当前配置下的真实调用连续返回执行器内部错误，暂建议选 Codex；具体记录见交付说明。重试是关联到原委托的新尝试，不是恢复原生 CLI 会话。

## 连接已有积累

“设置与连接”可以添加已有 Markdown 知识目录、包含各个 `SKILL.md` 子目录的 Skills 根目录，以及 Linear 连接。

- 外部知识只读；修订可下载，交回原仓库处理。工作台管理的知识默认写入 `.runtime/knowledge/{personal,team}`。
- 委托时按需选择一套 Skill 和最多 10 篇知识，固定正文与方法支持文件。重试保留已选择资料的快照；要使用更新后的资料，创建新委托。Skills 需要适用于目标工程；引用原仓库专有脚本的方法仍可能需要调整。
- Linear 使用个人 API Key 或本机权限为 `600` 的凭证文件。凭证保存在 `.runtime/linear.json`，不进入 Git，也不回传到页面。
- Linear 页面分页读取分配给当前账号的事项。导入创建本地工作；再次导入更新远端快照，保留本地标题、目标、安排和进展。
- 向 Linear 发成果前先准备固定正文预览，再点发送。系统回读评论核对；网络结果不确定时优先核对已有评论，不自动重复发送。本地事项与 Linear 状态独立维护。

## 数据与运行

```bash
python scripts/workbench.py status
python scripts/workbench.py stop
python scripts/workbench.py backup
python scripts/workbench.py start
```

备份位于 `.runtime/backups/`，包括 PostgreSQL dump 和工作台知识压缩包。外部知识、CLI 账号凭证、方法连接配置和运行目录需按需另行备份。不要把包含个人数据或凭证的 `.runtime/` 提交到仓库。

恢复时先停止应用，将 dump 用 `pg_restore` 恢复到一个**新的数据库**，将知识包解压到新的知识目录，再用 `LIFEWEAVE_DB_NAME` 和 `LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT` / `LIFEWEAVE_TEAM_KNOWLEDGE_ROOT` 指向它们。先检查恢复结果，再切换日常使用环境；不覆盖现用数据库。

数据库仅监听本项目私有 Unix socket，目录 `.runtime/postgres/`，端口参数 `55440`，默认数据库和角色均为 `gongzuo`。服务日志为 `.runtime/server.log`；AI 的隔离目录、私有账号副本与产物位于 `.runtime/executions/`，运行记录保存在数据库。不要在 AI 正在执行时停止服务。

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

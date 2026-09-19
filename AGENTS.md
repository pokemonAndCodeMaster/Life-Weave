# LifeWeave · 经纬

这是个人/团队工作台的独立产品仓。2026-09-18 用户明确要求新目录、新 Git 仓，并授权持续自主实现。Omni-Brain 是已复用代码、知识和 Skills 的来源，不再决定本仓的物理落点。

2026-09-19 用户要求重新命名并说明项目。当前产品为 **LifeWeave · 经纬**，实际工程目录为 `/home/yyh/project/lifeweave`。产品目标见 `docs/product.md`，当前实现见 `docs/architecture.md`，完成范围见 `docs/status.md`，运维见 `docs/development.md`。旧目录仅为已有成果路径的兼容链接。现行内部模块、组件、默认数据库和表名均使用 LifeWeave；历史迁移和用户数据不批量改写。

- 面向中文用户，交付可运行的工作管理、知识阅读与修订、AI 委托和成果审阅。
- Vue Composition API + TypeScript；FastAPI Router → Service → Repository → PostgreSQL。
- `src/lifeweave` 管工作事实，`src/lifeweave_runtime` 管执行，`src/lifeweave_knowledge` 管知识，`src/integrations` 管外部连接。`web/` 是独立前端。
- 运行数据仅在 `.runtime/`；不读取或修改旧项目数据库，不复制认证到版本库，不输出密钥。
- 外部知识默认只读。正式修订必须显示差异、检查源版本并由用户在页面接受。不得将候选数据库版本冒充已更新原文件。
- 日常任务运行在显式目标项目或空白任务目录，不默认在工作台源码中运行。不强迫学习、讨论和写作走软件开发审批流程。
- 远端连接失败保留本地工作，不报告已同步。外部写入采用显式用户操作，检查冲突及回读。
- 启动与验证见 README.md；范围和证据见 docs/delivery.md。测试数据库独立于用户数据库。
- 普通本地开发可以直接推进，不因模板、编号或缺少独立审批文件重复索要已有授权。

## 使用工作台的正式入口

本机新会话处理日常工作时，先读 README 的“在新的本机 Agent 会话接续”，使用 `python scripts/lifeweave.py --help`。查旧事先 discover，再 continue 读取当前记录；先记录时只 capture，讨论不自动 run。推荐按文本匹配提供候选，Agent 应核对适用范围；不假定已有方法实际执行。纠偏通过 feedback 保存，让下一轮自动读取，不手工补写数据库。这里是产品使用入口，不能把开发仓内的自然任务理解为修改工作台源码。云端 ChatGPT 未连接不得报告已同步。

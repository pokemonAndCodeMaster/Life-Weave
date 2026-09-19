# LifeWeave · 经纬

这是个人/团队工作台的独立产品仓。2026-09-18 用户明确要求新目录、新 Git 仓，并授权持续自主实现。Omni-Brain 是已复用代码、知识和 Skills 的来源，不再决定本仓的物理落点。

2026-09-19 用户要求重新命名并说明项目。当前产品为 **LifeWeave · 经纬**，实际工程目录为 `/home/yyh/project/lifeweave`。产品目标见 `docs/product.md`，当前实现见 `docs/architecture.md`，完成范围见 `docs/status.md`，运维见 `docs/development.md`。旧目录仅为兼容链接；`gongzuo` 内部模块和数据库标识仍属同一产品，不可据此启动另一套工作台或改写历史材料。

- 面向中文用户，交付可运行的工作管理、知识阅读与修订、AI 委托和成果审阅。
- Vue Composition API + TypeScript；FastAPI Router → Service → Repository → PostgreSQL。
- `src/gongzuo` 管工作事实，`src/gongzuo_runtime` 管执行，`src/gongzuo_knowledge` 管知识，`src/integrations` 管外部连接。`web/` 是独立前端。
- 运行数据仅在 `.runtime/`；不读取或修改旧项目数据库，不复制认证到版本库，不输出密钥。
- 外部知识默认只读。正式修订必须显示差异、检查源版本并由用户在页面接受。不得将候选数据库版本冒充已更新原文件。
- 日常任务运行在显式目标项目或空白任务目录，不默认在工作台源码中运行。不强迫学习、讨论和写作走软件开发审批流程。
- 远端连接失败保留本地工作，不报告已同步。外部写入采用显式用户操作，检查冲突及回读。
- 启动与验证见 README.md；范围和证据见 docs/delivery.md。测试数据库独立于用户数据库。
- 普通本地开发可以直接推进，不因模板、编号或缺少独立审批文件重复索要已有授权。

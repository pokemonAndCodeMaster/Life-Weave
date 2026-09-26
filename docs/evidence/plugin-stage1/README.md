# 首批插件接入：真实开发与知识复用证据

核对日期：2026-09-27。工程依据是 [阶段 1 方案](../../../workspaces/reviews/plugin-foundation-stage1/review.md)；本页记录当前正式服务和两个真实事项，不把模型自述当作用户验收。

首个事项 `item-92989f3f9ca34660` 的开发委托 `dev-ac40c6a24079a273e873eede1d84e5a6` 固定了方法、两篇项目知识和 Git 提交。只读方案 `gzrun-20260926-163150-9b181d3e`、独立审阅 `gzrun-20260926-163408-4b56d934`、隔离实施 `gzrun-20260926-163536-b616da61` 均真实完成；其插件页面读回 22 条调用。迁移 015 后，三个开发组合调用与对应 Run 关联，另有执行器、知识、上下文和检查调用。实施者核对隔离补丁、回归及页面后，将代码以 [af6d072](https://github.com/pokemonAndCodeMaster/Life-Weave/commit/af6d0728ef8d523090e86e36dc4777b82378886a) 合入主仓。

第二个事项 `item-e044cf4e1af64b0c` 复用同一开发组合，目标是让接手开发者能在网页找到项目知识、固定版本并核对插件过程。委托 `dev-1e692d4cd39406fb5393c58147bf8468` 先完成方案 `gzrun-20260926-172328-9706ccec`，再由独立审阅 `gzrun-20260926-172527-abab3301` 给出 `PASS`，最后在 `gzrun-20260926-172650-784859ce` 的隔离工作树修改 `docs/development.md`、`docs/README.md` 与整合文档。复核者只接收这三份差异，执行完整汇编检查，并从正式 API 和 390px 页面读回新正文；[b8ab207](https://github.com/pokemonAndCodeMaster/Life-Weave/commit/b8ab207) 已推到 GitHub main。旧委托仍保存旧知识版本，正式知识入口已读回新正文；后续任务需以新版本重新委托。

正式服务应用了迁移 013—015，`GET /items/{itemId}/plugin-process` 能读回首个事项的计划及 22 条调用，API 投影不发送原始插件错误、提示词或路径。知识页 `docs/plugin-system.md` 的两条人工登记关系在本地和 GitHub 提交核对后显示为当前版本；桌面 1360px 与手机 390px 没有脚本错误或横向溢出。插件目录中对同一首轮 Run 的开发组合和 Codex 执行分别保存了一条“无法判断”评价：技术过程已被核对，但尚无用户接受的该 Run 证据，不能凭运行成功判定业务效果。

独立 PostgreSQL 整库回归、Vue 类型检查、67 项组件测试和生产构建通过；`python scripts/build_complete_guide.py --check` 验证 10 份当前来源全文一致、本地链接有效。第二个文档任务的隔离实施也运行了汇编检查和 `git diff --check`。这些检查不证明 Notion 双端发布：LifeWeave 产品后端仍显示 `enabled=false`、`configured=false`，交互式 Codex Notion 授权不等于产品后台授权。线上交付说明由 Codex 通过 Notion MCP 人工写入，不能计作工作台自动镜像成功。

# 开发 Agent 首条真实执行证据

正式 LifeWeave 仓又通过网页提交了一次有界 CLI 增量，留下独立方案、审阅、实施 Run 与合入检查；见[正式项目执行记录](live-project-run.md)。下文是更早的临时小仓验证，不应与正式仓的产物混为同一运行。

日期：2026-09-26。使用一次性 PostgreSQL 数据库和一个仅有 README 的临时 Git 仓库，运行正式 FastAPI、内置本机 Worker 和已登录的 Codex CLI。测试结束后删除临时数据库及仓库；下列身份来自运行时输出，不是生产事项。

用户任务：在 README 既有句子后新增 `Greeting: hello`，只改这一文件，执行 `grep` 验证。通过 `/api/lifeweave/personal/development` 提交，选择 `reviewMode=independent`。委托 `dev-78f864c7b38f25de0a683bb649b8350f` 从 `planning` → `reviewing` → `implementing` → `awaiting_acceptance`，没有第二次授权按钮。

| 阶段 | 实际 Run | 观察结果 |
| --- | --- | --- |
| 只读方案 | `gzrun-20260926-135258-2294fc8f` | 读到原提交 `8e673bf424f9293c595685de8c9743d1731af7cf`；指出目标行仍不存在、`grep` 退出码 1；提出单行差异、风险、自检，未修改文件 |
| 独立审阅 | 第二个独立 Run | 输出 `REVIEW_DECISION: PASS`，说明本轮只审方案，尚未实施；没有以方案成功冒充完成 |
| 实施与验证 | `gzrun-20260926-135427-0b630731` | 隔离工作树中的 README 多出一行；报告 `grep -nFx 'Greeting: hello' README.md` 输出 `4:Greeting: hello`、退出码 0，并报告 `git diff --check` 通过；未合回原仓 |

本机执行快照记录 `executor=codex`、`executorVersion=codex-cli 0.154.0`、`effectiveModel=gpt-6-astra`、`modelSource=Codex CLI config`、`credentialSource=personal local CLI account copy` 和各 Run 的实际隔离目录。实施后的 Git diff 由服务重新读取，而不是从模型文字生成。测试时发现该读取最初把注入的材料目录计入文件数；已改为读取逐文件 Git 列表并排除注入的 Skill 与 manifest。随后以真实数据库/HTTP 回归验证“已提交的 README 修改 + 未跟踪的新文件”仍出现、注入输入不出现。此修正发生在上述真实 Run 之后，因此该 Run 的原始文件数不作为修正后的展示证据。

本次没有验证：复杂真实项目的方案质量、外部 Codex 会话自动工具级采集、Notion 后台真实上传和图片显示、OpenCode 调用、API Key 切换、自动合并。模型报告的 `grep` 与 `git diff --check` 尚未另从运行事件逐条人工回放；可独立核对的后果是服务读回的 README Git 补丁与委托状态。

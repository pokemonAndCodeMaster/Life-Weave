# OpenCode 指定模型的三阶段开发实测

核对日期：2026-09-26。个人空间的一个小型 Git 仓库用网页开发委托 API 完成只读方案、独立审阅、可写实施；当前模型固定为 `opencode/mimo-v2.5-free`，执行器版本 `1.18.10`。这证明该模型在本机账号副本下能通过现有 Worker 完成一次有界链路，不代表任意 OpenCode 模型或复杂项目质量已验证。

测试仓原始提交 `e80b6591cd8114e8129682e9a9706424132aa58b`，含 `wordcount.py` 与 README。任务是在原函数旁新增非空行计数、标准库测试和测试说明。事项 `item-c52809b4b3294166`、开发委托 `dev-5629b7cc885372ea444c7ec453e9d93d` 均保留在正式本机工作台；测试仓位于 `/tmp/lifeweave-opencode-WNcJFK`，实施结果在工作台私有隔离目录，并未合回测试仓。

| 阶段 | Run | 实际结果 |
| --- | --- | --- |
| 只读方案 | `gzrun-20260926-145410-af1a6a3a` | 成功，退出码 0；写出实现、风险、验证与自检。独立检查原提交的 Git 差异为空。 |
| 独立审阅 | `gzrun-20260926-145615-c2750f14` | 成功，退出码 0；输出独立 `REVIEW_DECISION: PASS`。独立检查原提交的 Git 差异为空。 |
| 可写实施 | `gzrun-20260926-145718-a0deeaab` | 成功，退出码 0；改动 README、`wordcount.py`，新增 `test_wordcount.py`；服务保留实际隔离目录和 Git 补丁。 |

三个 Run 的环境快照均报告 `effectiveModel=opencode/mimo-v2.5-free`、`modelSource=run selection`、`credentialSource=personal local CLI account copy`。这里的模型值来自委托参数，执行器确实将它传给 OpenCode CLI 的 `--model`；原生事件未给出上游提供方的模型身份回执，不能据此独立证明最终提供方身份或未来凭证仍可用。方案和审阅权限为 `read-only`，实施为 `workspace-write`。委托状态经过 `planning → reviewing → implementing → awaiting_acceptance`，用户业务接受尚未发生。

实施模型报告 7 项 unittest 通过；我又在实施工作树独立执行 `python -m unittest test_wordcount -v`，7 项全部通过，`git diff --check` 通过。服务回读的文本补丁可见新增函数和 7 个测试。运行测试产生两个未跟踪的 `__pycache__/*.pyc`；初次差异计数误把它们算为改动文件，随后服务改为明确列出并排除未跟踪测试缓存。缓存仍留在隔离目录，不会伪装成源码修改或悄悄删除。当前页面应展示 3 个实际代码/文档文件与 2 个已排除缓存文件。

这次小仓事项最初的背景写的是“空白字符串词数”，而委托明确要求新增“非空行数”。审阅 Run 没有指出这处背景与本轮任务的偏差。因此此证据只证明阶段运行、固定模型与可审差异，不能证明模型能可靠识别所有目标冲突。页面仍默认推荐已有正式仓验证的 Codex；OpenCode 只在当前空间近七天有明确模型的成功 Worker Run 且 CLI 可用时出现，并且服务端拒绝其他模型。

## 网页选择与提交

同日晚些时候在真实事项 `item-4891c4eedb674483` 的“开发 Agent”页，用 Chromium 点选 OpenCode。页面显示指定模型，项目路径切换到外部小仓后默认 LifeWeave 知识变成 0 篇；[提交前截图](opencode-selector.png)保留了这些选择。浏览器发出的 `POST /api/lifeweave/personal/development` 返回 202，实际 JSON 包含 `engine=opencode`、`model=opencode/mimo-v2.5-free`、`knowledgeRefs=[]`、外部仓库路径和 `reviewMode=self`，生成委托 `dev-32ad272700c04ed418a4c1730651a387`；页面没有 JavaScript 错误。

**这次浏览器委托暴露了只读边界失败。** 方案 Run `gzrun-20260926-151255-21d9d208` 在 `read-only` 阶段通过 OpenCode 的 `task` 子代理改动了隔离工作树中的 README。发现 Git 差异后立即取消委托，最终状态为 `cancelled`，没有进入实施，原测试仓提交也未改变。第一条小仓成功记录不能抵消这次反例。此时网页开发链的 OpenCode 选项已临时关闭。修正包括禁止只读阶段调用 `task`、`bash` 和编辑工具、禁用只读阶段外部插件，并在方案和审阅 Run 结束后以原提交核对隔离树；若发现修改则阻断后续阶段。数据库/HTTP 回归已覆盖“方案改动 README 必须 blocked”，但仍需真实模型回归才能重新开放。

修正后尝试了两个新的隔离 Worker 只读 Run，其中 `gzrun-20260926-152319-714eedda` 在模型启动前返回 `OpenCode's free tier can only be used from within OpenCode`；没有得到新的真实只读行为证据。对比测试中，日常 HOME 下直接运行 OpenCode `--pure` 可以返回 `OK`，而使用 Worker 私有 HOME 与复制的账号文件运行则返回服务端错误；这定位到当前隔离环境/提供方路径差异，尚未找到可接受的修复。不能通过改用用户日常 HOME 绕过隔离来假装第二条开发链恢复。当前页面服务端门禁仍关闭 OpenCode 开发委托；通用执行器的既有失败和成功 Run 都保留，可继续排查。

只读阶段的第一版 Git 守卫先被独立复核发现漏看 `.gitignore` 忽略的路径；补查 ignored 文件后，又被发现可通过 Git 索引的 `assume-unchanged` 或把 `core.worktree` 指向另一棵干净目录，令 Git 命令看不到隔离目录的真实改动。最终修正由可信 Worker 在模型启动前对整个隔离目录计算文件内容、目录、权限和符号链接的 SHA-256，服务在方案及审阅结束后直接重新计算；不再以可被模型改变的 Git 配置或索引作为唯一依据。数据库/HTTP 回归分别注入 README 改动、ignored 文件和两种 Git 元数据绕过，均要求委托 `blocked` 且不能进入实施。OpenCode 仍关闭，等待这版修正后的真实模型回归；一次静态/受控回归不能证明过程中绝无短暂写入，也不证明隔离目录之外不可写。

正式服务上的 Codex 委托 `dev-98f64f30a737b4c0ab18d2062c313bd8` 从同一小仓提交出发，方案 Run `gzrun-20260926-152934-e3603670` 保持 Git 差异为空，进入实施 Run `gzrun-20260926-153025-90502cb1` 后状态为 `awaiting_acceptance`。实施服务差异仅有 README 一文件，独立执行 `grep -nFx 'Smoke: codex-guard' README.md` 得到第 4 行，`git diff --check` 通过。

文件指纹守卫启用后，再以正式服务委托 `dev-f769ccffdc913e618c4e6b4052dd45c0` 做 Codex 小仓回归：方案 Run `gzrun-20260926-154932-3771002b` 成功，环境快照含运行前树指纹 `b708c0faa0058dfa04ddfbd81894d272a5a47b729ea19b6332ae6a048c9c6386`，结束后独立重算相同；委托随后进入实施 Run `gzrun-20260926-155058-e016397c` 并达到 `awaiting_acceptance`。服务实际差异仅 README 新增一行 `Smoke: snapshot-guard`，独立 `grep -nFx` 得到第 4 行，`git diff --check` 通过。它证明守卫未阻断这个有界 Codex 任务；OpenCode 修正后的模型级回归仍未完成。

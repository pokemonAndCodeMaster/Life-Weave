# 项目知识与外部开发接续：验证记录

核对日期：2026-09-26。候选应用使用独立数据库 `lw_candidate_05a7f122d6be`、端口 8011 和同一份候选源码；日常库 `lifeweave` 未用于测试写入。本文记录这次改进可复查的结果，不把候选事项当作日常事项，也不把主动上报当作自动捕获的工具轨迹。

## 用户路径

1. 新浏览器打开“知识与材料”，选“LifeWeave 项目”：列出清单中的 9 篇当前文档，打开 `docs/status.md` 可读全文和来源版本。截图：[项目知识](project-knowledge.png)。正式 CLI 的 `knowledge --source lifeweave-project` 和 `read-knowledge lifeweave-project:docs/status.md` 也返回同源正文及版本。直接请求历史档案作为该来源正文返回 409，避免旧判断混入当前规范。
2. 在候选库创建“LifeWeave 项目知识与开发接续”事项，并把已在进行的外部 Codex 会话关联该事项。页面“推进记录”可读主动登记的开始与验证阶段、Git 提交与工作区差异、选用材料版本及上报的检查。截图：[外部开发记录](external-development.png)。开始登记发生在代码修改之后，因此它**不证明此前的设计与实施命令曾被平台观察**。
3. 复核发现初版 `continue` 遗漏外部记录后，修复正式接续接口及网页“接着推进”面板。重启候选服务，再执行 `python scripts/lifeweave.py --url http://127.0.0.1:8011 continue item-f244ab01d6bf4540`，读回 `verification` 和 `started` 两条记录、所选材料版本、上报检查以及当时 Git 的 20 个修改和 8 个未跟踪文件；`runs=[]`，边界明示这些不是平台 Run。对话准备阶段也读取同一事项最近 10 条外部报告，完整接续接口保留全部记录。
4. 独立只读复核在修复前指出“推进记录有、继续事项没有”的反例；修复后对 CLI 接续路径和页面重新读取均确认可用。候选库及其事项是隔离验收材料，不能充当正式环境已运行的证据。

## 检查与边界

`LIFEWEAVE_TEST_DB=1 .venv/bin/pytest -q` 通过 81 项；`npm --prefix web test -- --run` 通过 41 项（15 个文件）。`npm --prefix web run type-check`、`npm --prefix web run build`、`python scripts/build_complete_guide.py --check` 与 `git diff --check` 均通过。集成测试覆盖当前规范清单、版本随原文变化、固定材料版本、外部会话真实 Git 观测、幂等请求、空间隔离和新会话接续。

日常服务升级前，两空间均无排队或运行中的 Run。服务停止后备份数据库和默认知识目录，分别保存为 `.runtime/backups/lifeweave-20260926-182640.dump` 与 `knowledge-20260926-182640.tar.gz`，再启动 8010；健康接口显示数据库 `lifeweave` 正常。正式库创建事项 `item-58363ef3851142d8`，外部会话 `external-d974db8448183ebb740c22dae29213ca` 从集成阶段开始登记。正式 CLI 找到 9 篇项目文档；新浏览器在桌面和 390px 手机视口打开项目知识全文和同一事项的接续记录，均无页面异常：[桌面知识](daily-knowledge-desktop.png)、[手机知识](daily-knowledge-mobile.png)、[桌面接续](daily-continuation-desktop.png)、[手机接续](daily-continuation-mobile.png)。候选库“只记录一个生活想法”也成功，仅创建 Idea，不创建开发会话或 Run。

正式会话开始时选入的 `docs/status.md` 内容指纹为 `f4eb2777518b`；修订当前状态说明后再次从正式 CLI 读取，得到 `591f5ec184cb`，全文包含新的正式服务核查。知识阶段报告也固定了当时 `docs/status.md` 和 `docs/architecture.md` 的版本。新版本可读不代表历史输入被静默覆盖：外部会话开始事件仍保留旧版本。

当前项目知识是按清单读取 Git 工作区文件，来源版本是内容指纹；本次候选截图中的提交还是修改前的基线。它没有持久增量索引、跨来源关联或单独的发布状态。历史档案留在 Git，知识页的当前来源不能直接打开历史正文；从文档链接追溯历史需到代码仓。外部开发报告只记录主动提交的阶段和服务当时可观察的 Git 状态；无法重建此前未上报的内部命令。日常服务此时使用已验证源码和前端构建，健康接口的应用版本仍为 `0.1.0`，不提供精确 Git 构建身份；最终源码提交和远端回读需单独核对。

# 本机 Codex Hook 真实烟测

日期：2026-09-26。测试在现有 LifeWeave 工程启动新的 `codex exec`，明确让它关联正式事项 `item-92989f3f9ca34660` 并只执行 Git 读取。正式服务当时处于运行状态，测试没有修改代码。测试命令对当前受审 Hook 使用 Codex 的 `--dangerously-bypass-hook-trust`，因此**不证明未来普通会话已完成持久信任**。

先用 `--sandbox read-only` 运行：Codex 确实执行了 Hook，但工具内访问 `127.0.0.1:8010` 被该沙箱拒绝，`external-start` 返回连接失败，未登记事项；Git 读取仍成功。这说明“Hook 被触发”和“LifeWeave 收到事件”必须分别验收。

第二次使用 `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`，并要求不改文件。`external-start` 成功产生 `external-18192f71158ccea2aff2cd0a8ee94818`；`git rev-parse --short HEAD` 返回 `dcf3647`。随后从正式 `external-list item-92989f3f9ca34660` 回读，该原生会话下有 `started`，以及两条 `source=codex_hook, phase=tool, toolName=Bash` 和一条 `source=codex_hook, phase=stop`。它们是平台收到的 Hook 请求，不是事后人工补写的阶段总结。

Hook 只发送原生会话、Turn、工具调用 ID/名称、模型、工具输入哈希和可识别的退出码；不发送提示、命令、参数或工具输出。服务在收到事件时独立读取当前 Git 提交和文件状态。当前 Bash 的原生响应未提供本程序可安全确认的退出码，因此页面如实显示“未报告”；Codex 最终文字中的成功判断不能自动替代这个字段。Hook 只对已通过 CLI 明确绑定且仓库一致的会话上传，未绑定会话静默跳过。已测试的 Event 不能代表 Codex 所有工具路径都能被 Hook 捕获，正常会话还需 Codex 对 Hook 的信任审查。

此次测试使用了[Codex 官方 Hook 文档](https://learn.chatgpt.com/docs/hooks)声明的 `PostToolUse`、`Stop` 输入字段和项目/用户级 `hooks.json`。第一次烟测时，本机另行配置的直连 `mcp.notion.com` 因 OAuth metadata 网络请求失败未启动。用户随后完成浏览器授权；新的 Codex CLI 会话 `01a0de18-eff6-78c3-9649-2a7fb25636de` 通过实际出现的 `codex_apps/notion.fetch` 工具读取项目入口，返回标题“LifeWeave｜项目与知识入口”。这证明本机 Codex 当前可经 Notion 应用连接器读取该页，但没有单独证明直连 `mcp.notion.com` 的调用，更不能当作 LifeWeave 后台自动镜像已获授权。

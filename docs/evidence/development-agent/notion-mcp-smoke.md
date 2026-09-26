# 本机 Codex 的 Notion MCP 读取

日期：2026-09-26。用户完成浏览器 OAuth 后，本机 `codex mcp list` 显示 `notion` 指向 `https://mcp.notion.com/mcp`，状态为 enabled、认证方式为 OAuth。随后启动一个新的临时 Codex CLI 会话，要求只使用名为 `notion` 的 MCP 读取项目入口页面 `3e7af682864481769d2decf36863c820`，不得使用应用连接器或网页。

JSON 运行事件中的工具名为 `mcp__notion__notion_fetch`；最后只返回页面标题 `LifeWeave｜项目与知识入口`，无工具错误。这证明当前本机 Codex 的直接 Notion MCP 交互式读取可用。会话使用 `--ephemeral`，不提供持久线程或后台上传证明。LifeWeave 服务端的自动镜像使用另一套集成令牌与根页面共享，当前仍未配置或完成真实上传回读。

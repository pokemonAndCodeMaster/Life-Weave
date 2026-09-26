已按已审方案完成，改动仅在本轮隔离工作树，未合并主仓。

- `scripts/lifeweave.py`：新增 `development-choices <itemId>`，发送一次无请求体 GET，完整输出缩进、保留中文的 JSON。
- `tests/test_agent_cli.py`：新增真实 `main(argv)` 契约测试，覆盖空间、自定义 URL、ID 编码、只读请求、JSON 透传和 HTTP 错误退出。
- `README.md`：补充调用示例和“不启动执行”说明。

验证结果：

- 默认 `python` 缺少 pytest；改用项目 `.venv/bin/python` 执行，**5 项测试通过**。
- `git diff --check` 通过。
- 新命令访问本机真实接口成功，返回该事项的开发选项。

交付基准：`2d70b2db51322ede29507940dddba5123d2ed95b`；差异为 **3 个文件，新增 71 行、删除 3 行**。

知识入口回读仍是原仓 README；新增说明仅在隔离工作树，尚未进入正式知识来源。本轮反馈为空，未调整目标。本次不验证 Codex 执行能力或 Notion 镜像，技术完成不代表事项已被用户接受。

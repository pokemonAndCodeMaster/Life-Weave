方案已完成。本轮仅核对源码，未修改文件；后续独立审阅通过后，可在隔离工作树实施这三个文件的增量，不合并主仓。

用户将能运行：

```bash
python scripts/lifeweave.py development-choices item-92989f3f9ca34660
```

命令只发送一次 `GET /api/lifeweave/{workspace}/items/{itemId}/development/choices`，打印完整、缩进且保留中文的 JSON。沿用现有 `--url`、`--workspace`、事项 ID 编码和错误退出行为，不创建开发委托。返回内容由现有服务决定，包括 Agent、执行器、推荐仓库、方法和知识引用。

实现顺序及责任：

1. **`scripts/lifeweave.py`**：注册 `development-choices` 子命令和必填 `item_id`；增加明确的分发分支，复用 `call()` 发送无请求体的 GET，再复用统一 JSON 输出。
2. **`tests/test_agent_cli.py`**：沿用现有动态加载方式，调用真实 CLI 的 `main(argv)`，仅替换网络边界 `urlopen`。检查 personal 默认空间、team 与自定义本机 URL、特殊字符 ID 编码；断言请求次数为一、完整路径正确、方法为 GET、请求体为空、返回码为零及输出 JSON 与响应一致。补充 HTTP 错误返回非零的契约检查。测试执行参数解析与请求构造，不以源码字符串匹配代替行为验证。
3. **`README.md`**：在“在新的本机 Agent 会话接续”命令示例中加入上述调用，并说明它只读查询开发选项，不启动执行。这是本次唯一知识文档变化。

后端接口已存在于 `src/lifeweave/development_router.py:35`，业务响应由 `src/lifeweave/development.py:52` 提供，无需修改接口、数据库、网页或 Notion/Linear 模块。

主要风险是新命令误落入 CLI 末尾的运行创建分支，或空间、路径编码处理错误。明确分支和“唯一 GET、无请求体”的契约断言共同防止这些回归；测试响应包含中文、嵌套对象和空值，以检查 JSON 完整透传。

实施后运行：

```bash
python -m pytest -q tests/test_agent_cli.py
git diff --check
```

再核对差异仅涉及指定三个文件，并留下实际测试结果、交付版本和隔离工作树差异。该测试验证 CLI 路由契约，不代表真实后端、Codex 可用性或 Notion 镜像已经验收。

本轮可核验证据：基准提交为 `2d70b2db51322ede29507940dddba5123d2ed95b`；现有 CLI 帮助尚无该命令；当前 `git diff --check` 通过，无已跟踪文件差异，存在未跟踪的 `.agents/`、`.lifeweave/`。未运行新增测试，因为尚未实施。

自检：方案限定三个文件，覆盖用户行为、接口、实施顺序、风险、验证及知识变化。本轮固定纠偏反馈为空，无需调整已接受目标；本方案不代表独立审阅通过或事项已被业务接受。

尚未解决的问题：沙箱以 `Operation not permitted` 阻断本机 HTTP，`continue`、`knowledge` 和 `read-knowledge` 未能回读当前服务，因此依据本轮固定事项与已选知识快照、仓库源码制定方案。无必须由用户补充的实现决策；新增测试与实施后的检查留待后续可写阶段完成。

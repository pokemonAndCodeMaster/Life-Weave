# 验证命令与边界

- 完整改动后，`LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest -o addopts='' -q`：151 passed；使用一次性测试库，不重置用户库。
- 独立审查修复后，`LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest tests/test_workflow_protocol.py tests/test_work_view.py -o addopts='' -q`：26 passed。修复的同一步新旧交付反例包含在内。
- `npm --prefix web test`：33文件、143 passed；独立审查修复后再次通过。最后固定file/output链接的页面聚焦回归7项通过。
- `npm --prefix web run type-check`、`type-check:node`、`build`通过；最后页面修改后重新类型检查与build。Mermaid拆包体积提示保留，不视为已解决的性能优化。
- `npm audit --json`：全部依赖漏洞0；独立审查也核对生产依赖0。
- `python scripts/build_complete_guide.py --check`：11份当前来源正文一致，本地文档链接有效。
- `git diff --check`通过；代码交付由临时Git索引验证补丁回放，原仓索引不被捕获动作改变。

浏览器证据区分真实本机事项与隔离夹具；仅390px视口验证，不代表手机网络可连通。真实论文两项id/status/payload前后精确一致；媒体缓存和新步骤记录是本轮必要新增，不声称整个数据库字节不变。

生产服务为主Agent按标准脚本重启并拥有的127.0.0.1:8010，前端dist重新构建。数据库与知识备份见.runtime/backups；该目录不进入版本库。没有执行用户接受事项、发布正式知识或Linear写入。

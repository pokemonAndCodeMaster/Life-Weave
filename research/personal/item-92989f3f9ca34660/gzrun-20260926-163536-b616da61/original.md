已在本轮隔离工作树完成实现，未修改或合并主仓。

实际改动 **3 个文件，新增 492 行、删除 25 行**：

- `PluginProcess.vue`：调用独立展开、固定版本与绑定差异、安全引用与错误说明、同事项 Run 和事件分页阅读。
- `api/plugins.ts`：补充计划的事项身份字段。
- `PluginProcess.test.ts`：新增安全过滤、归属检查、分页和请求竞态等测试。

审阅意见均已落实：支持 `output_ref.runId`；事件摘要和错误原文不直接展示；缺少绑定明确说明“无法比较”。纠偏反馈为空，没有扩大范围。

验证均通过，退出码为 **0**：

- Vue 类型检查。
- 相关组件测试：**23 项通过**。
- 生产构建、差异检查。
- 真实事项页面：22 条调用、43 条事件；键盘展开、刷新保留状态及 390px 窄屏检查通过，无写请求或浏览器错误。

可核验材料：[完整补丁](/tmp/lifeweave-plugin-process.patch)、[测试记录](/tmp/lifeweave-plugin-tests.log)、[页面检查](/tmp/lifeweave-plugin-browser.log)、[窄屏截图](/tmp/lifeweave-plugin-run-mobile.png)。

正式知识正文和 Notion 未修改，已回读确认知识版本；文档更新留待后续授权范围。原始事件全文不在本次展示范围。技术完成不代表事项已被业务接受。
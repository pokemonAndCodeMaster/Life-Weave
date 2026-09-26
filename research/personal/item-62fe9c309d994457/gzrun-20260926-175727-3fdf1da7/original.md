建议把改动限定为“固定代码交付”区的两项完整版本展示与复制，复用现有接口。本轮只完成源码和文档核对，没有修改文件或运行测试。

**现状与依据**

核对基线为 `047fe3857f0400dbd710d1735b5a1c17cc6cf2ec`；四篇项目文档的 SHA-256 均与本轮固定输入一致。

- [DevelopmentDelivery.vue](/home/yyh/project/lifeweave/.runtime/executions/personal/gzrun-20260926-175727-3fdf1da7/repo/web/src/features/lifeweave/components/DevelopmentDelivery.vue:51) 已拿到完整值，但基线提交和包哈希都通过 `slice(0, 12)` 显示。
- [交付接口类型](/home/yyh/project/lifeweave/.runtime/executions/personal/gzrun-20260926-175727-3fdf1da7/repo/web/src/features/lifeweave/api/development.ts:43) 已包含 `baseRevision`、`artifactSha256`。后端确认前者来自委托固定提交，后者是完整 ZIP 字节的 SHA-256。
- 当前使用说明仍让用户通过开发者工具取得部分完整版本，适合补充直接复制入口。

**用户将看到的行为**

交付区展示两个有明确标签、可选择的完整值，长字符串允许换行：

| 标签与按钮 | 复制内容 |
| --- | --- |
| Git 基线提交 ·「复制完整基线提交」 | `delivery.baseRevision` |
| 交付包 SHA-256 ·「复制交付包 SHA-256」 | `delivery.artifactSha256` |

复制只写入原始完整字符串，不附带标签、空格或换行。成功后提示具体哪项已复制；失败时显示“复制失败，请选择完整值手动复制”，完整值始终可见。

没有固定交付包的历史委托保持原有提示。这里的包哈希指 ZIP，不是 `manifest.patchSha256`；基线提交也不是集成后的目标提交。

**最小改动与实现顺序**

1. 修改交付组件：加入完整值展示、两个原生按钮、组件内复制方法和独立状态提示。直接响应点击调用 `navigator.clipboard.writeText`，等待成功后才报告成功；不可用或拒绝时提供手动复制提示。状态区域使用 `aria-live`，按钮支持键盘操作。
2. 处理局部布局与状态：窄屏换行；复制状态不占用下载、核对和接受操作的 `busy/error`；交付身份或版本改变时清除旧提示。
3. 更新 [docs/development.md](/home/yyh/project/lifeweave/.runtime/executions/personal/gzrun-20260926-175727-3fdf1da7/repo/docs/development.md:172)：说明入口、字段含义及失败后的手动操作。原来的网络响应说明仍用于上下文、材料版本和无交付包场景。

预计修改一个 Vue 组件和一篇说明；验证完成后在 `docs/status.md` 简记实际结果。无需新增依赖、公共复制组件、数据库字段或接口。继续使用：

`GET /api/lifeweave/{space}/development/{assignmentId}/delivery`

复制动作不发业务写入请求。

**验证办法与风险**

- 在实际页面分别复制并粘贴，逐字符比较接口完整值，尤其检查第 12 位之后的内容；连续操作、多条交付之间不能串值。
- 下载同一 ZIP，以 `sha256sum` 核对复制的包哈希；将基线值与包内 `manifest.json.baseRevision` 比较。
- 检查剪贴板写入拒绝、API 不可用时不会出现成功提示，并能手动选择完整值。
- 检查桌面、窄屏、键盘操作，以及下载、目标提交核对和接受入口仍可用；覆盖个人与团队空间的同一组件。
- 实施后运行 `npm --prefix web run type-check`、`npm --prefix web test`、`npm --prefix web run build`。本次低影响改动优先用真实页面验证，不另建测试框架。

主要风险是复制错字段、复制截断值、浏览器拒绝写入以及长字符串撑开布局。上述字段绑定、失败处理和页面检查分别覆盖这些风险。

**自检及尚未解决的问题**

已静态核对：服务端 `plan_only` 分支在创建实施 Run 前进入 `plan_ready` 并返回；[现有门禁测试](/home/yyh/project/lifeweave/.runtime/executions/personal/gzrun-20260926-175727-3fdf1da7/repo/tests/test_development.py:189) 包含“不建立实施 Run”的断言。本轮未执行该测试，也不能提前宣称本次运行已通过平台门禁。

开始和结束的 Git 状态一致，仅有原有未跟踪目录 `.agents/`、`.lifeweave/`，已跟踪文件无差异。本轮纠偏反馈为空，无前轮成果需要修订。

方案无待用户裁决的阻塞问题。浏览器剪贴板实际表现、页面验收及本次运行最终门禁状态仍待后续验证；本轮未实施、未更新知识、未作业务接受。
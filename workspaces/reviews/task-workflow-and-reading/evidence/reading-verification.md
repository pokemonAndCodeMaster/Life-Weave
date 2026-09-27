# 内部文档阅读：实施与核查证据

2026-09-27，在当前候选工作树及本机 8010 页面核查。本记录是实施者自验，不替代独立审查或用户接受。没有修改生产数据库；浏览器拦截非 GET/HEAD/OPTIONS 请求，记录到的写请求为 0。

## 已交付行为

- 当前知识与固定工作产物共用内部阅读页。固定产物保留事项、产物、文件、版本及返回定位，不自动写入知识。Markdown 与源码/文本分别排版，后者保持原文并可复制。
- 共用 MarkdownBody 继续使用 KaTeX；Mermaid 使用精确锁定的 `11.17.2`，按需载入、strict 配置、禁用正文自定义配置与远程资源、清理生成 SVG。图与图片可放大；失败保留可读源码；迟到请求不覆盖后续文档。
- 当前文档只为实际引用的图片生成 `/library/asset` 地址；带 sourceId、documentPath、version、path。图片受注册来源根、正文清单、当前指纹、路径/符号链接、媒体类型和 10 MB 限制。已有 run 图片映射优先，不映射为偶然同名的当前文件。
- 知识页保留完整包下载；固定研究包是 Markdown 与资源。下载阅读版 HTML 明确标注需要连接工作台，不称作离线包。

## 真实页面结果

| 检查 | 结论 | 亲自核查证据 |
|---|---|---|
| 项目架构中文框图 | PASS | `docs/architecture.md` 的 2 幅 Mermaid 实际渲染；放大、125% 缩放、Tab 焦点限制、Escape 归位与背景滚动恢复通过。[页面](architecture-final.png)、[大图](architecture-enlarged-final.png)、[结果](final-browser-results.json) |
| 章节跳转 | PASS | 点击目录后焦点到实际标题“成果的异地归档”。[结果](final-browser-results.json) |
| GSSM 步骤 → 固定正文 | PASS | `item-de7785d0790445d8` 图节点 → 文档目录 → `report.md`，87 处 KaTeX，图片自然宽 848 px；图源为该固定产物受控地址。[页面](gssm-fixed-image.png)、[结果](fixed-browser-results.json) |
| 图片键盘操作 | PASS | 实际研究图与当前文档图 Enter 放大、Tab 限制、Escape 关闭并回原按钮。[研究结果](fixed-browser-results.json)、[当前结果](current-browser-results.json) |
| 返回及刷新 | PASS | 返回原事项打开原步骤，URL 保留 `step`、`output`、`file=report.md`；刷新内部阅读 URL 保留固定版本。[结果](fixed-browser-results.json) |
| 错误版本 | PASS | GSSM 错误版本显示“指定成果版本与保存的交付不一致，请返回产物目录选择版本”，无旧正文。[结果](fixed-browser-results.json) |
| 非 Markdown 原文 | PASS | 同固定交付的 `files/1a1efb53fc9582b6-code-evidence.txt` 71,594 字符保持原文，复制内容逐字一致，没有当作标题、公式或 SVG。[结果](final-browser-results.json) |
| 当前项目相对图片 | PASS | `docs/item-workspace-design.md` 真实引用 `../workspaces/reviews/task-workflow-and-reading/evidence/step-modal.png`，受控读取、自然宽 1440 px；旧版本、未引用及越界请求明确 409。[页面](current-relative-image.png)、[结果](current-browser-results.json) |
| 真实完整包 | PASS | GSSM ZIP 2,116,714 字节、32 个条目、8 张 PNG；`report.md` 引用的本地图片确实存在。未把其他来源 HTML 当作离线阅读首页。[清单核查](offline-bundle-resources.json)、[下载结果](fixed-browser-results.json) |
| 查看当前原文 | NOT_PROVEN（真实交付） | 前端根据可选 `currentSource` 跳当前知识的组件测试通过；核查时 output_files 未返回该字段，没有将真实入口声称为已验证。 |

固定 GSSM 版本为 `fec353264fb26271deaa183e66ba4645cc934e3c214bf44f7447d7666ed81520`。当前知识指纹会随文档正常更新；上表记录的是核查时版本。

## 隔离夹具与自动验证

这些是临时目录或浏览器拦截的响应，不是生产知识或真实失败记录。

- 浏览器夹具验证了 Mermaid 语法错误、坏公式、缺失图片、禁止外部图的明确降级；外部图片请求为 0。12 列宽表在 670 px 阅读区内横滚，表宽 4,570 px，页面仍为 1,280 px；焦点放到表格后 ArrowRight 将局部 scrollLeft 移到 40。[夹具截图](isolated-failure-table.png)、[结果](final-browser-results.json)。期间修正了旧全局表格样式导致的窄列与内部滚动位置问题。
- `.venv/bin/python -m pytest tests/test_library_assets.py`：4 通过。使用临时目录和无数据库的 FastAPI 测试服务；覆盖真实二进制接口、编码相对路径、正文引用约束、当前指纹、越界/隐藏路径、内外符号链接、媒体类型、SVG 危险内容、10 MB 边界及已有 run 来源优先。
- 阅读相关 5 个 Vitest 文件：22 通过。覆盖已有公式/图片回归、图失败与迟到结果、当前来源迟到警告、固定版本请求/返回/409、同空间受控图地址（含拒绝 `//外域`）、纯文本复制和章节/表格结构。
- `npm run type-check`、`npm run type-check:node`、`npm run build` 通过；最后表格 CSS 调整后重新构建及实际浏览器复测通过。`git diff --check` 通过。
- `npm audit` 为 0 个已知漏洞。Mermaid 动态依赖中有一个 662.70 kB（gzip 143.23 kB）拆包，构建仍提示超过 500 kB；未声称做过移动网络性能验收。

测试文件：`tests/test_library_assets.py`；`MarkdownBody.test.ts`；`components/reading/MarkdownReading.test.ts`；`utils/mermaidRenderer.test.ts`；`pages/KnowledgePage.test.ts`；`pages/KnowledgeDocumentPage.test.ts`。

技术参考：使用 [Mermaid 官方 API](https://mermaid.js.org/config/usage.html) 的 initialize/render，并核对本地安装的 11.17.2 类型；本次没有创建自制 Mermaid 解析器。实现入口为 `document_assets.py`、`library.py`/`library_router.py`、`KnowledgePage.vue`、`MarkdownBody.vue` 与 `components/reading/`。

## 集成补充

阅读侧初次交接时 `currentSource` 的真实后端映射尚未提供；随后集成负责人按已登记知识来源与交付实际仓库补齐。已在实际固定的 `docs/item-workspace-design.md` 中核对图片1440px和“查看当前原文”，见 [集成浏览器记录](integration-browser.json) 与 [固定项目文档截图](fixed-project-document.png)。此补充不把组件夹具冒充真实运行。

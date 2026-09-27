# 步骤详情两项修复独立复核

结论：PASS。2026-09-27，Chromium 真实页面与真实 GET API；未修改仓库或生产数据，未接受交付、保存意见或启动委托。浏览器设置只读请求守卫，本轮未出现任何写请求或被拦写请求。

## 390px 研究正文：PASS

在 `http://127.0.0.1:8010/lifeweave/personal/items/item-de7785d0790445d8/overview` 点击“委托研究与整理”，滚动实际正文内 Git 哈希、12 个展示公式、6 张表格、1 张图片及正文底部。

所有观测点 viewport / document.scrollWidth / body.scrollWidth 都是 390px。完整 40 位哈希 `0ee2542eb28e50948cae8561332365d5f76e29d4` 换为两行，没有省略或截断；两个文本矩形均位于内容宽度内。7 个较宽公式在 292px 容器内局部横向滚动，可到达各自最右端；6 张表格为 292px，内容换行，没有撑宽页面。原图真实加载，原始 848×458，显示约 292×158。

证据：`results.json` 的 `mobile`；截图 `mobile-hash.png`、`mobile-formulas-0-left.png` / `mobile-formulas-0-right.png`、`mobile-tables-0-left.png`、`mobile-image-0.png`、`mobile-end.png`。这些截图已由审阅者亲自查看。

## 轮询保留差异与正文：两入口均 PASS

概览页：打开 `item-62fe9c309d994457/overview`，点击“实施与交付”，点击“查看实际 Git 差异”，把差异内部滚动到 180px；等到真实 `/api/lifeweave/personal/items/item-62fe9c309d994457/work-view` GET 返回 200，距展开约 11.94 秒，再观察 1.2 秒。

成果页：直接打开同一事项 `/outputs`，选择同一代码交付，展开差异并同样滚动；真实 work-view GET 在约 11.25 秒后返回 200，再观察 1.2 秒。

两个入口都保持：差异 details.open=true；reader、Markdown、首段、diff 都是原 DOM 节点；MutationObserver 没有发现移除节点；正文 442 字符及 SHA-256 不变；差异 13,345 字符，内部 scrollTop=180 不变。展开后网络日志都只有该次 work-view GET，没有重新请求交付或 Run 正文，也无页面错误。

证据：`results.json` 的 `development.overview` / `development.outputs`，包含请求时间、200 响应、正文哈希、节点身份及移除记录；截图 `development-overview-before.png` / `development-overview-after.png` 和 `development-outputs-before.png` / `development-outputs-after.png`。

## 实现对应

当前 `MarkdownBody.vue:87` 的 `min-width:0; overflow-wrap:anywhere` 使长哈希在正文容器内换行。`WorkOutputReader.vue:55` 使用 Vue 多源 getter 数组，按标识、版本、状态等原始值比较，避免 work-view 轮询替换同值对象时重新执行 load 清空 diff。复核的是父 Agent 最新修正后的构建；实际加载 `ItemDetailPage-BAolpmbc.js`。

复现脚本：`verify.py`。复核仅覆盖本任务指定的两个修复和两个入口，没有扩大到平台其他能力。

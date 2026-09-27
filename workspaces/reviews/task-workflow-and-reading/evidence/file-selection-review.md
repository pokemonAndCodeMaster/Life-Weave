# selectFile 只读交付复核

结论：**pass**（限定 `ItemDetailPage.vue::selectFile` 本次固定产物选择）。没有发现 fail。真实新增交付写入生产数据的完整链路为 **not_proven**；本次仅以浏览器 route mock 模拟视图变化，未写生产数据。

候选：LifeWeave 当前提交 `b2b0e2757fa32e14fa2fc46fe2711f58544366f8`；`web/src/features/lifeweave/pages/ItemDetailPage.vue` SHA-256 为 `71b91161ab2b5de5602e40e0a36c0312f7cbf793da00563f75c9480ac8fd949e`。复核结束时该文件工作树无差异。批准方案原文位置：`f108a48a9a80f5256b99514c28776fce2e32fa26:workspaces/reviews/task-workflow-and-reading/review.md`。

亲自操作与观察：

1. 使用系统 Python Playwright 的 Chromium，打开主事项 `overview?step=workflow-artifacts`。此步骤真实默认产物为 `artifact:output-49ae40cec72d0f1fc4391a1584867802`，固定版本 `ecb02b3d581cd749386b65a87242d1652d5845b003b586efd089fc7f0e60bbad`。
2. 展开“代码变更”，在“查找路径”输入 `src/lifeweave/output_files.py` 并点击该文件。地址变为 `?step=workflow-artifacts&output=artifact:output-49ae40cec72d0f1fc4391a1584867802&file=src/lifeweave/output_files.py`；实际 `/outputs/file` 请求同时带原 `outputId`、路径和固定版本，差异内容显示。**pass**。
3. 浏览器重新加载该地址，地址和选中状态保持；再次发出的 `/outputs/file` 请求仍是上述原产物与版本。**pass**。
4. 在浏览器内只对本事项 `work-view` GET 安装 route mock：将 `workflow-artifacts.outputIds` 临时模拟为 `[artifact:output-ac40015fca565f4cb7e7387403ee9661, artifact:output-49ae40cec72d0f1fc4391a1584867802]`。第一个 ID 是该事项已有的另一份真实代码产物，用作模拟的“更靠前新产物”，没有改服务端记录。等待一次 12 秒自动轮询后，页面显示两份可选产物，但 URL 仍含原 `output` 与 `file`，阅读标题仍为“固定交付、完整目录与受控文件读取”，文件仍被选中；期间文件请求没有转向模拟的新产物。**pass（模拟）**。
5. 在同一 mock 下重新以无 `output` 的步骤地址进入，默认阅读确实切到模拟的首项“步骤弹窗、产物目录与固定选择”；随后在页面明确选择旧产物，URL 写入旧 `output`。再次重新加载后，仍阅读旧产物。**pass（模拟）**。

边界：未新建事项、外部开发会话或生产交付；未重启服务、未运行全量测试或评审无关代码。真实生产中新交付到来后的端到端写入链路不由这次只读 mock 证明。

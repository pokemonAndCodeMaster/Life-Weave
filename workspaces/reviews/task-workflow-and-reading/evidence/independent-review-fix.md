# 独立复核：步骤默认交付与弹窗文件差异

**结论：pass（仅限本次受影响的关闭条件）。** 当前候选在同一业务步骤多次成功后默认打开最新一次有效的固定交付；失败、重试、被拒绝或旧计划的迟到报告没有夺取默认。用户手选旧交付及从文档返回的定位保留。点击代码目录文件后，真实文件 diff 在有界步骤弹窗内显示，长差异在内部滚动。此结论不是整轮工作流与阅读方案的全量验收。

| 关闭条件 | 结果 | 亲自执行的动作与观察 | 边界 |
| --- | --- | --- | --- |
| 多次成功后默认最新有效固定交付；失败、重试、拒绝、计划修订与迟到报告不夺取默认 | pass | 只读读取真实事项 `item-7547b65b4f704829` 的 `/work-view`：`workflow-protocol` 三次成功报告按时间为 21:26:06、21:34:48、21:38:57，节点首项是最后一次的 `artifact:output-094b172d09b65c49efd2a34cb94074a8`。全新 Chromium 从概览点击“两入口与步骤交付”，弹窗实际打开该产物及固定版本 `3280208d135d…`。另用一次性 PostgreSQL 测试库制造同一步初始失败→重试→成功 A→再次失败→重试→成功 B→引用 A 的拒绝报告→验收要求修订→成功 C→旧计划迟到报告。B 后默认 B、A 次之；修订后默认 C；拒绝和迟到报告 `applied=false`，未夺取默认，旧 A/B 仍在事项成果索引。 | 隔离库中的 A/B/C 是独立构造的验证记录；真实事项证明了多次固定代码交付的页面默认结果。没有向生产事项提交测试报告。 |
| 旧交付可查，显式选择和返回定位保留 | pass | 真实页面在同一步手选旧交付 `artifact:output-8ecebcf3e39c7f090962ac15a44ec628`，URL 写入 `output`，阅读区变为固定版本 `ce762c7f727e…`；刷新后仍是旧交付。展开“文档”并打开 `implementation-result.md`，进入内部知识阅读页，URL 带旧产物 ID、文件路径与版本；点击“返回原步骤”，回到 `step=workflow-protocol&output=…8ece…&file=implementation-result.md`，旧交付与文档选中状态仍在。 | 修订后的旧版本在隔离库 `/work-view.outputs` 中保留；本次没有再为隔离库启动浏览器。 |
| 点击代码文件可在固定高度弹窗直接阅读差异，不撑长主页面 | pass | 真实页面点击 `workflow-artifacts`，展开“代码变更 → src → lifeweave”，点击 `output_files.py`。URL 定位到 `file=src/lifeweave/output_files.py`，弹窗显示该路径及“本次差异”，内容起始为 `--- src/lifeweave/output_files.py` / `+++ src/lifeweave/output_files.py` 和 `+1,365` hunk。刷新仍选中该文件。1360×900 浏览器中弹窗高 810 px、正文可视高 674 px/滚动高 2017 px、diff 可视高 504 px/滚动高 6871 px；主页面高度从 1373 px 到 1339 px。 | 实测一个长文本差异；二进制/重命名等目录边界不属于这次定向修复复查。 |

浏览器这几次操作未观察到 page error 或 HTTP 4xx/5xx。只复用父 Agent 拥有的 `http://127.0.0.1:8010` 服务，没有重启或停止它。隔离脚本为 [证据](independent-fix/lifeweave_review_scenario.py)，以 `LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest -q -s /tmp/lifeweave_review_scenario.py` 执行，结果 `1 passed`；它使用 `tests/test_live_database.py` 的 `database_client` 创建并销毁一次性数据库。这里的通过依据是上述状态和页面结果，不是测试数量。

审批身份：修改前方案 Git blob `4554ea26e240b3d1bdcdf2404891b9a20c222957`；`f108a48a9a80f5256b99514c28776fce2e32fa26:workspaces/reviews/task-workflow-and-reading/review.md` 的 blob 与其一致。Diff 基线为 `89959e1b263405b9f0d76d7e6dee135141c638a7`。候选为该基线上的未提交工作树；相关文件 SHA-256：

```text
864d0bb9bec670095febe9c850015dd12f8c36fa23ac4ac58badb937c443dedc  src/lifeweave/work_view.py
eeb33c3d5f46047dc64e8c700490fd11a285b6cc3169e3dbf2e504a891048030  src/lifeweave/work_step_reports.py
aa02e638c2e61a3085755b59600c00c96125a4964193b468cca55afab7dcc520  src/lifeweave/development_delivery.py
4f71d92555b42d277a49753a39416c9f21e9ecc8c986b9d83c3d1db5c8c6dc40  src/lifeweave/output_files.py
58bf7f025dcc4c966a44efc72c1e420293593fce2f6d8434ab178f57ac298c01  web/src/features/lifeweave/components/workspace/WorkOutputCatalog.vue
5ac6c76304074e8289ebe204834174217b36331fae5b9ef3078e52662c03e682  web/src/features/lifeweave/components/workspace/WorkFileDiff.vue
3ea45f0a084dc99b727192fa1e14bd0144fd472e388d0905e2686a0bb930b07e  web/src/features/lifeweave/components/workspace/WorkFileTree.vue
a84f1cab990ffdb1f12b655def155852ffe4a6738dbd2025c5dfb6563326cc6a  web/src/features/lifeweave/components/workspace/WorkNodeDetail.vue
adad49406a9689cba808a571a7446ec2423bb75f9a2f4547a1a8592fd8f299ae  web/src/features/lifeweave/components/workspace/WorkStepDialog.vue
a802e1e442db93abffc3c36501dfcd19992d8b5c1395fd3c11a323a711d83e94  web/src/features/lifeweave/pages/ItemDetailPage.vue
```

只读源码核对的关键链路：`work_step_reports.py` 将不满足要求或旧计划报告保留为尝试但不应用；`work_view.py` 将最后一次已应用的成功交付排在节点产物首位；`WorkNodeDetail.vue` 默认读取首项，同时接受 URL 指定的旧产物；`WorkOutputCatalog.vue` 根据固定目录选文件，`WorkFileDiff.vue` 读取固定文件 diff；`WorkStepDialog.vue` 限制弹窗高度并让正文内部滚动。

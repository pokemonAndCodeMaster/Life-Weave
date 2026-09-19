# PDF 字符存储修复独立交付复核

**结果：fail。候选 `7ee164b` 已避免 NUL 事件与结果使运行失败，但成果下载版本与正文不一致，且正常成果阅读入口没有说明字符替换。**

本复核未参与施工，未修改实现或审查单。批准输入为 `10d326d` 的根目录产品定义 v1.0 第 8、10、12、13 章，以及 `workspaces/reviews/lifeweave-next-stage/review.md` 中网页研究可用版原方案。候选 Diff 为 `032a029..7ee164b`，本轮关闭范围限于 PDF NUL 事件/结果存储及它的直接消费者，不重新裁定全部 G1。

| 关闭条件 | 结果 | 亲自执行的动作与观察 | 需要怎样处理 |
| --- | --- | --- | --- |
| 本机与 HTTP 正式 worker 入口不因 NUL 终止 | pass | 随机临时 PostgreSQL 库、全部真实迁移；完整 `LifeWeaveWorker.execute_once()` 分别使用 `ServiceWorkerClient` 与 `HttpWorkerClient`（真实 TCP 8015），确定性执行器先发含 NUL 的 PDF 提取事件，再发后续事件，最后返回含 NUL 的结果；两种运行均 succeeded，后续事件保存 | 保留 |
| summary、嵌套 payload 可读且原始 JSON 可还原 | pass | summary 中 NUL 变为 ␀；从 Base64 解码得到完整原事件且逐值相等；含 NUL 的键与原有 ␀ 键均保留，不因碰撞丢成员 | 保留；原证据是语义等价 JSON，不是原 HTTP 报文逐字节副本 |
| result/result_payload 保存且研究成果可读 | pass | 完整 worker 最终结果写入真实数据库；正式 research-output API 和 Chromium 事项成果页均显示完整正文，正文含 ␀，浏览器无 pageerror | 保留 |
| 无 NUL 文本不改，字面转义不混同 | pass | 两条传输各增加无 NUL 对照；正文、字面 `\\u0000` 与原有 ␀ 均保持，不增加存储元数据；有 NUL 时原始 JSON 可区分原有 ␀ 与替换产生的 ␀ | 保留 |
| 原输入 provenance、租约与跨空间保护 | pass（本范围） | 两条路径运行前后 selectedInputs 不变；已结束租约下事件写入 403、错误 worker token 回报 403、跨空间读 run 404；源码确认 fixed_input_keys 过滤与 SQL 租约约束仍共用原 owner | 不以此替代此前全量权限/并发复核 |
| 声明的成果版本对应可读取原文 | **fail** | worker 的 result.txt 原始字节哈希为 `sha256:f5a6beca69bc41ea7d916ace1184f00d8dfe564ee557d1f0cd677576613c4390`；`GET /artifacts/result` 的 `X-Artifact-Version` 与 ETag 声明该哈希，但返回正文已将 NUL 替换为 ␀，实际哈希为 `sha256:360a9d2c73a0b6f2c9922a59b5db0da07b87ed2ca7163974f128d03e6c0c3748`。本机、HTTP 两条路径均复现；无 NUL 对照均匹配。页面“审阅固定版本”仍关联原始哈希 | 原始产物与阅读投影应分别标识；下载返回与声明哈希匹配的字节，不能悄悄换正文而保留旧版本 |
| 明确显示替换和原证据范围 | **fail（正常成果页）** | 当前 API 的 environmentSnapshot/payload 有 note 和 Base64；但研究成果投影没有该说明字段。实际打开事项“成果与验证”，看到 `ADEn␀等式`，没有 NUL、替换、原始证据的解释或入口。同页原有 ␀ 也完全相同 | 将存储投影说明和原证据入口传到正常阅读消费者；不能仅把说明藏在原始运行 JSON 中 |

两个阻断均是存储修复的直接下游问题，并非论文内容质量判断。事件存储改善是真实的，但不足以关闭全部交付条件。

## 实际执行与证据

- 读取源码：storage_text.py、repository.py、service.py、worker.py、runtime router/models、research_outputs.py、API app/迁移入口、ResearchOutputPanel.vue、RunsPage.vue。
- 回放：[pdf-storage-replay.py](pdf-storage-replay.py)。命令：`PYTHONPATH=. .venv/bin/python docs/evidence/web-research/pdf-storage-replay.py`。脚本只创建随机 `test_pdf_review_*` 数据库；8015 需空闲。
- 首轮四个独立运行：[原始观察](pdf-storage-observations.json)。其中两个含 NUL，两个无 NUL；哈希匹配结果为 false/true/false/true。
- 再次运行并亲自访问浏览器：[浏览器及 API 观察](pdf-storage-browser-observations.json)、[成果截图](pdf-storage-browser.png)。同样四个运行重现哈希结果；页面无脚本错误。
- 浏览器第一次启动时默认缓存版本不存在；改用已安装的 Chromium 1208 后完成。此为复核环境配置问题，不计产品缺陷。
- 未调用付费模型，未测试论文算法正确性。本次不涉及新增依赖，未重复依赖审计。
- 每次 finally 均停止自有 8015 server、删除自有随机数据库和临时执行目录；JSON 记录清理结果。未写入或停止 8010/8011，未访问日常数据库。证据不含注册 token/worker token/认证文件。

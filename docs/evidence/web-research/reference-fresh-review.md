# G1 来源保真独立复核：cd8c709

结论：**fail**。真实旧采纳知识的“来源记录”现已能正确打开，原文和版本未被改写；但复杂来源链接在成果成为知识后仍失去运行归属，带行号来源返回 400，原成果中的含空格和中文图片也无法显示。这些是 A04/A06 的实际结果失败，不能用简单来源通过或测试总数覆盖。

本复核由未参与施工的新上下文完成，先读取批准身份 `10d326d` 的根目录《LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md》A01—A09 与 `workspaces/reviews/lifeweave-next-stage/review.md` 最后施工方案，再核对候选 `cd8c709742de4e22e88de41a0463566d4af2fae2`。Diff 基线为 `10d326d`。本报告只冻结该候选的失败，不为后续修复背书。

## 影响接受的三个反例

1. **含空格或中文的来源在知识页点不开。** 合成成果包含 `[带空格来源](<research/source one.md>)` 和 `[中文来源](research/来源.md)`，文件真实存在于所属 run。通过正式知识候选接口提交后，在真实事项页面展开候选并点击“接受并更新知识原文”，进入正式知识页。两条链接仍为相对地址，亲自点击分别请求错误的知识路径 `研究/research/source one.md`、`研究/research/来源.md`，均 **404**，页面显示 `Request failed with status code 404`。同一错误存在于候选、Library 修订阅读、正式知识和下载 HTML；下载 HTML 把它们固定成错误知识 URL。[实际点击与 HTTP](reference-fresh-review.json) 的 `actual_clicks`、[空格失败截图](reference-fresh-click-space.png)、[中文失败截图](reference-fresh-click-unicode.png)。原因是候选提交时 Mistune 产生百分号编码的映射键，MarkdownBody 在 Marked 的 `walkTokens` 阶段按另一种编码形式查询。直接请求错误的前端相对 URL 会得到 SPA HTML 200，本复核没有将这个 200 当作来源可读。
2. **带行号来源在成果页正常，成为知识后失败。** `[行号来源](research/source.md:2)` 在原成果页由 `sourceBase` 去除行号；知识映射却把 `:2` 当成文件名。亲自点击知识链接打开 `/source?path=research%2Fsource.md%3A2`，返回 **400**“此类型不支持在浏览器阅读”。此错误映射还进入下一任务的提示词与材料清单。定位：候选版本 `src/lifeweave/research_references.py:17` 与 `MarkdownBody.vue:29`、`:33` 行号处理不一致。[HTTP、DOM 和下游快照](reference-fresh-review.json)。
3. **原成果页复杂图片加载失败。** 同一成果的普通图和括号文件名图可显示；含空格、中文、已编码空格以及引用式含空格图显示“加载失败；请核对本轮资产”。相应真实图片文件通过资产 API 均 **200**，并在候选/正式知识/修订及 HTML 阅读版里都实际显示，`naturalWidth=1`、`complete=true`。因此失败来自原成果 `assetBase` 分支对已编码地址再次编码，而非文件缺失或 PNG 无效。定位：候选版本 `MarkdownBody.vue:49`。[同页原成果失败与候选正常对照](reference-fresh-candidate.png)、[正式知识图片](reference-fresh-accepted.png)，[DOM 与直接资产读取](reference-fresh-review.json) 的 `candidate_browser` 和 `original_image_sources`。

修复应统一前后端引用键及目标路径的编码规则，并保留原成果已经支持的行号语义；以这三项实际用户路径和隐藏路径反例重做独立复核。不要改知识原文或放宽资产目录来掩盖解析问题。

## 逐条件结果

| 关闭条件 | 结果 | 亲自执行的动作与观察 | 处理 |
|---|---|---|---|
| A04/A06：真实旧采纳知识的原来源能继续打开 | pass（本例） | 全新 Chromium 读取 8011 的 `研究/阳台采光因果解释.md`，点击“来源记录”进入正确 run 的 sources.md，正文包含实际版本与读取范围；从下载的 HTML 再点击也能读到相同正文。 | 原失败中的普通隐藏研究来源已修好；[真实页面](reference-fresh-real-knowledge.png)、JSON `real_accepted_source`。 |
| A04：复杂来源和原成果图片实际可读 | **fail** | 上述三反例；有效图片接口返回 200，原成果却显示加载失败；两种知识来源 404，行号来源 400。 | 修复后再验，阻断 G1 完成声明。 |
| A06：候选、正式知识与历史修订共用引用归属 | **fail（复杂来源）** | 事项候选、正式知识、Library 修订阅读都亲自展开检查；普通映射和全部知识图片正确，复杂链接在三个消费者重复失败。 | `ResearchOutputs.document_references` 是同一 owner，接入一致本身不能证明结果正确。 |
| A06：不改原文、版本与未接受内容隔离 | pass（本轮引用修改范围） | API 正文、候选正文、浏览器“下载原文”字节内容一致；真实旧文版本仍为 `5de064f9225d0e4fba0aace4fcf5e113188f326444637e66edc7c9f471533615`；创建第二 run 的冲突候选后正式 document 全字段仍相同。 | JSON `raw_unchanged`、`real_raw_download_unchanged`、`stable_formal_after_draft`。本轮未重新声称已执行拒绝/版本冲突全套。 |
| A07：引用归属进入下一任务 | pass（传递）；**fail（行号目标）** | 独立第二事项推荐找到已采纳知识；正式 `/runs` 创建的固定输入、prompt 和调用正式 worker 材料落盘方法生成的 manifest 均携带同一映射，版本一致。但行号映射错误一并传下去。 | `downstream_recommendations`、`downstream`、`downstream_manifest`；属于受控准备验证，未调用真实模型，不能声称模型已正确使用来源。 |
| 多 run 相同相对引用不任意选择 | pass（歧义提示） | 第二 run 使用同名来源/图片并合并到候选；页面明确显示多个来源同名警告，冲突 links/images 为空；正式旧文仍保持第一 run 映射。 | JSON `ambiguous`、`ambiguity_visible`；没有把显示歧义当作已自动解决来源。 |
| 普通知识链接、代码与外链保持原有含义 | pass | 正式知识点击新增 `other.md` 真正进入 `研究/other.md` 并显示“普通知识目标”；代码块仍保留 Markdown 字面量；外链仍为 `https://example.org/`，未访问外站。 | JSON `ordinary_knowledge_target` 与各浏览器 DOM。 |
| HTML 下载与原文下载 | **fail（复杂来源）**；简单来源/知识图 pass | 原文不变；从 `file://` 打开下载阅读版，六张受控图片真正显示，来源与样式依赖原工作台的说明可见。真实旧文普通来源可点；复杂链接仍错误，行号仍 400。 | [真实阅读版](reference-fresh-real-reading.html)、[受控阅读版](reference-fresh-controlled-reading.html)。8014 回收后受控导出引用失效属明确环境边界，浏览器证据采于回收前。 |
| 隐藏文件、跨 run、跨空间与绝对路径保护 | pass（所列反例） | `.env`、`.runtime/research/.hidden.md`、父级穿越、跨 run、绝对路径：来源 400，资产 409；跨空间 run 404。允许的 `.runtime/research/allowed.md` 200。 | JSON `path_guards`、`cross_workspace`；没有放宽私密路径白名单。 |
| A01/A02/A03/A05/A08/A09 的完整重新验收 | not_proven（本轮未重跑） | 只读真实知识问答会话看到此前内容复用；没有再次发起模型、改变目标或执行恢复/取消。 | 沿用其他独立证据的范围，不用本次来源复核替代完整验收。 |

## 运行、依赖与副作用

- 依照 [独立交付复核协议](/home/yyh/project/omni-brain/.agents/skills/review-work/references/independent-delivery-check.md) 执行；源码定向读取 ResearchOutputs、Library、research_references、TaskSources、runtime prompt/worker material manifest、MarkdownBody、KnowledgePage、ResearchKnowledgeReview、readingExport 及相关测试，未编辑这些源码或批准方案。
- 8011 为主代理所有，仅 GET 和只读浏览器操作；未写入、停止 8010/8011/8013。真实会话 `conversation-976d78f0c0785613fd74cd03e2726c3b` 只读复核。测试使用新 Chromium 上下文，不继承开发会话。
- 受控数据库为独立 `test_lifeweave_ref_*`，`LIFEWEAVE_LOCAL_WORKER=0`，临时知识与执行根；通过正式 API 新建事项、候选、下一任务，通过正常网页接受知识。只有合成 run 的结束状态/正文使用测试夹具写库，明确不计真实模型成功；材料清单使用正式 worker 方法生成。
- 实际命令：`.venv/bin/python /tmp/lifeweave_reference_fresh_review.py`；归档可重放脚本为 [reference-fresh-harness.py](reference-fresh-harness.py)。自身 8014 uvicorn 线程已停止，两个临时测试库及临时文件根均已回收；最后一次为 `test_lifeweave_ref_d614c906c53f`。没有停止其他进程。
- 浏览器 `pageerror` 为零，但这不掩盖已捕获的 HTTP/图片失败。亲自运行 `npm audit --omit=dev --json`，生产依赖已知漏洞为零，见 [审计结果](reference-fresh-dependency-audit.json)；未把前端审计宣称为 Python 全依赖审计。
- [完整新鲜证据](reference-fresh-review.json) 包含真实读取、DOM、实际点击错误、图片尺寸、导出观察、固定输入、manifest、保护反例和清理结果。既有 63/28 测试成绩未当作本复核通过依据。

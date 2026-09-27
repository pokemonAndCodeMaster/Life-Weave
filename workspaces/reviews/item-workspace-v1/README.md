# 事项工作区第一版交付核查

日期：2026-09-27。方案与实现说明在 [docs/item-workspace-design.md](../../../docs/item-workspace-design.md)。本轮用户授权按理解沉淀并实现一版；这是统一工作区的首次交付，不是全部产品目标已完成。

## 首版使用反馈后的修订

“工作”页签改为“概览”；节点内实际阅读产物、前后步骤切换、链接恢复与带步骤引用讨论已接入。见[本次改动与验证](step-detail/README.md)。下面保留的是首版证据，本次修订的测试与截图独立记录，用户验收仍待反馈。

## 打开后能做什么

- [事项列表](http://127.0.0.1:8010/lifeweave/personal/items)：按范围和字段筛选，分组排序，选择列，展开父子；保存当前空间视图。
- [本次开发](http://127.0.0.1:8010/lifeweave/personal/items/item-7547b65b4f704829/overview)：读方案/实施/验证与等待用户使用反馈的阶段，点击节点查看具体内容。该图由真实阶段登记，不声称是每条工具命令的自动映射。
- [GSSM](http://127.0.0.1:8010/lifeweave/personal/items/item-de7785d0790445d8/overview)、[Qwen-Drive](http://127.0.0.1:8010/lifeweave/personal/items/item-810217743bbb4be2/overview)：读取当前成果，历史按需选择，正文保留公式/图片/定位反馈/ZIP。

新安装不会预置这些个人事项；测试用家庭安排仅存在于已隔离的临时数据库，完成核查后回收。

## 实际核查

| 范围 | 结果与证据 |
| --- | --- |
| 后端全套 | `LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest -q` 138 项通过；末次开发阶段状态修复后，`tests/test_work_view.py tests/test_research_outputs.py` 29 项通过。覆盖计划 80/81 节点边界、依赖环、同事项归属、旧成果保留、版本冲突及事务回滚。 |
| 前端 | `npm run type-check` 通过；`npm test` 25 文件、116 项通过；`npm run build` 通过。 |
| 真实保存与人工路径 | [浏览器结果](browser-roundtrip.json)：真实 HTTP/PostgreSQL；父子关系、组合筛选持久化、完成日期、空间隔离、自定义并行图、人工成果、轮询后的编辑冲突、手机布局；没有启动执行器。 |
| 真实研究与开发阅读 | [浏览器结果](browser-real-read.json)：两篇单份研究、历史元数据按需、实际图片和 ZIP；开发方案不误取代码包，固定代码交付不误取实体。 |
| 大图和验收边界 | [浏览器结果](browser-boundaries.json)：80 节点、79 条边、200 字标题、桌面/窄屏溢出及有证据但无成果目录的验收入口。 |
| 视觉核查 | 发现长需求和重复摘要后返工；最终默认不展开节点，长原文、配置、过程与证据按需查看。 |
| 审查范围 | 主代理核对模型/行为/真实页面；不同模块作者交叉审查。受会话线程上限限制，没有另开全新上下文的独立终审，不将交叉审查称为完整独立验收。 |

首次直接执行虚拟环境 `pytest` 入口因 `scripts` 不在导入路径而收集失败，改用 `python -m pytest` 后通过。浏览器脚本两处定位断言曾与实际文案/CSS 类名不符，修正定位后重新验证；这些失败不记为产品路径通过。

## 页面证据

| 页面 | 截图 |
| --- | --- |
| 默认事项列表与保存筛选 | [桌面](items-desktop.png)、[组合筛选](filtered-list.png) |
| GSSM 工作与成果 | [工作图](gssm-desktop.png)、[正文](gssm-output.png)、[手机](gssm-mobile.png) |
| Qwen-Drive | [工作](drive-desktop.png)、[正文](drive-output.png) |
| 实际开发 | [四阶段](development-desktop.png)、[固定代码交付](code-delivery.png) |
| 自定义第三种事项 | [并行与汇合](custom-plan-desktop.png)、[手机节点](custom-plan-mobile.png)、[人工正文](manual-output.png) |

截图证明被检查路径的实际呈现，不证明所有历史任务和所有屏幕均已验证。旧研究只有实际粗粒度运行记录；平台未补造论文识别、逐章分析等细步骤。图保存不调度任意能力，执行仍走现有人工、研究委托和受管开发路径。用户使用验收保持待反馈。

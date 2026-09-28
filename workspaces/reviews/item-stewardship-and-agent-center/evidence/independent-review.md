# 事项整理与 Agent 中心：独立审查

审查对象固定为 `ccd4c1b17c3ed361ea38be411d0b6387d533f619` → `ee676f0285fd7ff398b6e403bf8d4356e551b195`。需求依据是用户六项原始诉求及该提交内固定的 `approved-plan.md`、`approved-contracts.md`、`design-identity.json`。我没有读取开发者的 `review.md` 或既有“验证通过”摘要来形成判断。以下运行只访问 8012 隔离服务及数据库 `test_lifeweave_agent_center_20260928`，未访问 8010 正式数据，也未启动真实模型。审查时工作树另有他人未提交改动；源码判断以 `ee676f0` 为准。

**结论：原候选尚不能按六项要求完整交付。** 概览、真实事项分组、Agent 注册与统一触发的主要路径可用；下面四项会让组织规则被绕过、点错成果或使执行阅读与实时状态达不到批准方案。正式部署与真实开发链验证由主 Agent 另行提供实证；这两项尚未完成本独立审查，不计作代码错误。

## 需关闭的问题

### 1. 公开关系接口绕过事项整理批次

在 8012 创建测试事项 `item-945c984309a44e37`、父项 `item-9d2f3696a94c45b4` 和专题 `topic-a20f704937a04c04` 后，分别调用 `POST /api/lifeweave/personal/relations`，传 `item→topic / serves` 和 `item→item / part_of`，两次都返回 **201**。随后 `GET /item-organization/catalog` 立即显示新专题及父级，子项版本为 2；操作没有整理建议、调整理由、预览、批次撤销身份或提交方提供的事项版本。`DELETE /relations/{id}` 在同一公开路由里，也没有整理批次约束。复现涉及 `src/lifeweave/router.py:143-154`、`src/lifeweave/service.py:121-181`；新的批次校验位于 `src/lifeweave/item_organization.py:296-403`，但公开入口无需经过它。

这违反固定方案对“所有 Agent 调用同一整理服务、版本校验、追溯与撤销”的要求。应限制**组织关系**的公开直接写入：`item→topic/domain` 的 `serves`，以及 `item→item` 的 `part_of`、`contributes_to`，同时覆盖创建和删除。普通资源/成果引用及其他非组织关系可沿用普通关系入口。创建新事项时的分类继承和整理服务自身的原子应用/撤销需要可信内部路径。关闭时用 API 反例证明两种公开绕过均被拒绝，普通引用仍可创建；再证明正式整理批次可应用和撤销。

### 2. 执行详情里的成果链接打开了另一份成果

在浏览器打开外部会话 `external-ee630a9a0ff794aa5f3d8f8ef4429298`，点击第一份“在事项中阅读”，跳到 `.../outputs?output=output-807d5e59db6580578aebf0e63e064788`。事项成果目录中的对应标识实际是 `artifact:output-807d5e59db6580578aebf0e63e064788`；因为标识不匹配，页面高亮并阅读目录第一份**“工作流与阅读：实际交付及独立验证”**，不是被点击的产物。受管开发也有相同的命名差异：例如 `dev-80a91560b8d1aaa9fab35dd13504e970` 的详情给出 `delivery-80…`，事项成果目录使用 `delivery:dev-80…`。

原因是 `src/lifeweave_agents/service.py:429-431,465-470` 返回底层实体/交付 ID，`web/src/features/lifeweave/components/agents/ExecutionDetail.vue` 直接把该 ID 写入 `output` 查询参数，而 `web/src/features/lifeweave/components/workspace/WorkspaceOutputs.vue:15` 在找不到目录 ID 时静默回退到第一份。关闭时按外部交付、受管开发交付和研究结果分别点读，确认高亮的标题与点击项相同；无对应目录条目时不能给出误导性的直达链接。

### 3. 执行详情的关键内容仍被原始文本和 JSON 淹没

浏览器在 1366×900 视口打开受管 Run `gzrun-20260928-153215-45f73ee5`：`promptSnapshot` 是字符串，`ExecutionDetail.vue` 只折叠对象值，所以它从“本次输入”直接铺出整份 Markdown/JSON。输入卡片实测约 **1495 px** 高，“实际产出”卡片起点在页面 **y=1776 px**，首屏无法看到结果与轨迹。原候选的 `plan`、`review`、普通 Run 的 `result` 也只显示“成果”或原始记录入口，正文藏在 JSON 折叠内。详情应先给人可读的任务、状态、步骤、结果与错误，长快照按需展开，并让方案/审查/结果可直接阅读或进入正确的固定成果。关闭时用有长输入和有正文结果的真实记录重走页面，核对首屏和正文阅读，而不只检查 DOM 存在。

### 4. 执行目录响应慢于承诺的状态刷新节奏

隔离库有 33 条统一执行记录时，连续两次请求 `GET /agent-executions?limit=8` 分别耗时 **11.247 秒**、**11.359 秒**，尽管仅返回 8 条。`src/lifeweave_agents/service.py:342-378` 先取全量记录，再对每条调用 `_reference` 读取原 owner、关系和 Agent 配置，最后才筛选分页。`ExecutionList.vue` 仅在请求结束后再等待 3 秒刷新，所以列表状态实际约 14 秒一轮，历史增加后还会变慢。批准契约要求进行中自动以 3 秒刷新。关闭时应在数据库层缩小候选并批量读取必要状态，保留正确总数与筛选语义；在同等记录量下复测列表响应明显低于 3 秒，且新增历史记录不会线性拖慢首屏。

## 已独立核对的覆盖

- **事项阅读与现有数据组织：** 事项 `item-7547b65b4f704829` 的首卡实际显示“背景 / 要做什么 / 预期结果 / 真实进展 / 实际产出”，概览主内容只有该卡和步骤区，成果仍有独立目录。事项列表默认按专题分组，浏览器可见“LifeWeave 平台建设”“自动驾驶论文研究”等真实组，父项有展开按钮；这不是单纯增加筛选器。实现入口在 `web/src/features/lifeweave/components/workspace/WorkOverview.vue`、`pages/ItemDetailPage.vue` 和 `components/items/itemView.ts`。
- **整理服务的受控路径：** 在隔离库用建议接口把一个已有父项改成其子项，返回 400“聚合关系形成循环”；把个人事项挂到团队事项，返回 404；提交一条显式移组建议后应用与撤销均返回 200，状态依次为 `proposed → applied → undone`。这些证明批次路径的基本保护有效，不抵消第 1 项公开绕过。
- **注册、触发与快照：** 经 API 注册内置整理 Agent `review-org-b2094b18`，用同一事项触发建议，再把配置从 “Review original” 改为 “Review renamed”。旧执行详情仍显示原名称与版本，同一请求 ID 重试返回同一建议。经 Agent 中心页面选择该事项与 Agent 并点击“开始委托”，浏览器进入新 `organization` 执行详情 `orgp-de809c9a5e534cbc84d7ff1f`。这条路径不启动模型。
- **旧入口与轨迹来源：** 原开发、Run 和外部会话的路由已接统一服务；执行目录实读得到受管 Run、受管开发、外部会话和整理记录，开发组合的阶段 Run 不作为列表主行重复。受管详情可下钻子 Run；外部会话详情显示 20 条已采集/报告事件，并明确 Hook 未采集命令输入输出。未接入的外部进程及历史未采集动作不能被称为完整可回放轨迹。
- **开发流程与配置说明：** `docs/agent-workflow.md` 区分了上一轮本机 Codex/子 Agent 实施与平台受管 Run，并给出两条顺序图；没有把外部登记冒充平台调度。Agent 中心提供 Agent、Codex/OpenCode 和每次任务覆盖，OpenCode 开发受限原因在配置状态中可见。认证仍归运行环境。以上是文档和页面/接口覆盖；真实受管开发执行及正式环境结果待主 Agent 实证。

独立测试只为复现边界创建了上述两个个人测试事项、一个测试专题、一个自定义整理 Agent 和若干仅提出/应用/撤销组织建议的测试记录，均在 8012 隔离库。没有对正式数据操作，也没有运行真实 AI 模型。

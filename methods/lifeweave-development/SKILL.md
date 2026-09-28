---
name: lifeweave-development
description: 在 LifeWeave 或明确绑定的代码仓开发一项已有事项，读取当前项目知识、核对源码，交付代码、验证和可接续结果。仅用于实际软件开发；普通问答、只记录想法与论文研究不走此流程。
---

# 开发一项可接续的工作

先从已有事项读取当前目标和背景。新会话可用 `python scripts/lifeweave.py discover '目标'` 定位，再用 `continue` 回读；没有匹配时用 `work-bind` 选择明确接续、独立子事项或新目标；同名候选先核对目标，重复请求复用 requestId，普通追问不另建事项。读 `knowledge --source lifeweave-project` 找当前项目规范，并用 `read-knowledge 'lifeweave-project:路径'` 读取必要正文。资料的实际版本、Git 仓库和未提交改动要核对；匹配推荐只是初筛，不证明已采用或适用。

事项的归属通过共同服务维护：子项创建后继承父项的专题与领域；明确规则可以补充新建项分类。需要整理现有事项时，先运行 `python scripts/lifeweave_organization.py catalog`，核对目标后用 `propose --file <JSON>` 提交带理由的分类、父级或聚合建议，再用 `apply <proposalId>` 应用；`undo <proposalId>` 只恢复这批组织关系。保留原事项、讨论和成果，不因标题相似而删除或静默合并。

从网页或 CLI 委托一个独立执行时，先用 `agents`、`agent-choices <事项>` 查看可执行配置，再用 `agent-dispatch <事项> --file <JSON> --request-id <稳定ID>` 通过共用入口触发。`agent-executions --item-id <事项>` 与 `agent-execution <kind> <id>` 能读回状态、固定输入、成果与已采集轨迹；当前会话自己实施时仍走下文 external-start，不重复创建一个受管运行。API Key 留在执行器的本机认证配置，不写入 Agent 描述或任务正文。

用普通语言说清本次用户动作、期望结果、方案、代码责任和验收。多步骤开发先读取 `work-view <事项>`，用 `work-plan <事项> --file <JSON>` 保存业务计划；每步写明 `expectedOutputs`（id、title、kind、required）、`acceptance`、依赖及负责人。计划修订说明原因，保留旧版。简单局部修复可用精简步骤，不能省略真实交付。只读问题直接回答，记录想法不启动代码执行。真正实施时先读相关源码，再在适当的隔离工作区修改、运行测试和必要页面验证；失败与未完成项保留。

平台受管开发由服务绑定业务步骤并上报各阶段，Run 自身不重复创建外部会话。若正在**现有 Codex 会话**直接开发，先用 `external-start <事项> --repo <Git目录> --summary <目标> --step-id <步骤> --plan-version <版本>` 关联工作；保留已有用户授权，不因换会话重新审批。

代码形成后，用 `external-delivery <事项> <sessionId> --title <标题> --summary <实际结果> --path <文件>` 固定本次拥有的变更；重复 `--path` 指明范围，会话开始前已存在的改动需明确确认归属。计划、验证等非代码成果用 `manual-result --kind plan|validation|decision|document ...` 保存实际正文。再用 `external-report <事项> <sessionId> <phase> <摘要> --step-id <步骤> --plan-version <版本> --outcome succeeded --deliverable <预期ID>=<固定产物ID> --check <实际检查>` 关联产物。固定包不是测试证明；检查必须亲自执行并说明依据，不能把预定清单冒充通过。缺产物、版本不符或检查失败时不能声称步骤完成，失败和重试保留为独立尝试。

可附 `--knowledge <来源引用>` 记录实际采用的知识。服务观察Git身份和文件，过程与检查仍由外部会话主动报告，不冒充原生trace。命令不可用或服务不通时保留实际成果后补录，并标出未观测过程；不声称已经同步。反馈沿同一事项及成果继续，范围变化更新计划，不能让旧执行覆盖新要求。

结束前更新受影响的当前说明，保留原始证据；再次从知识入口读取新版本，确认新会话能找到。把代码版本、实际测试与页面结果、未完成范围和下一步留在同一事项。运行成功、人工接受证据与用户接受事项分别表达；没有明确授权不自动合并其他代码仓或发布能力。

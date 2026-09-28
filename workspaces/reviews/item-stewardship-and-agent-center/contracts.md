# 本轮联调契约

所有接口位于 `/api/lifeweave/{workspace}`。字段使用 camelCase；workspace 必须校验，version 冲突 409。以下是本轮实施协议，owner 可以在沟通后补充字段，不能静默另造平行入口。

## 概述（事项后端负责，UI消费）

`GET /items/{id}/work-view` 增加 `overview`：

```
{ background: string, intent: string, expectedResult: string,
  progress: { summary: string, state: string, completedSteps: number, totalSteps: number },
  outputIds: string[], sources: {background?:string,intent?:string,expectedResult?:string,progress?:string} }
```

`PUT /items/{id}/overview` body `{version, background, intent, expectedResult}`，返回最新 work-view。背景/意图/预期结果存 item.payload.overview（goal 同步意图用于现有派任务默认）；不覆盖正式 context，来源明确。已有 context/goal 可作回退；不从超长原始需求取整篇充概述。输出引用选当前每步最新有效产物/最新完整研究/正式固定交付，不将所有历史挤上首卡。

## 事项整理（事项后端负责）

- `GET /item-organization/catalog`：当前专题、领域、父子关系、待整理事项与规则、历史整理批次。
- `POST /item-organization/proposals` body `{requestId, itemIds?:string[], changes?: OrganizationChange[], groups?: OrganizationGroup[], reason?:string}`：保存可读建议，不应用。无 changes 时按当前明确规则/父项继承产生有理由的建议，不能暗示模糊匹配已证明语义。
- `GET /item-organization/proposals/{id}`：固定前后差异、冲突和状态。
- `POST /item-organization/proposals/{id}/apply` body `{requestId}`：校验项版本与原关系，原子应用，返回 proposal。
- `POST /item-organization/proposals/{id}/undo` body `{requestId}`：仅撤销该批组织差异，冲突不覆盖。
- `PUT /item-organization/rules` body `{version?:number,rules: OrganizationRule[]}`：维护适用分类与明确匹配说明。

`OrganizationChange {itemId,itemVersion,topicIds?:string[],domainIds?:string[],parentId?:string|null,reason}`。未提供字段保持原值，空数组显式清空。父级不变时省略 parentId。允许显式 Agent 提交语义理解后的判断。`OrganizationGroup {key,title,goal,itemIds:string[]}` 创建一级聚合事项并保留全部子项。应用时校验一个子项唯一父级和无环；不重复创建同名组。
`OrganizationRule {id,title,terms:string[],topicIds:string[],domainIds:string[],enabled:boolean}` 为可维护的确定性规则。自动分类只在无显式现有分类时运行；子项优先继承。规则仅分类，不用关键词自动改变已有父级。

Proposal 至少 `{id,status:'proposed'|'applied'|'undone',reason,changes:[{itemId,title,before:{topicIds,domainIds,parentId},after:{topicIds,domainIds,parentId},reason}],groups,createdAt,appliedAt?,warnings:string[]}`。需要额外 itemVersion/receipt 字段可增。完整创建路径 `LifeWeaveService.create_item` 和 `WorkBindingService` 共同挂接自动继承；所有事务内保证实体与关系一致。CLI整理子命令由事项后端提供独立 `scripts/lifeweave_organization.py`，避免与Agent后端同时改主CLI；主入口后续root联接。

## Agent目录与执行（Agent后端负责）

- `GET /agents` → `{items: AgentDefinition[], engines:[{id,label,available,reason}], ...}`。
- `POST /agents`、`PATCH /agents/{id}`（patch带version）：注册/更新可触发配置。
- `GET /items/{id}/agent-choices` → 推荐及可选配置，就绪原因与执行环境。
- `POST /items/{id}/agent-dispatch`：统一触发，body `{requestId,agentId,mode,engine?,model?,instruction?,repositoryPath?,methodId?,knowledgeRefs?,reviewMode?,executionScope?,stepId?,planVersion?,acknowledgeExcludedChanges?,organization?:{proposalId?,action:'propose'|'apply',itemIds?}}`。
- `GET /agent-executions?agentId=&itemId=&status=` → `{items: ExecutionRef[],total}`，完整受管/外部/整理归总。
- `GET /agent-executions/{kind}/{id}` → `{execution,configuration,inputs,events,outputs,children,coverage,links}`。持久轮询或事件读取由UI 3秒刷新，离页/终态停止，错误可重试。

`AgentDefinition {id,name,description,version,capability:'development'|'research'|'general'|'organization',pluginId,methodId?:string|null,engine:'codex'|'opencode'|'builtin',model?:string|null,enabled:boolean,available:boolean,reason?:string,modes:string[]}`。内置ID development/research/general/item-steward，注册新Agent只绑定已实现能力。扩展字段需在此同步。
`ExecutionRef {kind:'managed_development'|'managed_run'|'external_session'|'organization',id,itemId,agentId,agentName?,status,createdAt,updatedAt?,engine?,model?,runIds?:string[],traceCoverage:string,title?:string}`。
返回 dispatch `{kind,id,itemId,agentId,status,...}` 即ExecutionRef。历史没有agent身份时推断标明 inferred，不填成显式选择。

原开发、runs、external API 响应保持兼容，由新的共用服务调旧业务owner并完成共同登记；不得dispatch递归调用route。新Agent center新增的触发与历史事项入口共用同一AgentLaunch组件/dispatch API。原Run输出使用既有详情/成果阅读，不复制正文维护。

事项整理Agent是现有整理公共能力的可触发配置；agent后端向 `ItemOrganizationService` 调用（constructor/service API与事项owner沟通），不另写分类算法。项目已有插件host可登记 `lifeweave.item-organization`，由Agent后端负责其registry条目，事项owner不改plugin core。

## 文件所有权

- Sol事项：`src/lifeweave/item_organization*`, `item_overview*`, `service.py`, `work_binding.py`, `work_view.py`（仅概述挂接）, `tests/test_item_organization*`, `tests/test_item_overview*`, `scripts/lifeweave_organization.py`。新router导出但不改app.py；告知Agent后端接线。
- Sol Agent：`src/lifeweave_agents/*`, `src/api/app.py`, 原development/runtime/external routers必要适配，`src/lifeweave_plugins/*`必要登记，`scripts/lifeweave.py`，对应后端测试。不要修改事项owner文件。
- Sol UI：`web/src/**`，对应前端测试。需要类型契约时与两个后端owner直接沟通。
- Root：方案/流程文档、真实数据整理批次、集成与浏览器验证、交付证据、Notion镜像。代码只做必要最终集成，先通知owner。

## 实施中明确的字段与边界

Agent 配置包含 `runtime`（native/docker）和 `permission`（read-only/workspace-write）。能力决定 pluginId，注册请求不接受独立 pluginId；已有配置修改不允许换能力。派发支持 directory/runtime/permission/image/branch/machineId/capabilityCandidateId 等本次运行参数，开发组合仍使用自身阶段权限与隔离工作树。省略 knowledgeRefs 与明确传空数组含义不同：前者允许能力默认知识，后者明确不携带。

执行引用包含 `agentIds`、`itemIds`，组织建议由多个 Agent 先后操作时按参与身份/事项均可筛选。详情 `launches[]` 保存每次提出/应用操作的当时配置、输入和结果，不因后续配置改变而重写。events 保留脱敏 payload 以及 native/platform/reported 来源；coverage 说明缺口。

公开 `/relations` 不再直接改写专题/领域归属或父级；普通资源引用保留。旧网页关系编辑和新建后关联分类也走组织 proposal/apply。创建时继承、批次应用/撤销保留内部事务路径，旧领域 references 关系可读取与原样撤销。

# LifeWeave 改名独立复核

审查对象：`d70552afa275a72c3bddd4124896bbfaa16ed25a`，基线 `a119cba`。实际服务 `http://127.0.0.1:8010`。先独立读取 `git show a119cba:docs/rename-request.md`；未读取开发者 `docs/evidence/rename/` 作为通过依据。

## 初始裁决

产品改名与旧页面/历史结果读取：pass。当前文档关闭条件：fail，需澄清下列两项，不需要改业务实现。

1. `docs/naming.md` 的 API 兼容说明未写客户端需要支持 308。真实 Python 3.10 urllib GET/POST 都直接返回 HTTPError 308；需写明不跟随 308 的客户端改用 `/api/lifeweave/`，并避免承诺所有旧 SDK 无感兼容。
2. `docs/development.md` 的配置来源总述把 `.env` 与下表所有变量连在一起。实际 ConfigManager 读取 `.env` 中数据库/日志配置；知识根和节点通过 `get_env` 只读进程环境，生命周期脚本也不加载 `.env`。需说明差异，避免读者配置了 `.env` 却仍使用默认目录/节点。

## 实际动作与通过证据

- 在全新 Chromium context 从 `/` 打开，进入 `/lifeweave/personal/home`；页面、标题、图标为新名。导航与网络请求均使用新前缀，没有 pageerror。见 `fresh-home.json`、`fresh-home.png`。
- 独立打开并刷新 `/gongzuo`、个人事项 outputs 深链接、团队事项 context 深链接、旧 runs、新团队首页、新知识页面。6 项均成功，个人/团队深链接 query/hash 保留，实际内容可读。见 `probe.json`、`page-*.png`。
- 在旧个人 outputs 链接点击“阅读结果”，历史 Codex 正文显示，源码引用生成新的 `/api/lifeweave/.../source` 地址。见 `historical-result-open.json/png`。
- 个人/团队 state 与带 limit/offset 的 runs 新旧 API 内容相等。4 条历史运行的旧成果地址跟随 308 后均得到 200，正文 SHA256 与原保存 artifact version 一致；4 个旧工作目录路径仍存在。
- 历史 Codex README 源码旧 API 读取结果与该轮 worktree 原文件字节一致；没有用当前 README 代替历史文件。
- POST/PATCH/DELETE 对不存在的旧 API 路径返回 308 并保留编码查询参数；未跟随后续业务写入。这里证明重定向响应，不冒充已验证任意客户端的请求体重放。
- 实际工程为 `/home/yyh/project/lifeweave`；旧目录是指向同一工程的 symlink；已安装 Python distribution 为 `lifeweave`，前端包为 `lifeweave-web`，OpenAPI 和健康接口为 LifeWeave · 经纬。
- 7 份当前入口说明的本地 Markdown 链接全部存在。产品理由、架构、存储、执行、知识修订、完成状态与维护入口可读；明确多人权限、专门生活模块、OpenCode 成功和真实 Linear 写入尚未验证/完成。抽查快照数量与大小、版本冲突、原文指纹和启动代码符合核心说明。
- `git diff a119cba d70552a -- migrations` 为空；已有历史标题、来源和结果保留旧名，与原始要求一致。

## 证据边界

本次是只读命名与文档复核，未启动真实 AI，未向 Linear 发请求，未改日常业务数据，也未停止主 Agent 服务。未重跑与改名无关的完整业务测试。已证明代表历史记录读取与成果指纹一致；没有独立的改名前全库快照，因此不宣称已独立证明全库每行均无变化（not_proven）。

## 修订后的最终裁决

最终候选 `79dc573582319309ca81cfeffa622f6ef14e98b4`：**pass（本轮命名与文档适配范围）**。

已亲自读取 `git diff d70552a 79dc573 -- README.md docs/naming.md docs/development.md`；两项问题均已修复：README 与命名页明确 308 跟随要求，维护页说明 urllib 例外及新前缀；配置说明明确 ConfigManager 与进程环境的不同消费范围，并要求 export。新修订未改变产品执行代码，因此上述真实服务证据继续适用于最终版本。

无剩余必修问题。全库逐行改名前后不变仍为本独立检查的 not_proven 边界，不应被本裁决扩大；代表旧数据、全部当前 4 条历史运行成果、旧目录和历史源码读取已经实际通过。

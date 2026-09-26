# 研究成果归档、离线阅读与跨文章讨论

本轮解决的是：报告只留在家中电脑时无法随时找回，单独下载 Markdown 会丢本机图片，以及讨论另一篇文章时需要明确带入已有成果。用户已明确选择“每次成功生成报告后自动归档”，目标仓为 `pokemonAndCodeMaster/Life-Weave`。

## 现在从哪里找两篇论文

| 内容 | GitHub（现行归档） | Linear（历史只读） |
| --- | --- | --- |
| 所有研究版本 | [归档首页](https://github.com/pokemonAndCodeMaster/Life-Weave/tree/research-archive) | [原工作台项目](https://linear.app/yyhpokemonmaster/project/个人工作台日常使用与持续推进-a2184ae8c325)的文档资源 |
| Qwen-Drive 1.0 首轮 | [正文与同目录 ZIP](https://github.com/pokemonAndCodeMaster/Life-Weave/blob/research-archive/research/personal/item-810217743bbb4be2/gzrun-20260919-095844-49f47906/report.md) | [完整报告及 ZIP](https://linear.app/yyhpokemonmaster/document/e904a16678bf) |
| GSSM v5 首轮 | [正文与同目录 ZIP](https://github.com/pokemonAndCodeMaster/Life-Weave/blob/research-archive/research/personal/item-de7785d0790445d8/gzrun-20260919-130600-2cabbf3e/report.md) | [完整报告及 ZIP](https://linear.app/yyhpokemonmaster/document/3815a1caa1d2) |
| 产品代码与说明 | [main 分支](https://github.com/pokemonAndCodeMaster/Life-Weave) | 项目 Overview 提供入口 |

本机事项仍是工作事实的维护位置；归档保存成功运行的版本快照，包含事项身份、标题、正文版本、图片和引用文件，不等于整个事项数据库的镜像，也不替代“接受知识”。两篇报告没有因归档而成为已接受的正式知识。

远端已上传的版本在本机关机后仍可访问；新的研究、讨论和自动上传需要工作台服务运行。仓库或历史 Linear 工作区若限制访问，另一台设备仍须登录有权访问的账号。此前验证过 GitHub 重新 clone 后的完整文件，以及历史 Linear 正文和附件回读；未完成已登录 Linear 页面实际显示验收。旧 Linear 公式显示为 LaTeX 代码原文；ZIP 内原 Markdown 与工作台的公式版本保持一致。Notion 镜像尚需单独配置后台集成令牌及页面授权，不能因本机 Codex 的 OAuth 已授权就视为报告已镜像。

## 自动和手动怎样配合

进入“设置与连接 → 研究成果自动归档”，保存仓地址并勾选自动归档。当前个人空间的 GitHub 归档已配置并开启，团队空间保持单独设置。需要 Notion 镜像时在同页另行配置根页面与后台集成令牌文件。后台约20秒检查一次成功成果；归档耗时取决于文件数量与网络，报告显示成功不表示远端已经完成上传。

成果下方显示本机完整包、GitHub、Notion 各自的状态和远端链接，旧 Linear 状态仅标历史。一处成功、另一处失败时分别显示；失败约5分钟后重试，也可点“立即归档 / 重试”。GitHub 已确认版本不会重复上传；启用 Notion 时，已确认镜像约每5分钟重新回读一次，发现远端被修改或删失就标失败并保留原链接。配置关闭会暂停后台处理，手动按钮仍可使用。首次开启前的旧成果需逐项点击归档；两篇已有 GitHub 与历史 Linear 归档，尚未声称 Notion 补归档完成。开启后遗漏的成功运行会在服务恢复时重新扫描。

每次成功运行产生独立版本文档和 Git 路径。正文或引用文件若在同一运行身份下被修改，归档拒绝覆盖原版本；应通过新运行修订。Git 分支发生不能快进的冲突会显示失败；Notion 已有镜像页若被人在远端编辑，相同源版本再次核对或后续写入都会停在冲突状态。已经确认的状态是最近一次回读证据，不是两次核对之间的持续监控，也不会把用户在远端的修改自动反写进本机。

Git 使用本机 SSH 认证，归档在私有独立 checkout 中提交 `research-archive` 分支。自动归档不提交开发者当前工作区里的代码、账号文件或数据库。Notion 镜像从已确认的 GitHub 报告正文创建子页，将图片链接改为 GitHub Raw 地址并回读 Markdown、来源版本和完整性标记；当前还没有对 Notion 图片实际显示逐张验收，离线图片以 ZIP 为准。旧 Linear 已停止新增发布和报告重试，既有归档保留。

## 下载后怎样保留图片

在任一运行成果处点击“下载完整包（含图片）”。解压后保持文件结构，用支持 Markdown 的阅读器打开 `report.md`：

- `report.md`：相对链接已改写，图片与引用指向包内文件。
- `original.md`：没有改动的成果原文。
- `files/`：正文引用的本轮图片、文本及嵌套 Markdown 材料。
- `manifest.json`：本轮事项、运行、正文版本、各文件哈希和未收录清单。
- `README.md`：阅读说明。远端归档目录还包含同内容的 `research.zip`。

“仅下载 Markdown”仍提供原正文，适合只要文本时使用。外部网页、外部远程图片不自动抓取，仍可能需要网络。当前支持本轮目录内的 PNG/JPEG/GIF/WebP 和有限文本格式；嵌入的本地图片取不到时下载失败，普通缺失引用进入清单并在归档状态显示提醒。每包最多128个引用文件、总引用内容64 MB，单图片受既有10 MB接口限制、单文本1 MB，越界、隐藏文件和越界软链接拒绝。

实际两篇包没有缺失警告。Qwen 收录11个引用文件，GSSM 收录28个；断网打开解压正文时，Qwen 的两张内嵌图与 GSSM 的一张内嵌图均实际解码显示。被文字链接引用的其他图片也在包内。

## 怎样讨论当前文章并引用另一篇

在 GSSM 成果页点“就地讨论”，进入关联该事项、范围为“仅讨论”的 AI 对话。当前成果自动作为材料，选段时还会保留原运行与定位。展开“附带其他研究成果”，选择 Qwen-Drive，然后直接问两者的关系。最多另外选5篇；按事项去重，不跨个人/团队空间读材料。

已有知识仍通过现有文本匹配推荐读取，最多10篇、总40000字符；并非自动搜索所有未登记资料。报告与正式知识分开显示，回复下方“本次参考来源”记录实际版本。当前报告最多60000字符、其他每篇最多20000字符，总预算120000字符；长报告均保留有标记的摘录，不能把摘录当作全文已读。已成功运行的两篇现有论文小于上限，实际讨论用了完整正文。

所选文章和模式保存在当前浏览器的该对话草稿中，发送后切换到新对话地址及刷新仍保留；服务器每轮也保存实际引用。换浏览器能读历史来源，但下一轮需重新选择附带文章。“就地讨论”的明确入口优先于旧草稿的委托模式；只有用户主动改变范围才会发起新委托。旧的“记录讨论笔记”仍是手工记录入口，和 AI 对话有明确区分。

[本轮真实跨文章讨论](http://127.0.0.1:8010/lifeweave/personal/conversation/conversation-6214d5172fb425f7ce4e34642a954be9?itemId=item-de7785d0790445d8)比较两篇的学习目标、训练信号与风险含义，并区分报告事实和组合建议。该轮只保存讨论，没有新执行、知识接受或目标采纳。

## 后续维护责任

源码入口是 `research_bundle.py`、`research_archive.py`、`Conversations.prepare` 与对应 Vue 组件；运行配置见[维护文档](development.md)。本次新事实的长期维护位置是本仓 [架构](architecture.md)、本页与[当前状态](status.md)。Omni-Brain 的知识体系和本产品并非同一个来源身份，本轮没有把这里的实现直接写成其正式知识；未来如需登记，建议新增 `knowledge/lifeweave/research-archive.md` 来源页并经原库治理接受。

自动成果归档没有完成已接受知识的单独自动发布、全库备份或完整个人日常 Alpha。Notion 后台令牌未配置前，新增报告只会继续归档至 GitHub；既有两篇的 Notion 镜像仍待真实上传和回读。[验证记录](evidence/research-archive/README.md)区分了历史远端、本机网页和受控回归的覆盖范围。

# LifeWeave 改名与文档验证

日期：2026-09-19。原始要求见 [修改前任务记录](../../rename-request.md)，基线 `a119cba`；本目录只记录此次适配，不把首轮真实 AI 调用当成本轮执行。

- 项目目录为 `/home/yyh/project/lifeweave`；旧目录是同一仓库的兼容符号链接。
- Python 分发包已改名并重新安装为 `lifeweave 0.1.0`，前端包为 `lifeweave-web`。
- `LIFEWEAVE_TEST_DB=1 .venv/bin/python -m pytest -q`：47 项通过。新增旧 API 方法/正文/参数及变量别名兼容检查。
- `npm --prefix web run type-check`、`npm --prefix web test`、`npm --prefix web run build`：通过，前端 13 项测试。
- [实际浏览器记录](browser.json)：新首页、旧事项深链接参数/片段、历史 AI 源码原文、中文知识链接、团队设置与页面异常检查。
- [数据保留记录](data-preservation.json)：22 张业务表的整行内容指纹一致，2 篇知识正文指纹一致；执行节点表发生预期心跳更新。没有改写历史事项、原文、结果或迁移。
- [桌面](desktop.png)、[390px 首页](mobile.png)、[窄屏导航](mobile-navigation.png)：实际页面截图。
- [独立复核](independent-review.md)：实际新旧页面、历史结果和源码读取；发现并修正 `.env` 范围与 308 客户端说明。报告中的原始探针和截图位于本机 `.runtime/rename-independent/`，不把其中的私人工作正文复制到文档仓。

当前文档中的相对文件链接经过检查；产品设计与源码职责定向核对。开发说明明确保留内部旧标识，首次交付文档保留历史名称并增加当前入口。

实施者取得了改名前后的数据库内容指纹，独立复核者只检查代表历史记录和已保存的成果指纹，没有独立取得改名前全库快照；这两类证据范围分别保留。

修订后的两处说明另由一个全新上下文独立复核 `79dc573`：对照配置加载、知识根、节点和数据库脚本；实际 GET 旧配置接口返回 308，Python 3.10 urllib 不自动跟随，新地址返回 200。结论为两处文档修订通过，未扩展为完整业务验证；过程仅使用本机 GET，没有修改日常数据。

迁移前备份位于本机 `.runtime/backups/gongzuo-20260919-100353.dump` 与对应知识包。应用已从新目录重新启动，服务地址仍为 `http://127.0.0.1:8010`。此次没有执行真实 AI 调用或 Linear 外部写入。

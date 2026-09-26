已按已审方案完成，改动仅涉及三份文档，共新增 66 行、删除 2 行：

- [development.md](/home/yyh/project/lifeweave/.runtime/executions/personal/gzrun-20260926-172650-784859ce/repo/docs/development.md:162)：新增六步操作说明，覆盖默认知识、固定版本、插件调用、运行检查及 Notion 镜像。
- `docs/README.md`：新增章节直达链接。
- `docs/complete-guide.md`：同步生成完整汇编。

审阅建议均已纳入：`read/bind` 需结合成功状态和输出引用判断；镜像需比较三个版本；单篇发布要求正文与本地 HEAD 一致且 GitHub main 指向该 HEAD。本轮无额外纠偏反馈。

实际验证通过：

- `python scripts/build_complete_guide.py`
- `python scripts/build_complete_guide.py --check`：10 份当前来源全文一致，本地链接有效。
- `git diff --check`

已核对页面源码、服务实现和 `docs/plugin-system.md`，未进行浏览器交互验收。本机 API 实际返回个人空间 Notion `enabled=false`、`configured=false`，此篇没有镜像记录；未执行配置或发布。

改动保留在隔离工作树，未合回原仓。知识入口回读仍是原版本，合入后需重新核对新指纹；技术完成不代表事项已被业务接受。
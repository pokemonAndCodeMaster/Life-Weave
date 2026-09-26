已完成前轮待实施部分：仅在隔离工作树的 [README.md](/home/yyh/project/lifeweave/.runtime/executions/personal/gzrun-20260926-155058-e016397c/repo/README.md:4) 末尾新增：

```diff
+Smoke: snapshot-guard
```

验证结果：

- `grep -nFx 'Smoke: snapshot-guard' README.md` 输出 `4:Smoke: snapshot-guard`，退出码 0。
- `git diff --check` 通过，退出码 0。
- 原文及 LF 换行保留，已跟踪文件仅 README 有变化。

本轮无纠偏反馈；按明确任务使用 `snapshot-guard`，保留其与已接受目标 `codex-guard` 的差异，未改写上下文。

知识变化仅为 README 更新；仓库缺少知识登记入口，未完成额外知识登记。代码实施与指定验证无剩余项，无需页面验证。未推送、未合并，技术完成不代表事项已获业务接受。

已完成追加与验证，补齐前轮尚未实施的部分。仅修改 README.md，保留原有三行及 LF 换行：

```diff
 This project has a Python helper.
+Smoke: codex-guard
```

验证通过：

- `grep -nF 'Smoke: codex-guard' README.md` 输出 `4:Smoke: codex-guard`，退出码 0。
- `git diff --check` 通过；Git 差异仅包含该新增行。
- 原有未跟踪目录 `.agents/`、`.lifeweave/` 未改动。

本轮无纠偏反馈，目标与范围未变。知识更新仅为 README 冒烟标记，未进行额外知识登记。无未完成的实施项；未合回原仓，技术验证通过不代表事项已获业务接受。
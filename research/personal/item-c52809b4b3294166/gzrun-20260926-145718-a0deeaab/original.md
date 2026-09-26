## 交付结果

### 文件差异

**wordcount.py** — 新增 `count_nonempty_lines` 函数：
```python
def count_nonempty_lines(text: str) -> int:
    count = 0
    for line in text.splitlines():
        if line.strip():
            count += 1
    return count
```

**test_wordcount.py** — 新建，7 个 unittest 用例，全部通过。

**README.md** — 追加测试运行命令：`python -m unittest test_wordcount -v`

### 测试结果

```
Ran 7 tests in 0.000s
OK
```

覆盖：空字符串、纯空白、单行内容、中英文混合、空行夹杂、空白行夹杂、`\r\n` 换行。

### 未覆盖范围

无。任务要求的三项改动（实现、测试、README）均已完成且验证通过。

### Git 状态

改动未提交，仅在工作区修改。
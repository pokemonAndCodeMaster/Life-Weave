## 计划：改进 wordcount.py

### 现状分析

仓库包含：

- `wordcount.py`：仅有 `count_words(text: str) -> int`，用 `len(text.split())` 实现
- `README.md`：基础项目描述，无测试说明
- 无任何测试文件
- 无 Python 配置文件（无 pyproject.toml、requirements.txt 等）
- 单一 baseline 提交

### 需要修改/新增的文件

| 文件 | 操作 |
| --- | --- |
| `wordcount.py` | 追加 `count_nonempty_lines` 函数 |
| `test_wordcount.py` | 新建 unittest 测试文件 |
| `README.md` | 更新，添加运行测试命令 |

### 实现方案

#### 1. `wordcount.py` — 新增 `count_nonempty_lines`

```python
def count_nonempty_lines(text: str) -> int:
    """统计去掉首尾空白后仍有内容的行数。"""
    count = 0
    for line in text.splitlines():
        if line.strip():
            count += 1
    return count
```

设计要点：

- 使用 `str.splitlines()` 处理 `\n`、`\r\n`、`\r` 等各种换行符
- 每行用 `.strip()` 去除首尾空白后检查是否非空
- 空字符串 `""` → `splitlines()` 返回空列表 → 返回 `0` ✓
- 全空白行 → `strip()` 结果为空字符串 → 不计数 ✓
- `count_words` 保持不变，确保向后兼容

#### 2. `test_wordcount.py` — unittest 测试

测试用例覆盖：

| 用例 | 输入 | 期望输出 |
| --- | --- | --- |
| 空字符串 | `""` | `0` |
| 只有空白字符的字符串 | `"   \n\t\n  "` | `0` |
| 单行有内容 | `"hello"` | `1` |
| 混合中英文 | `"你好 world\n第二行\nthird line"` | `3` |
| 空行夹在内容行之间 | `"a\n\nb"` | `2` |
| 只有空白的行夹在内容行之间 | `"a\n  \nb"` | `2` |
| 不同换行符 `\r\n` | `"line1\r\nline2"` | `2` |

```python
import unittest
from wordcount import count_words, count_nonempty_lines

class TestCountNonemptyLines(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(count_nonempty_lines(""), 0)

    def test_only_whitespace(self):
        self.assertEqual(count_nonempty_lines("   \n\t\n  "), 0)

    def test_single_content_line(self):
        self.assertEqual(count_nonempty_lines("hello"), 1)

    def test_mixed_chinese_english(self):
        text = "你好 world\n第二行\nthird line"
        self.assertEqual(count_nonempty_lines(text), 3)

    def test_blank_lines_between_content(self):
        self.assertEqual(count_nonempty_lines("a\n\nb"), 2)

    def test_whitespace_lines_between_content(self):
        self.assertEqual(count_nonempty_lines("a\n  \nb"), 2)

    def test_windows_line_endings(self):
        self.assertEqual(count_nonempty_lines("line1\r\nline2"), 2)
```

#### 3. `README.md` — 更新

追加测试运行说明：

```
## 测试

```bash
python -m unittest test_wordcount -v
```

```

### 受影响模块和接口

- **无外部依赖**：仅使用 Python 标准库 (`unittest`)
- **无公共 API 变更**：新增函数为独立功能，`count_words` 不受影响
- **无配置文件变更**

### 实现顺序

1. 编辑 `wordcount.py`，在末尾追加 `count_nonempty_lines` 函数
2. 创建 `test_wordcount.py`，包含上述 7 个测试用例
3. 编辑 `README.md`，追加测试运行命令
4. 运行 `python -m unittest test_wordcount -v` 验证全部通过

### 风险与边界

| 风险 | 评估 |
|------|------|
| `splitlines()` 对空字符串的行为 | 返回 `[]`，安全 |
| Unicode 中文字符处理 | Python 3 str 原生支持，无问题 |
| 与现有 `count_words` 冲突 | 无，独立函数 |
| 换行符兼容性 | `splitlines()` 自动处理 `\n`、`\r\n`、`\r` |

### 自检

- [ ] 新函数对空字符串返回 `0`
- [ ] 新函数对纯空白行返回 `0`
- [ ] 新函数正确计数中英文混合行
- [ ] 测试覆盖至少 7 个用例
- [ ] 测试使用标准库 unittest
- [ ] README 包含运行测试命令
- [ ] 未修改 `count_words` 现有行为
- [ ] 未引入外部依赖

### 尚未解决的问题

无。任务范围明确，实现方案无歧义。

---

**计划已完成。** 是否可以开始实施？
```

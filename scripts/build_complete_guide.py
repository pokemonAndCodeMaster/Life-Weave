"""Assemble every project Markdown document without summarizing its content."""
from pathlib import Path
import argparse
import hashlib
import os
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/complete-guide.md'
CURRENT = ['README.md', 'docs/README.md', 'docs/naming.md', 'docs/product.md',
           'docs/architecture.md', 'docs/status.md', 'docs/development.md',
           'LifeWeave_产品定义与首版迭代计划_v1.0_2026-09-19.md']
HISTORY = ['docs/brief.md', 'docs/rename-request.md', 'docs/delivery.md']
PLANS = ['workspaces/reviews/lifeweave-next-stage/review.md']
LINK = re.compile(r'(!?\[[^\]\n]*\]\()([^\s)]+)(\))')
HEADING = re.compile(r'^(#{1,6}) (.+)$')


def headings(body):
    fence = None
    for number, line in enumerate(body.splitlines()):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            match = HEADING.match(line)
            if match:
                yield number, match[1], match[2]


def build():
    available = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'docs').rglob('*.md') if p != OUTPUT}
    ordered = CURRENT + PLANS + HISTORY + sorted(available - set(CURRENT + HISTORY))
    sources = {path: (ROOT / path).read_text() for path in ordered}
    sections = {path: f'doc-{index + 1:02}' for index, path in enumerate(ordered)}
    anchors = {}
    titles = {}
    historical_links = []
    for path, body in sources.items():
        seen = {}
        for number, level, title in headings(body):
            slug = re.sub(r'[^\w\-\s]', '', title.lower()).replace(' ', '-')
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            if count:
                slug += f'-{count}'
            anchors[(path, slug)] = f'{sections[path]}-line-{number + 1}'
            titles.setdefault(path, title)

    def link_from(source, match):
        target = match[2]
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith('/'):
            return match[0]
        resolved = ((ROOT / source).parent / unquote(parsed.path)).resolve() if parsed.path else ROOT / source
        try:
            relative = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return match[0]
        if resolved == OUTPUT:
            dest = '#complete-guide'
        elif relative in sections and not parsed.query:
            dest = '#' + (anchors[(relative, unquote(parsed.fragment))] if parsed.fragment else sections[relative])
        else:
            if not resolved.exists():
                if source.startswith('docs/evidence/'):
                    historical_links.append((source,target))
                    return match[0]
                raise ValueError(f'{source}: missing link {target}')
            dest = os.path.relpath(resolved, OUTPUT.parent)
            if parsed.query:
                dest += '?' + parsed.query
            if parsed.fragment:
                dest += '#' + parsed.fragment
        return match[1] + dest + match[3]

    result = [
        '<a id="complete-guide"></a>', '# LifeWeave · 经纬：完整项目说明', '',
        '这是一份可连续阅读的完整汇编：前半部分是当前产品、架构、状态和使用维护说明，后半部分是历史授权、交付与验证文字附录。', '',
        f'范围为项目根 README、产品定义 v1.0 原文、docs/ 下全部 Markdown（不含本汇编自身），以及当前建设方案，共 {len(sources)} 份来源。'
        '所有来源正文、表格、代码块、Mermaid 图及历史说明完整保留；重复内容也保留，不做摘要或删节。只调整标题层级、链接位置和文内导航。', '',
        '源码、截图、JSON 运行记录和 API 文档保留可访问的引用，不把它们误作本次需要合并的说明正文。'
        '历史附录中的旧名称、当时状态和旧测试数量按原文保留；当前能力请以“当前完成情况”为准。', '',
        '维护时先更新分篇，再执行 `python scripts/build_complete_guide.py`；'
        '`python scripts/build_complete_guide.py --check` 会逐篇检查整合版是否与当前来源一致。', '',
        '## 阅读目录与来源覆盖', '', '| 部分 | 章节 | 来源 | 原文 SHA-256 |', '| --- | --- | --- | --- |'
    ]
    for path, body in sources.items():
        digest = hashlib.sha256(body.encode()).hexdigest()
        kind = '当前说明' if path in CURRENT else ('建设方案（含未实现范围）' if path in PLANS else '历史与验证附录')
        result.append(f'| {kind} | [{titles.get(path, Path(path).stem)}](#{sections[path]}) | `{path}` | `{digest}` |')
    for path, body in sources.items():
        result.extend(['', '---', '', f'<a id="{sections[path]}"></a>',
                       f'<!-- source-begin: {path} -->'])
        by_line = {number: (level, title) for number, level, title in headings(body)}
        fence = None
        for number, line in enumerate(body.splitlines()):
            marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
            if marker:
                token = marker[1]
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
                result.append(line)
                continue
            if fence is not None:
                result.append(line)
                continue
            if number in by_line:
                level, title = by_line[number]
                result.extend([f'<a id="{sections[path]}-line-{number + 1}"></a>', ''])
                line = '#' * min(len(level) + 1, 6) + ' ' + title
            result.append(LINK.sub(lambda match: link_from(path, match), line))
        result.append(f'<!-- source-end: {path} -->')
    if historical_links:
        result.extend(['', '## 历史产物引用的验证边界', '',
            '以下引用来自原样保存的运行或审查产物，其相对路径属于当时的执行目录。正文完整保留，但不冒称这些路径在本文档目录中可打开；实际工作台通过运行来源接口解析。当前说明文档的本地链接仍须存在。', ''])
        result.extend(f'- `{source}`：`{target}`' for source,target in sorted(set(historical_links)))
    return '\n'.join(result) + '\n', len(sources)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成或检查 LifeWeave 完整项目说明')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content, count = build()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            raise SystemExit('整合版与来源不一致，请运行 python scripts/build_complete_guide.py')
        print(f'完整性检查通过：{count} 份来源全文一致；当前文档本地链接有效，历史产物相对引用另列边界。')
    else:
        OUTPUT.write_text(content)
        print(f'已生成 {OUTPUT.relative_to(ROOT)}，完整收录 {count} 份来源。')

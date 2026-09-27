"""Read only media actually referenced by an allowed current document."""
from __future__ import annotations

import os
import posixpath
import re
import stat
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

import mistune

MAX_ASSET_BYTES = 10_000_000
EXCLUDED = {'raw', 'node_modules', '__pycache__'}


def image_references(content: str) -> set[str]:
    found: set[str] = set()

    class Images(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag.lower() == 'img':
                for name, value in attrs:
                    if name.lower() == 'src' and value:
                        found.add(unquote(value))

    def walk(tokens):
        for token in tokens:
            if token['type'] == 'image':
                found.add(unquote(token.get('attrs', {}).get('url', '')))
            elif token['type'] in {'inline_html', 'block_html'}:
                Images().feed(token.get('raw', ''))
            walk(token.get('children', []))

    walk(mistune.create_markdown(renderer='ast', plugins=['table', 'math'])(content))
    return found


def asset_relative(document_path: str, reference: str) -> str:
    parsed = urlsplit(reference)
    if (not reference or parsed.scheme or parsed.netloc or not parsed.path or
            parsed.path.startswith('/') or '\\' in parsed.path or '\x00' in parsed.path):
        raise ValueError('图片必须是所选文档引用的相对文件')
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(document_path), parsed.path))
    parts = Path(relative).parts
    if any(part == '..' or part.startswith('.') or part in EXCLUDED for part in parts):
        raise ValueError('图片路径超出所选来源或位于隐藏、原始材料目录')
    return relative


def read_media(root: Path, relative: str) -> tuple[bytes, str]:
    """Open every component with NOFOLLOW, so replaced symlinks cannot escape."""
    root = root.resolve()
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p == '..' or p.startswith('.') or p in EXCLUDED for p in parts):
        raise ValueError('图片路径不允许读取')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(parts):
            try:
                next_fd = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_DIRECTORY if index < len(parts)-1 else 0), dir_fd=fd)
            except FileNotFoundError as exc:
                raise KeyError('图片文件不存在') from exc
            except OSError as exc:
                raise ValueError('图片路径包含符号链接或不可读取目录') from exc
            os.close(fd)
            fd = next_fd
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('图片必须是普通文件')
        if os.fstat(fd).st_size > MAX_ASSET_BYTES:
            raise ValueError('图片超过 10 MB')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            data = handle.read(MAX_ASSET_BYTES + 1)
        if len(data) > MAX_ASSET_BYTES:
            raise ValueError('图片超过 10 MB')
    finally:
        os.close(fd)
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return data, 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return data, 'image/jpeg'
    if data[:6] in {b'GIF87a', b'GIF89a'}:
        return data, 'image/gif'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return data, 'image/webp'
    if Path(relative).suffix.lower() == '.svg':
        # SVG is served as an image, never injected as document HTML. Reject
        # active/remote content even if the URL is later opened in a new tab.
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('SVG 含有不支持的外部声明')
        try:
            tree = ElementTree.fromstring(data)
        except ElementTree.ParseError as exc:
            raise ValueError('SVG 图片格式不可读取') from exc
        allowed = {'svg', 'g', 'path', 'rect', 'line', 'polyline', 'polygon', 'circle', 'ellipse', 'text', 'tspan', 'title', 'desc', 'defs', 'marker', 'clipPath', 'mask', 'linearGradient', 'radialGradient', 'stop', 'use'}
        if tree.tag.split('}')[-1] != 'svg':
            raise ValueError('文件不是 SVG 图片')
        for node in tree.iter():
            if node.tag.split('}')[-1] not in allowed:
                raise ValueError('SVG 包含脚本、嵌入内容或不支持的样式')
            for name, value in node.attrib.items():
                name = name.split('}')[-1].lower()
                if (name.startswith('on') or (name == 'href' and not value.startswith('#')) or
                        re.search(r'(?:javascript:|https?:|data:|@import|expression\s*\(|url\s*\(\s*[\'\"]?(?!#))', value, re.I)):
                    raise ValueError('SVG 包含外部引用或不安全内容')
        return data, 'image/svg+xml'
    raise ValueError('文件不是支持的 PNG、JPEG、GIF、WebP 或安全 SVG 图片')

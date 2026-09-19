"""Portable research snapshots: only cited, owned files; never a run home/archive dump."""
import hashlib
import io
import json
import mimetypes
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import mistune
from mistune.renderers.markdown import MarkdownRenderer

MAX_FILES = 128
MAX_BYTES = 64_000_000
TEXT_TYPES = {'.md', '.txt', '.py', '.ts', '.js', '.vue', '.css', '.html', '.json', '.yaml', '.yml', '.toml', '.sql', '.sh'}


class PortableMarkdown(MarkdownRenderer):
    def inline_math(self, token, state):
        return '$' + token['raw'] + '$'

    def block_math(self, token, state):
        return '$$\n' + token['raw'] + '\n$$\n\n'


def rewrite_markdown(content, resolve, *, math_as_code=False):
    parser = mistune.create_markdown(renderer='ast', plugins=['table', 'math', 'strikethrough'])
    tokens, state = parser.parse(content)

    def walk(rows):
        for token in rows:
            if math_as_code and token['type']=='inline_math':
                token['type']='codespan'
            elif math_as_code and token['type']=='block_math':
                token.update(type='block_code',style='fenced',marker='```',attrs={'info':'latex'})
            if token['type'] in {'link', 'image'}:
                token['attrs']['url'] = resolve(token['attrs']['url'], token['type'] == 'image')
                token.pop('label', None)
                token.pop('ref', None)
            walk(token.get('children', []))
    walk(tokens)
    state.env['ref_links'] = {}
    renderer = PortableMarkdown()
    renderer.register('strikethrough', lambda r, t, s: '~~'+r.render_children(t,s)+'~~')
    return renderer(tokens, state)


def source_path(root, workspace, run_id, path):
    run_root = (Path(root)/'.runtime/executions').resolve()/workspace/run_id
    folder = run_root/'repo'
    relative = Path(path)
    target = (folder/relative).resolve()
    def allowed(parts):
        visible = parts[2:] if parts[:2] == ('.runtime', 'research') else parts
        return not any(p.startswith('.') or p in {'..', 'node_modules', '__pycache__'} for p in visible)
    if (relative.is_absolute() or not allowed(relative.parts) or
            not folder.resolve().is_relative_to(run_root) or not target.is_relative_to(folder.resolve()) or
            not allowed(target.relative_to(folder.resolve()).parts)):
        raise ValueError('只提供本次独立工作目录中的普通源文件')
    return target


def build_bundle(outputs, workspace, run_id):
    run = outputs.runtime.get_run_snapshot(workspace, run_id)
    if run['state'] != 'succeeded':
        raise ValueError('完整归档需要已成功结束的运行')
    content = outputs._content(run)
    if not content.strip():
        raise ValueError('本轮没有成果正文')
    files = {}
    seen = {}
    records = []
    warnings = []
    total = 0

    def resolve(href, image=False, parent=''):
        nonlocal total
        decoded = unquote(href)
        parsed = urlsplit(decoded)
        if parsed.scheme or parsed.netloc or not parsed.path or decoded.startswith('#'):
            return href  # External references remain external; no arbitrary network fetches.
        path = re.sub(r':\d+(?:-\d+)?$', '', parsed.path)
        if path.startswith('/'):
            warnings.append('未打包本机绝对或网页路径：'+path)
            return href
        try:
            target = source_path(outputs.root, workspace, run_id, path)
            if not target.is_file() and parent:
                path = str(Path(parent).parent/path)
                target = source_path(outputs.root, workspace, run_id, path)
            if not target.is_file():
                raise FileNotFoundError(path)
            key = str(target)
            if key in seen:
                return seen[key] + ('#'+parsed.fragment if parsed.fragment else '')
            if len(seen) >= MAX_FILES:
                raise ValueError('引用文件超过128个，请拆分研究成果')
            if target.suffix.lower() in {'.png','.jpg','.jpeg','.gif','.webp'}:
                data, mime = outputs.asset(workspace, run_id, path)
            elif not image and target.suffix.lower() in TEXT_TYPES:
                if target.stat().st_size > 1_000_000:
                    raise ValueError('引用文本超过1 MB')
                data = target.read_bytes()
                data.decode('utf-8')
                mime = 'text/plain'
            else:
                raise ValueError('引用格式不支持打包：'+path)
            total += len(data)
            if total > MAX_BYTES:
                raise ValueError('引用材料超过64 MB')
            safe_name = re.sub(r'[^\w.\-]', '_', target.name)
            name = 'files/'+hashlib.sha256(path.encode()).hexdigest()[:16]+'-'+safe_name
            seen[key] = name
            original_hash = hashlib.sha256(data).hexdigest()
            if target.suffix.lower() == '.md':
                # All derived Markdown lives one level down; restore that base after recursion.
                data = rewrite_markdown(data.decode(), lambda u, i: ('../'+v if (v:=resolve(u,i,path)).startswith('files/') else v)).encode()
            files[name] = data
            records.append({'path':path, 'file':name, 'mime':mime, 'sourceSha256':original_hash,
                            'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data)})
            return name + ('#'+parsed.fragment if parsed.fragment else '')
        except (OSError, UnicodeError, ValueError) as exc:
            if image or '超过' in str(exc):
                raise ValueError('完整包无法取得引用材料：'+path) from exc
            warnings.append('未打包引用 '+path+'：'+str(exc))
            return href

    report = rewrite_markdown(content, resolve)
    item = outputs.work.get_item(workspace, run['item_id'])
    manifest = {'workspace':workspace, 'itemId':run['item_id'], 'runId':run_id, 'title':item['title'],
                'version':hashlib.sha256(content.encode()).hexdigest(), 'files':records,
                'warnings':list(dict.fromkeys(warnings)), 'boundary':'研究成果归档，不代表已接受的正式知识。外部网址仍需联网。'}
    files['report.md'] = report.encode()
    files['original.md'] = content.encode()
    files['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    files['README.md'] = ('# '+item['title']+'\n\n打开 report.md 阅读，图片与本地引用在 files/，请保留目录结构。\n'
                         'original.md 是未改写的原始正文；manifest.json 记录来源、版本和缺失材料。\n'
                         '外部网页不在压缩包内。归档不代表用户已经接受研究结论。\n').encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return files, manifest, buffer.getvalue()

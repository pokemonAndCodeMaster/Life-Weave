"""Explicit, immutable inputs for a task; no global instruction inheritance."""
from pathlib import Path
import hashlib
import json
import os
import yaml


class TaskSources:
    def __init__(self, root, library):
        self.root = Path(root)
        self.library = library

    def config_file(self, workspace):
        if workspace not in ('personal', 'team'):
            raise ValueError('工作区不存在')
        return self.root / '.runtime' / f'methods-{workspace}.json'

    def roots(self, workspace):
        file = self.config_file(workspace)
        return json.loads(file.read_text()) if file.exists() else []

    def add_root(self, workspace, root):
        path = Path(root).expanduser().resolve()
        if not path.is_dir():
            raise ValueError('Skills 目录不存在')
        roots = list(dict.fromkeys([*self.roots(workspace), str(path)]))
        file = self.config_file(workspace)
        file.parent.mkdir(parents=True, exist_ok=True)
        temporary = file.with_suffix('.tmp')
        temporary.write_text(json.dumps(roots, ensure_ascii=False))
        temporary.chmod(0o600)
        os.replace(temporary, file)
        return self.catalog(workspace)

    def catalog(self, workspace):
        rows = []
        for root in self.roots(workspace):
            for file in sorted(Path(root).glob('*/SKILL.md')):
                try:
                    content = file.read_text()
                    metadata = yaml.safe_load(content.split('---', 2)[1]) if content.startswith('---') else {}
                    metadata = metadata if isinstance(metadata, dict) else {}
                except (OSError, UnicodeError, yaml.YAMLError, IndexError):
                    continue
                identity = 'method-' + hashlib.sha256(str(file.resolve()).encode()).hexdigest()[:20]
                if not any(row['id'] == identity for row in rows):
                    rows.append({'id': identity, 'title': str(metadata.get('name') or file.parent.name), 'description': str(metadata.get('description') or ''), 'path': str(file.resolve())})
        return {'roots': self.roots(workspace), 'items': rows}

    def snapshot(self, workspace, method_id, knowledge_refs):
        entries = []
        if method_id:
            method = next((row for row in self.catalog(workspace)['items'] if row['id'] == method_id), None)
            if method is None:
                raise ValueError('所选工作方法已不可用，请重新选择')
            file = Path(method['path']); root = file.parent
            files = {}
            total = 0
            for support in sorted(root.rglob('*')):
                if not support.is_file() or support.is_symlink() or any(p.startswith('.') or p in ('__pycache__', 'node_modules') for p in support.relative_to(root).parts):
                    continue
                if support.suffix not in ('.md', '.py', '.sh', '.txt', '.yaml', '.yml', '.json', '.toml'):
                    continue
                total += support.stat().st_size
                if len(files) >= 100 or total > 1_000_000:
                    raise ValueError('此 Skill 超过 100 个文本文件或 1 MB，请选择更聚焦的方法')
                files[support.relative_to(root).as_posix()] = support.read_text()
            content = files.pop('SKILL.md', '')
            if not content:
                raise ValueError('Skill 正文不可读取')
            digest = hashlib.sha256(json.dumps([content, files], sort_keys=True).encode()).hexdigest()
            entries.append({'id': method_id, 'title': method['title'], 'target': 'skill', 'version': digest, 'content': content, 'files': files, 'sourcePath': str(file), 'pinnedInput': True})
        for ref in dict.fromkeys(knowledge_refs or []):
            source_id, separator, path = ref.partition(':')
            if not separator:
                raise ValueError('知识引用格式不正确')
            doc = self.library.document(workspace, source_id, path)
            entries.append({'id': 'document-' + hashlib.sha256(ref.encode()).hexdigest()[:16], 'title': doc['title'], 'target': 'knowledge', 'version': doc['version'], 'content': doc['content'], 'sourcePath': ref, 'pinnedInput': True})
        if sum(len(row['content'].encode()) for row in entries) > 2_000_000:
            raise ValueError('任务知识正文合计超过 2 MB，请缩小选择范围')
        return entries

"""Markdown remains the source of truth; database rows are review history."""
from __future__ import annotations

import difflib
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from src.database import PGConnector


def fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


class Library:
    def __init__(self, postgres: PGConnector, roots: dict[str, Path]):
        self.db = postgres
        self.roots = roots

    def sources(self, workspace: str):
        if workspace not in self.roots:
            raise ValueError('工作区不存在')
        rows = self.db.fetch_all('SELECT id,title,root FROM workbench.library_source WHERE workspace=%s ORDER BY created_at', (workspace,))
        return [{'id': 'local', 'title': '工作台知识', 'root': str(self.roots[workspace]), 'writable': True}, *[{**row, 'writable': False} for row in rows]]

    def add_source(self, workspace: str, title: str, root: str):
        path = Path(root).expanduser().resolve()
        if not path.is_dir():
            raise ValueError('知识目录不存在')
        return self.db.fetch_one('INSERT INTO workbench.library_source(id,workspace,title,root) VALUES (%s,%s,%s,%s) ON CONFLICT(workspace,root) DO UPDATE SET title=excluded.title RETURNING id,title,root', ('source-'+uuid4().hex[:16],workspace,title,str(path)))

    def source(self, workspace: str, source_id: str):
        result = next((s for s in self.sources(workspace) if s['id'] == source_id), None)
        if result is None:
            raise KeyError('来源不存在')
        return result

    def file(self, workspace: str, source_id: str, relative: str) -> Path:
        root = Path(self.source(workspace, source_id)['root']).resolve()
        rel = Path(relative)
        if not relative or rel.is_absolute() or any(p in {'..', 'raw', '.git', '.runtime', 'node_modules'} or p.startswith('.') for p in rel.parts):
            raise ValueError('请选择知识目录中的 Markdown 文件，不包含原始材料和隐藏目录')
        path = (root / rel).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != '.md':
            raise ValueError('文件必须位于所选知识目录内，扩展名为 .md')
        return path

    def document(self, workspace: str, source_id: str, relative: str):
        source = self.source(workspace, source_id)
        path = self.file(workspace,source_id,relative)
        if not path.is_file():
            raise KeyError('文件不存在')
        if path.stat().st_size > 2_000_000:
            raise ValueError('文件超过 2 MB，请拆分或使用本地编辑器阅读')
        content = path.read_text(encoding='utf-8')
        return {'path':relative, 'sourceId':source_id, 'sourceTitle':source['title'], 'writable':source['writable'], 'content':content, 'version':fingerprint(content), 'title':self.title(content,relative)}

    @staticmethod
    def title(content: str, fallback: str):
        return next((line[2:].strip() for line in content.splitlines() if line.startswith('# ')), Path(fallback).stem)

    def catalog(self, workspace: str, query: str = ''):
        result = []; unavailable = []
        for source in self.sources(workspace):
            root = Path(source['root'])
            if not root.is_dir():
                unavailable.append(source['title']); continue
            for file in sorted(root.rglob('*.md')):
                relative = file.relative_to(root).as_posix()
                try:
                    doc = self.document(workspace,source['id'],relative)
                except (ValueError, KeyError, OSError, UnicodeError):
                    continue
                if query.casefold() not in (doc['title']+' '+relative+' '+doc['content']).casefold():
                    continue
                result.append({key:value for key,value in doc.items() if key != 'content'})
        return {'items':result,'unavailableSources':unavailable}

    def propose(self, workspace: str, source_id: str, path: str, content: str, base_version: str, reason: str):
        target = self.file(workspace,source_id,path)
        old = self.document(workspace,source_id,path)['content'] if target.exists() else ''
        expected = fingerprint(old) if target.exists() else 'new'
        if base_version != expected:
            raise ValueError('正文已经变化。请重新阅读并合并，草稿不会覆盖来源。')
        identity = 'revision-'+uuid4().hex[:16]
        row = self.db.fetch_one('INSERT INTO workbench.document_revision(id,workspace,source_id,path,base_version,before_content,content,reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *', (identity,workspace,source_id,path,base_version,old,content,reason))
        return self.with_diff(row)

    @staticmethod
    def with_diff(row):
        return {**row, 'diff': ''.join(difflib.unified_diff(row['before_content'].splitlines(keepends=True),row['content'].splitlines(keepends=True),fromfile='当前正文',tofile='建议正文'))}

    def revisions(self, workspace: str):
        return [self.with_diff(row) for row in self.db.fetch_all('SELECT * FROM workbench.document_revision WHERE workspace=%s ORDER BY created_at DESC', (workspace,))]

    def decide(self, workspace: str, revision_id: str, accept: bool):
        changed = False; temporary = None; before = None; target = None
        try:
            with self.db.transaction() as conn:
                conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('library-'+workspace,))
                row = conn.execute('SELECT * FROM workbench.document_revision WHERE workspace=%s AND id=%s FOR UPDATE', (workspace,revision_id)).fetchone()
                if not row:
                    raise KeyError('修订不存在')
                if row['status'] != 'draft':
                    raise ValueError('这份修订已经处理')
                if accept:
                    if not self.source(workspace,row['source_id'])['writable']:
                        raise ValueError('外部知识保持只读。可下载修订交给原知识库受审发布，或另存到工作台。')
                    target = self.file(workspace,row['source_id'],row['path'])
                    before = target.read_text(encoding='utf-8') if target.exists() else None
                    if (fingerprint(before) if before is not None else 'new') != row['base_version']:
                        raise ValueError('来源在审阅期间已变化，请重新合并后提出修订')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    temporary = target.with_name('.'+target.name+'.'+uuid4().hex+'.tmp')
                    with temporary.open('x',encoding='utf-8') as handle:
                        handle.write(row['content']); handle.flush(); os.fsync(handle.fileno())
                    temporary.replace(target); changed = True
                updated = conn.execute('UPDATE workbench.document_revision SET status=%s,accepted_at=now() WHERE id=%s RETURNING *', ('accepted' if accept else 'rejected',revision_id)).fetchone()
            return self.with_diff(updated)
        except Exception:
            if changed and target is not None:
                if before is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_text(before,encoding='utf-8')
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

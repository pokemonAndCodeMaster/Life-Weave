"""Read complete, owned output catalogs and pinned document/file content.

Catalog metadata and per-file reading share one immutable snapshot. Neither the
current worktree nor the truncated development diff is a document source.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import mimetypes
import os
import posixpath
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlsplit

import mistune

from .development_delivery import _git
from .research_bundle import build_bundle
from .research_outputs import ResearchOutputs

IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/avif'}
CODE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.vue', '.css', '.scss', '.sql',
                 '.sh', '.bash', '.json', '.yaml', '.yml', '.toml', '.lock', '.ini', '.html'}


def safe_path(path: str) -> str:
    if not path or '\x00' in path or '\\' in path or path.startswith('/'):
        raise ValueError('产物路径无效')
    normalized = posixpath.normpath(path)
    if normalized == '..' or normalized.startswith('../'):
        raise ValueError('产物路径超出交付目录')
    return normalized


def category(path: str, kind: str = 'document') -> str:
    parts = Path(path).parts
    if kind in {'decision', 'operation', 'finding'} and path == 'report.md':
        return 'record'
    if kind == 'validation' or 'evidence' in parts or 'verification' in parts:
        return 'verification'
    if Path(path).suffix.lower() in {'.md', '.txt', '.rst', '.pdf', '.docx'}:
        return 'document'
    if Path(path).suffix.lower() in CODE_SUFFIXES:
        return 'code'
    return 'attachment'


def text_content(data: bytes | None) -> str | None:
    if data is None or b'\x00' in data:
        return None
    try:
        return data.decode('utf-8')
    except UnicodeError:
        return None


def line_counts(before: bytes | None, after: bytes | None) -> tuple[int | None, int | None]:
    if text_content(before or b'') is None or text_content(after or b'') is None:
        return None, None
    # Legacy packages have exact Git blobs but predate saved numstat metadata.
    with tempfile.TemporaryDirectory(prefix='lifeweave-file-stat-') as directory:
        left, right = Path(directory) / 'before', Path(directory) / 'after'
        left.write_bytes(before or b'')
        right.write_bytes(after or b'')
        result = subprocess.run(['git', 'diff', '--no-index', '--no-ext-diff', '--numstat',
                                 str(left), str(right)], capture_output=True, timeout=20)
        if result.returncode not in {0, 1}:
            raise ValueError('无法核对文件改动行数')
        if not result.stdout:
            return 0, 0
        added, deleted, _ = result.stdout.split(b'\t', 2)
        return (None, None) if added == b'-' else (int(added), int(deleted))


class OutputFiles:
    def __init__(self, work: Any, runtime: Any, development: Any):
        self.work, self.runtime, self.development = work, runtime, development
        self.root = Path(development.project_root)
        self.library = None
        self.research = None  # Supplied by the app after both owners are constructed.

    def _entity(self, workspace: str, item_id: str, identity: str) -> dict:
        owned = any((r.get('fromKind'), r.get('fromId'), r.get('toKind'), r.get('toId'),
                     r.get('relationType')) == ('item', item_id, 'entity', identity, 'produces')
                    for r in self.work.repository.list_relations(workspace, item_id))
        value = self.work.repository.get_entity(workspace, identity) if owned else None
        if not value or value.get('entityType') != 'artifact':
            raise KeyError('产物不属于当前事项')
        return value

    def _run(self, workspace: str, item_id: str, identity: str) -> dict:
        run = self.runtime.get_run_snapshot(workspace, identity)
        if str(run.get('item_id') or run.get('itemId')) != item_id:
            raise KeyError('运行不属于当前事项')
        if run.get('state') != 'succeeded':
            raise ValueError('该运行尚未成功交付，过程请在运行记录查看')
        return run

    @staticmethod
    def _blob(archive: zipfile.ZipFile, entry: dict | None, legacy_repo: Path | None) -> bytes | None:
        if not entry:
            return None
        if entry.get('mode') not in {'100644', '100755', '120000'} or entry.get('type') != 'blob':
            raise ValueError('此交付包含特殊 Git 对象，不能作为普通文件读取')
        if entry.get('snapshot'):
            data = archive.read(entry['snapshot'])
            if hashlib.sha256(data).hexdigest() != entry.get('sha256'):
                raise ValueError('固定文件快照校验失败')
            return data
        oid = entry.get('oid', '')
        if legacy_repo is None or not re.fullmatch(r'[a-f0-9]{40,64}', oid):
            raise ValueError('旧交付没有文件快照，仍可下载原交付包')
        try:
            return _git(legacy_repo, 'cat-file', 'blob', oid)
        except (ValueError, OSError) as exc:
            raise ValueError('旧交付的固定 Git 对象已不可读取，仍可下载原交付包') from exc

    def _development_snapshot(self, data: bytes, title: str, version: str,
                              legacy_repo: Path | None = None) -> dict:
        if hashlib.sha256(data).hexdigest() != version:
            raise ValueError('固定交付包校验失败')
        files = []
        contents = {}
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            for row in manifest['files'] + manifest.get('resources', []):
                if row.get('renameTarget'):
                    continue
                path = safe_path(row['path'])
                before = self._blob(archive, row.get('before'), legacy_repo)
                after = self._blob(archive, row.get('after'), legacy_repo)
                contents[path] = (before, after)
                files.append(self._file_meta(path, before, after, row=row))
            report = archive.read('implementation-result.md')
            path = 'implementation-result.md'
            # A project may already contain this filename; keep its source intact.
            if path in contents:
                path = 'delivery/implementation-result.md'
            contents[path] = (None, report)
            files.append(self._file_meta(path, None, report, kind='document', status='unchanged'))
        return {'title': title, 'version': version, 'kind': 'code', 'files': files, 'contents': contents,
                'bundle': data, 'warnings': []}

    @staticmethod
    def _file_meta(path: str, before: bytes | None, after: bytes | None, *, row: dict | None = None,
                   kind: str = 'document', status: str = 'unchanged') -> dict:
        row = row or {}
        data = after if after is not None else before or b''
        binary = text_content(data) is None
        if row.get('status') == 'unchanged' or not row:
            additions, deletions = None, None
        elif 'additions' in row:
            additions, deletions = row['additions'], row['deletions']
        else:
            additions, deletions = line_counts(before, after)
        return {'path': path, 'previousPath': row.get('previousPath'), 'category': category(path, kind),
                'status': row.get('status', status), 'additions': additions, 'deletions': deletions,
                'binary': binary, 'size': len(data),
                'contentType': mimetypes.guess_type(path)[0] or ('application/octet-stream' if binary else 'text/plain')}

    def _snapshot(self, workspace: str, item_id: str, output_id: str) -> dict:
        self.work.get_item(workspace, item_id)
        family, _, identity = output_id.partition(':')
        if not identity:
            raise KeyError('产物不存在')
        if family == 'delivery':
            assignment = self.development.get(workspace, identity)
            if assignment['itemId'] != item_id:
                raise KeyError('开发交付不属于当前事项')
            delivery = self.development.delivery(workspace, identity)
            if not delivery:
                raise ValueError('尚无固定代码交付')
            run = self._run(workspace, item_id, delivery['implementationRunId'])
            actual = (run.get('environment_snapshot') or {}).get('actualDirectory')
            legacy = Path(actual).resolve() if actual else None
            if legacy and not legacy.is_relative_to((self.root / '.runtime' / 'executions').resolve()):
                legacy = None
            snapshot = self._development_snapshot(self.development.delivery_bytes(workspace, identity),
                                              '代码交付', delivery['artifactSha256'], legacy)
            snapshot['repositoryPath'] = assignment.get('repositoryPath')
            return snapshot
        if family == 'artifact':
            entity = self._entity(workspace, item_id, identity)
            payload = entity.get('payload') or {}
            fixed = payload.get('fixedDelivery')
            if fixed:
                digest = fixed['sha256']
                if not re.fullmatch(r'[a-f0-9]{64}', digest):
                    raise ValueError('固定交付身份无效')
                data = (self.root / '.runtime' / 'output-deliveries' / f'{digest}.zip').read_bytes()
                snapshot = self._development_snapshot(data, entity['title'], digest)
                snapshot['repositoryPath'] = fixed.get('repositoryPath')
                return snapshot
            content = str(payload.get('body') or '')
            immutable = self.work.repository._postgres.fetch_one(
                'SELECT artifact_version,payload FROM workbench.t_lifeweave_evidence '
                'WHERE workspace_key=%s AND item_id=%s AND artifact_ref=%s '
                'ORDER BY created_at LIMIT 1', (workspace, item_id, identity))
            if immutable and isinstance(immutable['payload'].get('body'), str):
                # The manual result endpoint saves evidence atomically. Reading it
                # preserves the delivered version even if the entity is later edited.
                content = immutable['payload']['body']
                payload = {**payload, 'artifactVersion': immutable['artifact_version'],
                           'resultKind': immutable['payload'].get('resultKind', payload.get('resultKind', 'document'))}
                entity = {**entity, 'title': immutable['payload'].get('title', entity['title'])}
            if not content.strip():
                raise ValueError('该产物尚无可读正文')
            data = content.encode()
            version = payload.get('artifactVersion') or hashlib.sha256(data).hexdigest()
            kind = payload.get('resultKind') or 'document'
            return {'title': entity['title'], 'version': version, 'kind': kind,
                    'files': [self._file_meta('report.md', None, data, kind=kind)],
                    'contents': {'report.md': (None, data)}, 'warnings': []}
        if family == 'run':
            run = self._run(workspace, item_id, identity)
            content = ResearchOutputs._content(run)
            if not content.strip():
                raise ValueError('该运行没有可读成果')
            kind = 'document'
            for assignment in self.development.list(workspace, item_id):
                if assignment.get('planRunId') == identity:
                    kind = 'plan'
                elif assignment.get('reviewRunId') == identity:
                    kind = 'decision'
            # Research packaging already resolves cited files, rejects traversal and
            # preserves math. Freeze that exact package on first use for later reads.
            key = hashlib.sha256((workspace + identity + content).encode()).hexdigest()
            cache = self.root / '.runtime' / 'output-snapshots' / (key + '.zip')
            if cache.exists():
                data = cache.read_bytes()
            else:
                if self.research is None:
                    raise ValueError('研究产物读取尚未初始化')
                _, _, data = build_bundle(self.research, workspace, identity)
                cache.parent.mkdir(parents=True, exist_ok=True)
                temporary = cache.with_suffix('.' + os.urandom(6).hex() + '.tmp')
                try:
                    temporary.write_bytes(data)
                    try:
                        os.link(temporary, cache)
                    except FileExistsError:
                        data = cache.read_bytes()
                finally:
                    temporary.unlink(missing_ok=True)
            contents, files = {}, []
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                manifest = json.loads(archive.read('manifest.json'))
                for path in ['report.md'] + [r['file'] for r in manifest['files']]:
                    value = archive.read(path)
                    contents[path] = (None, value)
                    files.append(self._file_meta(path, None, value, kind=kind))
            return {'title': manifest['title'], 'version': hashlib.sha256(data).hexdigest(), 'kind': kind,
                    'files': files, 'contents': contents, 'bundle': data,
                    'warnings': manifest.get('warnings', []),
                    'snapshotBoundary': '运行正文及引用文件在本阅读快照首次生成时固定。'}
        raise KeyError('不支持的产物身份')

    def _checked(self, workspace: str, item_id: str, output_id: str, version: str | None) -> dict:
        snapshot = self._snapshot(workspace, item_id, output_id)
        if version is not None and snapshot['version'] != version:
            raise ValueError('指定成果版本与保存的交付不一致，请返回产物目录选择版本')
        return snapshot

    def catalog(self, workspace: str, item_id: str, output_id: str, version: str | None = None) -> dict:
        snapshot = self._checked(workspace, item_id, output_id, version)
        files = []
        for source in snapshot['files']:
            row = dict(source)
            if Path(row['path']).suffix.lower() in {'.md', '.txt', '.rst'} and not row['binary']:
                row['documentRef'] = {'itemId': item_id, 'outputId': output_id,
                                      'path': row['path'], 'version': snapshot['version']}
            files.append(row)
        return {'outputId': output_id, 'title': snapshot['title'], 'version': snapshot['version'],
                'kind': snapshot['kind'], 'readable': True, 'files': files,
                'warnings': snapshot['warnings'], 'snapshotBoundary': snapshot.get('snapshotBoundary')}

    def file(self, workspace: str, item_id: str, output_id: str, path: str,
             version: str | None = None) -> dict:
        snapshot = self._checked(workspace, item_id, output_id, version)
        path = safe_path(path)
        if path not in snapshot['contents']:
            raise KeyError('固定交付中没有此文件')
        before, after = snapshot['contents'][path]
        row = next(row for row in snapshot['files'] if row['path'] == path)
        left, right = text_content(before), text_content(after)
        patch = None
        if not row['binary'] and row['status'] != 'unchanged':
            patch = ''.join(difflib.unified_diff((left or '').splitlines(keepends=True),
                                                (right or '').splitlines(keepends=True),
                                                fromfile=row.get('previousPath') or path, tofile=path))
        return {**row, 'version': snapshot['version'], 'before': left, 'after': right,
                'content': right if after is not None else left, 'diff': patch}

    def bytes(self, workspace: str, item_id: str, output_id: str, path: str,
              version: str | None = None) -> tuple[bytes, str]:
        snapshot = self._checked(workspace, item_id, output_id, version)
        path = safe_path(path)
        if path not in snapshot['contents']:
            raise KeyError('固定交付中没有此文件')
        before, after = snapshot['contents'][path]
        row = next(row for row in snapshot['files'] if row['path'] == path)
        return after if after is not None else before or b'', row['contentType']

    def document(self, workspace: str, item_id: str, output_id: str, path: str,
                 version: str | None = None) -> dict:
        file = self.file(workspace, item_id, output_id, path, version)
        if file['binary'] or file['content'] is None:
            raise ValueError('此产物不是可阅读的文本，请下载文件')
        refs: dict[str, Any] = {'links': {}, 'images': {}, 'warnings': []}
        snapshot = self._checked(workspace, item_id, output_id, file['version'])
        tokens = mistune.create_markdown(renderer='ast')(file['content'])
        def walk(nodes):
            for token in nodes:
                if token.get('type') in {'image', 'link'}:
                    href = token['attrs']['url']
                    parsed = urlsplit(unquote(href))
                    if not parsed.scheme and not parsed.netloc and parsed.path:
                        try:
                            target = safe_path(posixpath.join(posixpath.dirname(path), parsed.path))
                            if target not in snapshot['contents']:
                                raise KeyError(target)
                            query = urlencode({'outputId': output_id, 'path': target, 'version': file['version']})
                            if token['type'] == 'image':
                                refs['images'][unquote(href)] = f'/api/lifeweave/{workspace}/items/{quote(item_id, safe="")}/outputs/asset?{query}'
                            else:
                                refs['links'][unquote(href)] = f'/lifeweave/{workspace}/knowledge?' + urlencode({
                                    'item': item_id, 'output': output_id, 'path': target, 'version': file['version']})
                        except (ValueError, KeyError):
                            refs['warnings'].append('本交付未包含引用：' + href)
                walk(token.get('children', []))
        walk(tokens)
        current_source = None
        if self.library is not None and snapshot.get('repositoryPath'):
            repository = Path(snapshot['repositoryPath']).resolve()
            for source in self.library.sources(workspace):
                if Path(source['root']).resolve() != repository:
                    continue
                try:
                    if self.library.file(workspace, source['id'], path).is_file():
                        current_source = {'sourceId': source['id'], 'path': path}
                        break
                except (KeyError, ValueError, OSError):
                    continue
        return {'title': Path(path).name, 'content': file['content'], 'path': path, 'version': file['version'],
                'sourceId': 'work-output', 'sourceTitle': snapshot['title'], 'writable': False,
                'references': refs, 'kind': 'artifact', 'itemId': item_id, 'outputId': output_id,
                'contentType': file['contentType'], 'currentSource': current_source}

    def bundle(self, workspace: str, item_id: str, output_id: str, version: str | None = None) -> bytes:
        snapshot = self._checked(workspace, item_id, output_id, version)
        if snapshot.get('bundle') is not None:
            return snapshot['bundle']
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, (before, after) in snapshot['contents'].items():
                archive.writestr(path, after if after is not None else before or b'')
        return buffer.getvalue()

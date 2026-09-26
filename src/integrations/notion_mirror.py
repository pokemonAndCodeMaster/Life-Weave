"""One-way, versioned Notion mirror. Original Markdown remains authoritative."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from src.lifeweave.models import WorkspaceKey
from src.lifeweave.research_archive import document_content
from src.lifeweave.research_bundle import rewrite_markdown
from src.integrations.github_source import confirmed_github_blob


NOTION_VERSION = '2026-03-11'


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class MirrorSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    tokenFile: str = Field(default='', max_length=4096)
    rootPage: str = Field(default='', max_length=500)


class NotionMirror:
    def __init__(self, root: Path):
        self.root = root
        self.folder = root / '.runtime' / 'notion-mirror'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.folder.chmod(0o700)

    @contextmanager
    def locked(self, workspace: str):
        folder = self.folder / workspace
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / 'lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield folder
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    @staticmethod
    def save(path: Path, value: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        temporary.chmod(0o600)
        temporary.replace(path)

    def settings(self, workspace: str) -> dict:
        path = self.folder / workspace / 'settings.json'
        return json.loads(path.read_text()) if path.exists() else MirrorSettings().model_dump()

    @staticmethod
    def page_id(value: str) -> str:
        match = re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', value)
        if not match:
            raise ValueError('请输入 Notion 页面链接或页面 ID')
        return match.group(1).replace('-', '')

    @staticmethod
    def token(settings: dict) -> str:
        path = Path(settings.get('tokenFile') or '').expanduser()
        if not path.is_file() or path.is_symlink():
            raise ValueError('Notion 凭据文件不存在或不是普通文件')
        stat = path.stat()
        if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise ValueError('Notion 凭据文件必须属于当前用户，且权限不宽于 600')
        value = path.read_text().strip()
        if not value:
            raise ValueError('Notion 凭据文件为空')
        return value

    def request(self, settings: dict, method: str, path: str, data: dict | None = None) -> dict:
        headers = {'Authorization': 'Bearer ' + self.token(settings), 'Notion-Version': NOTION_VERSION,
                   'Content-Type': 'application/json'}
        try:
            with httpx.Client(base_url='https://api.notion.com/v1', timeout=30) as client:
                response = client.request(method, path, headers=headers, json=data)
            if response.status_code >= 400:
                raise ValueError(f'Notion 请求失败（HTTP {response.status_code}）；请检查页面共享、集成权限与内容限制')
            return response.json()
        except httpx.HTTPError as exc:
            raise ValueError('Notion 网络请求失败，可稍后重试') from exc

    def configure(self, workspace: str, value: MirrorSettings) -> dict:
        settings = value.model_dump()
        if settings['enabled']:
            self.page_id(settings['rootPage'])
            self.request(settings, 'GET', '/pages/' + self.page_id(settings['rootPage']))
        with self.locked(workspace) as folder:
            self.save(folder / 'settings.json', settings)
        return self.public_settings(workspace)

    def public_settings(self, workspace: str) -> dict:
        value = self.settings(workspace)
        return {'enabled': value['enabled'], 'rootPage': value['rootPage'],
                'tokenFile': value['tokenFile'], 'configured': bool(value['enabled'] and value['tokenFile'] and value['rootPage'])}

    def state(self, workspace: str) -> dict:
        path = self.folder / workspace / 'state.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def record_failure(self, workspace: str, source: str, version: str, error: str) -> None:
        with self.locked(workspace) as folder:
            state = self.state(workspace)
            previous = state.get(source) or {'source': source, 'status': 'failed'}
            state[source] = {**previous, 'lastAttempt': {
                'status': 'failed', 'version': version, 'error': error[:500]}}
            self.save(folder / 'state.json', state)

    def _find_child(self, settings: dict, title: str) -> dict | None:
        cursor = None
        for _ in range(100):
            path = '/blocks/' + self.page_id(settings['rootPage']) + '/children?page_size=100'
            if cursor:
                path += '&start_cursor=' + quote(cursor)
            data = self.request(settings, 'GET', path)
            for child in data.get('results', []):
                if child.get('type') == 'child_page' and child.get('child_page', {}).get('title') == title:
                    return child
            cursor = data.get('next_cursor')
            if not cursor:
                break
        return None

    def sync(self, workspace: str, source: str, title: str, content: str, version: str, url: str) -> dict:
        settings = self.settings(workspace)
        if not settings['enabled']:
            return {'status': 'unconfigured'}
        identity = digest(source)[:16]
        stable_title = f'LifeWeave · {title} [{identity}]'
        body = f'> 原文位置：[打开来源]({url}) · 源版本 `{version}`。此页是自动镜像，请在原处修改。\n\n' + content
        with self.locked(workspace) as folder:
            state_file = folder / 'state.json'
            state = self.state(workspace)
            previous = state.get(source)
            if previous and previous.get('status') == 'confirmed' and previous['version'] == version and previous.get('sourceUrl') == url:
                actual = self.request(settings, 'GET', f'/pages/{previous["pageId"]}/markdown')
                if actual.get('truncated') or actual.get('unknown_block_ids') or digest(actual.get('markdown', '')) != previous['readbackHash']:
                    raise ValueError('Notion 镜像页已变化或无法完整回读，未沿用旧确认')
                if previous.get('lastAttempt'):
                    previous = {key: value for key, value in previous.items() if key != 'lastAttempt'}
                    state[source] = previous
                    self.save(state_file, state)
                return previous
            page_id = previous.get('pageId') if previous else None
            if not page_id:
                child = self._find_child(settings, stable_title)
                if child:
                    raise ValueError('Notion 已存在同名镜像页但本地没有写入记录；请先核对，未覆盖远端内容')
                created = self.request(settings, 'POST', '/pages', {
                    'parent': {'page_id': self.page_id(settings['rootPage'])},
                    'properties': {'title': {'type': 'title', 'title': [{'type': 'text', 'text': {'content': stable_title}}]}},
                    'markdown': body})
                page_id = created['id']
                state[source] = {'status': 'pending', 'pageId': page_id, 'pendingVersion': version}
                self.save(state_file, state)
            else:
                actual = self.request(settings, 'GET', f'/pages/{page_id}/markdown')
                if actual.get('truncated') or actual.get('unknown_block_ids'):
                    raise ValueError('Notion 镜像页存在无法完整回读的区块，未覆盖')
                if previous.get('status') == 'pending':
                    if previous.get('pendingVersion') != version or version not in actual.get('markdown', ''):
                        raise ValueError('Notion 上次写入未完成，需人工核对，未覆盖远端内容')
                elif digest(actual.get('markdown', '')) != previous['readbackHash']:
                    raise ValueError('Notion 镜像页已被外部修改，未覆盖；请在原文维护后处理冲突')
                else:
                    state[source] = {**previous, 'status': 'pending', 'pendingVersion': version}
                    self.save(state_file, state)
                    self.request(settings, 'PATCH', f'/pages/{page_id}/markdown', {
                        'type': 'replace_content', 'replace_content': {'new_str': body}})
            readback = self.request(settings, 'GET', f'/pages/{page_id}/markdown')
            if readback.get('truncated') or readback.get('unknown_block_ids'):
                raise ValueError('Notion 回读不完整，未确认镜像')
            remote = readback.get('markdown', '')
            if not remote.strip() or document_content(remote) != document_content(body):
                raise ValueError('Notion 回读正文与来源不一致，未确认镜像')
            record = {'status': 'confirmed', 'source': source, 'version': version,
                      'sourceUrl': url,
                      'pageId': page_id, 'url': 'https://www.notion.so/' + page_id.replace('-', ''),
                      'readbackHash': digest(remote)}
            state[source] = record
            self.save(state_file, state)
            return record

    def sync_current_docs(self, workspace: str) -> dict:
        if not self.settings(workspace)['enabled']:
            return {'status': 'unconfigured', 'count': 0}
        config = json.loads((self.root / 'docs/current-sources.json').read_text())
        count = 0
        failed = {}
        for relative in config['paths']:
            source = f'project:{relative}'
            version = 'unavailable'
            try:
                path = (self.root / relative).resolve()
                if not path.is_relative_to(self.root) or not path.is_file():
                    raise ValueError('项目当前文档路径不可读取')
                content = path.read_text()
                version = digest(content)
                url = self.confirmed_source_url(relative, content, config)
                self.sync(workspace, source, relative, content, version,
                          url)
                count += 1
            except (ValueError, OSError) as exc:
                self.record_failure(workspace, source, version, str(exc))
                failed[source] = str(exc)
        return {'status': 'partial' if failed else 'confirmed', 'count': count,
                'failedCount': len(failed), 'errors': failed}

    def sync_current_document(self, workspace: str, source_id: str,
                              path: str, expected_version: str) -> dict:
        if source_id != 'lifeweave-project':
            raise ValueError('目前仅支持当前项目清单中的原文单篇发布')
        config = json.loads((self.root / 'docs/current-sources.json').read_text())
        if path not in config['paths']:
            raise ValueError('此文档不在当前项目原文清单中')
        source = (self.root / path).resolve()
        if not source.is_relative_to(self.root.resolve()) or not source.is_file():
            raise ValueError('项目原文不可读取')
        content = source.read_text(encoding='utf-8')
        version = digest(content)
        if version != expected_version:
            raise ValueError('原文版本已变化，请重新打开后再发布')
        if not self.settings(workspace)['enabled']:
            return {'status': 'unconfigured', 'version': version}
        source_key = f'project:{path}'
        try:
            url = self.confirmed_source_url(path, content, config)
            return self.sync(workspace, source_key, path, content, version,
                             url)
        except (ValueError, OSError) as exc:
            self.record_failure(workspace, source_key, version, str(exc))
            raise

    def confirmed_source_url(self, path: str, content: str, config: dict) -> str:
        """Link an immutable GitHub blob only if this exact body is on main."""
        return confirmed_github_blob(self.root, path, content.encode('utf-8'),
                                     str(config.get('archiveBaseUrl') or ''))

    def sync_report(self, workspace: str, manifest: dict, report: str, github_url: str) -> dict:
        if not self.settings(workspace)['enabled']:
            return {'status': 'unconfigured'}
        base = github_url.rsplit('/', 1)[0]
        raw_base = re.sub(r'^https://github\.com/([^/]+)/([^/]+)/blob/',
                          r'https://raw.githubusercontent.com/\1/\2/', base + '/')
        def link(url: str, image: bool) -> str:
            if url.startswith('#'):
                return github_url + url
            if re.match(r'^[a-z]+:', url, re.I):
                return url
            return (raw_base if image else base + '/') + quote(url)
        report = rewrite_markdown(report, link)
        return self.sync(workspace, f'research:{manifest["runId"]}',
                         manifest['title'] + ' · ' + manifest['runId'], report,
                         manifest['version'], github_url)


router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['notion-mirror'])


class DocumentSync(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sourceId: str = Field(min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=1000)
    expectedVersion: str = Field(min_length=64, max_length=64)


@router.get('/notion-mirror/settings')
def settings(request: Request, workspace: WorkspaceKey):
    return request.app.state.notion_mirror.public_settings(workspace)


@router.put('/notion-mirror/settings')
def configure(request: Request, workspace: WorkspaceKey, body: MirrorSettings):
    try:
        return request.app.state.notion_mirror.configure(workspace, body)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/notion-mirror/status')
def status(request: Request, workspace: WorkspaceKey):
    return request.app.state.notion_mirror.state(workspace)


@router.post('/notion-mirror/sync')
def sync(request: Request, workspace: WorkspaceKey):
    try:
        return request.app.state.notion_mirror.sync_current_docs(workspace)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/notion-mirror/document')
def sync_document(request: Request, workspace: WorkspaceKey, body: DocumentSync):
    try:
        return request.app.state.notion_mirror.sync_current_document(
            workspace, body.sourceId, body.path, body.expectedVersion)
    except (ValueError, OSError, UnicodeError) as exc:
        raise HTTPException(409, str(exc)) from exc

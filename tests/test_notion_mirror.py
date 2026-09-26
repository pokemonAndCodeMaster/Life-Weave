"""Notion mirror preserves originals and does not overwrite a changed remote page."""
import hashlib
import json
from pathlib import Path

import pytest

from src.integrations.notion_mirror import MirrorSettings, NotionMirror


def test_mirror_create_update_readback_and_conflict(tmp_path, monkeypatch):
    mirror = NotionMirror(tmp_path)
    token = tmp_path / 'notion-token'
    token.write_text('test-token')
    token.chmod(0o600)
    root_id = '3e7af682864481769d2decf36863c820'
    remote = {}
    calls = []

    def request(_settings, method, path, data=None):
        calls.append((method, path))
        if method == 'GET' and path == '/pages/' + root_id:
            return {'id': root_id}
        if path.startswith('/blocks/'):
            return {'results': [], 'next_cursor': None}
        if method == 'POST':
            page_id = '11111111-1111-1111-1111-111111111111'
            remote[page_id] = data['markdown']
            return {'id': page_id}
        page_id = path.split('/')[2]
        if method == 'GET':
            return {'markdown': remote[page_id], 'truncated': False, 'unknown_block_ids': []}
        if method == 'PATCH':
            remote[page_id] = data['replace_content']['new_str']
            return {'markdown': remote[page_id]}
        raise AssertionError((method, path))

    monkeypatch.setattr(mirror, 'request', request)
    mirror.configure('personal', MirrorSettings(enabled=True, tokenFile=str(token), rootPage=root_id))
    first = mirror.sync('personal', 'project:README.md', 'README.md', '# First', 'v1', 'https://example.test/original')
    assert first['status'] == 'confirmed' and first['url'].startswith('https://www.notion.so/')
    count = len(calls)
    assert mirror.sync('personal', 'project:README.md', 'README.md', '# First', 'v1', 'https://example.test/original') == first
    assert len(calls) == count + 1  # Re-read remote even for an unchanged source version.
    remote[first['pageId']] += '\nHuman edit'
    with pytest.raises(ValueError, match='已变化'):
        mirror.sync('personal', 'project:README.md', 'README.md', '# First', 'v1', 'https://example.test/original')
    remote[first['pageId']] = remote[first['pageId']].removesuffix('\nHuman edit')
    updated = mirror.sync('personal', 'project:README.md', 'README.md', '# Second', 'v2', 'https://example.test/original')
    assert updated['version'] == 'v2' and '# Second' in remote[updated['pageId']]
    remote[updated['pageId']] += '\nHuman edit'
    with pytest.raises(ValueError, match='外部修改'):
        mirror.sync('personal', 'project:README.md', 'README.md', '# Third', 'v3', 'https://example.test/original')
    assert '# Third' not in remote[updated['pageId']]


def test_token_file_permissions_and_current_doc_inventory(tmp_path, monkeypatch):
    mirror = NotionMirror(tmp_path)
    token = tmp_path / 'token'
    token.write_text('secret')
    token.chmod(0o644)
    with pytest.raises(ValueError, match='权限'):
        mirror.token({'tokenFile': str(token)})
    token.chmod(0o600)
    assert mirror.token({'tokenFile': str(token)}) == 'secret'
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'README.md').write_text('# Source original')
    (tmp_path / 'docs/current-sources.json').write_text(json.dumps({
        'archiveBaseUrl': 'https://example.test/repo/blob/main', 'paths': ['README.md']}))
    mirror.save(mirror.folder / 'personal/settings.json', MirrorSettings(
        enabled=True, tokenFile=str(token), rootPage='3e7af682864481769d2decf36863c820').model_dump())
    seen = []
    monkeypatch.setattr(mirror, 'sync', lambda *args: seen.append(args))
    assert mirror.sync_current_docs('personal')['count'] == 1
    assert seen[0][1] == 'project:README.md'
    assert seen[0][4] == hashlib.sha256(b'# Source original').hexdigest()
    assert (tmp_path / 'README.md').read_text() == '# Source original'


def test_mirror_does_not_confirm_truncated_body_even_with_version(tmp_path, monkeypatch):
    mirror = NotionMirror(tmp_path)
    token = tmp_path / 'token'
    token.write_text('test-token')
    token.chmod(0o600)
    root_id = '3e7af682864481769d2decf36863c820'
    page_id = '11111111-1111-1111-1111-111111111111'

    def request(_settings, method, path, data=None):
        if path.startswith('/blocks/'):
            return {'results': [], 'next_cursor': None}
        if method == 'POST':
            return {'id': page_id}
        if method == 'GET':
            return {'markdown': '> 原文位置：源版本 `v1`。\n\n# Title',
                    'truncated': False, 'unknown_block_ids': []}
        raise AssertionError((method, path))

    monkeypatch.setattr(mirror, 'request', request)
    mirror.save(mirror.folder / 'personal/settings.json', MirrorSettings(
        enabled=True, tokenFile=str(token), rootPage=root_id).model_dump())
    with pytest.raises(ValueError, match='不一致'):
        mirror.sync('personal', 'project:one', 'One', '# Title\n\nImportant final paragraph.',
                    'v1', 'https://example.test/one')
    assert mirror.state('personal')['project:one']['status'] == 'pending'


def test_project_doc_failure_does_not_block_next_source(tmp_path, monkeypatch):
    mirror = NotionMirror(tmp_path)
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'README.md').write_text('# One')
    (tmp_path / 'docs/status.md').write_text('# Two')
    (tmp_path / 'docs/current-sources.json').write_text(json.dumps({
        'archiveBaseUrl': 'https://example.test/main', 'paths': ['README.md', 'docs/status.md']}))
    mirror.save(mirror.folder / 'personal/settings.json', MirrorSettings(
        enabled=True, tokenFile='/tmp/not-used', rootPage='3e7af682864481769d2decf36863c820').model_dump())
    attempted = []

    def fake_sync(_workspace, source, *_args):
        attempted.append(source)
        if source == 'project:README.md':
            raise ValueError('remote changed')
        return {'status': 'confirmed'}

    monkeypatch.setattr(mirror, 'sync', fake_sync)
    result = mirror.sync_current_docs('personal')
    assert attempted == ['project:README.md', 'project:docs/status.md']
    assert result['status'] == 'partial' and result['count'] == 1 and result['failedCount'] == 1
    assert mirror.state('personal')['project:README.md']['lastAttempt']['error'] == 'remote changed'


def test_missing_project_doc_records_failure_and_continues(tmp_path, monkeypatch):
    mirror = NotionMirror(tmp_path)
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'README.md').write_text('# Present')
    (tmp_path / 'docs/current-sources.json').write_text(json.dumps({
        'archiveBaseUrl': 'https://example.test/main', 'paths': ['docs/missing.md', 'README.md']}))
    mirror.save(mirror.folder / 'personal/settings.json', MirrorSettings(
        enabled=True, tokenFile='/tmp/not-used', rootPage='3e7af682864481769d2decf36863c820').model_dump())
    seen = []
    monkeypatch.setattr(mirror, 'sync', lambda _workspace, source, *_args: seen.append(source))

    result = mirror.sync_current_docs('personal')

    assert result['status'] == 'partial' and result['count'] == 1 and result['failedCount'] == 1
    assert seen == ['project:README.md']
    assert mirror.state('personal')['project:docs/missing.md']['lastAttempt']['version'] == 'unavailable'

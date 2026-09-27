"""Pinned outputs remain readable after the live repository changes."""
import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from src.lifeweave.external_delivery import freeze_scoped
from src.lifeweave.output_files import OutputFiles
from test_live_database import dedicated_client, post

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j7ioAAAAASUVORK5CYII=')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init', '-q')
    git(root, 'config', 'user.name', 'Test')
    git(root, 'config', 'user.email', 'test@example.invalid')
    (root / 'before.py').write_text('first = 1\nsecond = 2\n')
    (root / 'user.txt').write_text('user baseline\n')
    (root / 'docs').mkdir()
    (root / 'docs/image.png').write_bytes(PNG)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    return root


def test_complete_fixed_catalog_rename_binary_and_media(tmp_path):
    root = repo(tmp_path)
    base = git(root, 'rev-parse', 'HEAD').decode().strip()
    (root / 'before.py').rename(root / 'after.py')
    (root / 'docs/report.md').write_text('# 报告\n\n![图片](image.png)\n\n$$x^2$$\n')
    (root / 'asset.bin').write_bytes(b'\x00\xff')
    paths = ['before.py', 'after.py', 'docs/report.md', 'asset.bin']
    for i in range(305):
        path = f'group{i % 5}/file{i}.py'
        (root / path).parent.mkdir(exist_ok=True)
        (root / path).write_text(f'value = {i}\n')
        paths.append(path)
    manifest, data = freeze_scoped(root, {'revision': base}, paths, '实际文件交付')
    assert len(manifest['files']) == 309  # Before/after paths remain in the replay manifest.
    assert manifest['resources'][0]['path'] == 'docs/image.png'
    reader = object.__new__(OutputFiles)
    result = reader._development_snapshot(data, '本次交付', hashlib.sha256(data).hexdigest())
    files = result['files']
    renamed = next(row for row in files if row['path'] == 'after.py')
    assert renamed['status'] == 'renamed' and renamed['previousPath'] == 'before.py'
    assert renamed['additions'] == renamed['deletions'] == 0
    assert not any(row['path'] == 'before.py' for row in files)
    binary = next(row for row in files if row['path'] == 'asset.bin')
    assert binary['binary'] and binary['additions'] is None and binary['deletions'] is None
    assert len([row for row in files if row['path'].startswith('group')]) == 305
    (root / 'after.py').write_text('changed later\n')
    (root / 'docs/image.png').unlink()
    again = reader._development_snapshot(data, '本次交付', hashlib.sha256(data).hexdigest())
    assert again['contents']['after.py'][1] == b'first = 1\nsecond = 2\n'
    assert again['contents']['docs/image.png'][1] == PNG
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read('changes.patch')
        assert 'blobs/' in '\n'.join(archive.namelist())


def test_external_capture_requires_attribution_and_safe_paths(tmp_path):
    root = repo(tmp_path)
    base = git(root, 'rev-parse', 'HEAD').decode().strip()
    (root / 'user.txt').write_text('before Agent already dirty\n')
    baseline = {'revision': base, 'changedPaths': ['user.txt'], 'changedCount': 1}
    with pytest.raises(ValueError, match='会话开始前'):
        freeze_scoped(root, baseline, ['user.txt'], '不应冒认')
    with pytest.raises(ValueError, match='超出'):
        freeze_scoped(root, baseline, ['../outside.txt'], '不应读取')
    with pytest.raises(ValueError, match='清单不完整'):
        freeze_scoped(root, {**baseline, 'changedCount': 101}, ['before.py'], '不能猜测')
    (root / 'before.py').write_text('new = True\n')
    manifest, _ = freeze_scoped(root, baseline, ['before.py'], '只捕获自己负责的范围')
    assert [row['path'] for row in manifest['files']] == ['before.py']
    assert (root / 'user.txt').read_text() == 'before Agent already dirty\n'
    assert git(root, 'diff', '--cached') == b''  # Capture never stages the user's real index.


def test_owned_document_and_external_delivery_http(dedicated_client, tmp_path):
    client = dedicated_client
    root = repo(tmp_path)
    client.app.state.output_files.root = tmp_path
    item = post(client, '/items', {'itemType': 'fix', 'title': '交付阅读'})
    route = f"/items/{item['id']}"
    session = post(client, route + '/external-development/sessions', {
        'requestId': 'start-files', 'repositoryPath': str(root), 'summary': '实现文件快照',
        'knowledgeRefs': ['lifeweave-project:docs/status.md']})['sessionId']
    (root / 'docs/report.md').write_text('# 本次报告\n\n![图片](image.png)\n')
    request = {'requestId': 'capture-files', 'title': '代码与报告', 'summary': '报告已编写，图片随交付固定。',
               'paths': ['docs/report.md']}
    capture_url = '/api/lifeweave/personal' + route + f'/external-development/sessions/{session}/delivery'
    captured = client.post(capture_url, json=request)
    assert captured.status_code == 201, captured.text
    assert client.post(capture_url, json=request).json() == captured.json()
    assert client.post(capture_url, json={**request, 'summary': 'changed'}).status_code == 409
    output = captured.json()['outputId']
    api = '/api/lifeweave/personal' + route + '/outputs'
    catalog = client.get(api + '/catalog', params={'outputId': output})
    assert catalog.status_code == 200, catalog.text
    body = catalog.json()
    assert body['readable'] and body['version'] == captured.json()['version']
    assert {row['path'] for row in body['files']} == {'docs/report.md', 'docs/image.png', 'implementation-result.md'}
    params = {'outputId': output, 'version': body['version'], 'path': 'docs/report.md'}
    doc = client.get(api + '/document', params=params).json()
    assert doc['currentSource'] is None
    source = client.app.state.library.add_source('personal', '实际目标仓', str(root))
    doc = client.get(api + '/document', params=params).json()
    assert doc['currentSource'] == {'sourceId': source['id'], 'path': 'docs/report.md'}
    assert doc['kind'] == 'artifact' and not doc['writable']
    assert doc['references']['images']['image.png'].startswith(api + '/asset?')
    image = client.get(doc['references']['images']['image.png'])
    assert image.status_code == 200 and image.content == PNG
    (root / 'docs/report.md').write_text('后来修改的内容，不属于交付。')
    assert client.get(api + '/document', params=params).json()['content'].startswith('# 本次报告')
    assert client.get(api + '/document', params={**params, 'version': 'wrong'}).status_code == 409
    assert client.get(api + '/file', params={**params, 'path': '../user.txt'}).status_code == 409
    other = post(client, '/items', {'itemType': 'fix', 'title': '另一个事项'})
    assert client.get(api.replace(item['id'], other['id']) + '/catalog', params={'outputId': output}).status_code == 404
    assert client.get(api.replace('/personal/', '/team/') + '/catalog', params={'outputId': output}).status_code == 404
    downloaded = client.get(api + '/bundle', params={'outputId': output, 'version': body['version']})
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert json.loads(archive.read('manifest.json'))['baseRevision']
    manual = post(client, route + '/manual-results', {'title': '真实审查', 'content': '# 审查结论\n有依据。',
                  'verification': '仅测试固定文档读取', 'environment': '隔离测试数据库', 'resultKind': 'decision'})
    result = client.get(api + '/catalog', params={'outputId': 'artifact:' + manual['artifactId']})
    assert result.json()['kind'] == 'decision'
    assert result.json()['files'][0]['category'] == 'record'

    # Reading a delivered result uses its immutable evidence, even if entity metadata changes.
    client.app.state.database_manager.postgres().execute(
        "UPDATE workbench.t_lifeweave_entity SET payload=payload || %s::jsonb WHERE id=%s",
        (json.dumps({'body': 'later unrelated edit'}), manual['artifactId']))
    frozen = client.get(api + '/document', params={'outputId': 'artifact:' + manual['artifactId'],
                       'path': 'report.md', 'version': result.json()['version']})
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()['content'] == '# 审查结论\n有依据。'

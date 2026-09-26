"""Authored semantics remain linked to exact source and implementation versions."""
import hashlib
import json

from test_live_database import dedicated_client


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authored_knowledge_relation_is_current_then_stale(dedicated_client, tmp_path):
    client = dedicated_client
    root = tmp_path / 'project'
    (root / 'docs').mkdir(parents=True)
    (root / 'src').mkdir()
    source = root / 'docs/plugin-system.md'
    target = root / 'src/real.py'
    source.write_text('# Plugin\n\nThis behavior is implemented here.\n')
    target.write_text('def real(): return True\n')
    (root / 'docs/current-sources.json').write_text(json.dumps({
        'id': 'lifeweave-project', 'title': 'Project',
        'archiveBaseUrl': 'https://example.test/repo/blob/main',
        'paths': ['docs/plugin-system.md']}))
    (root / 'docs/knowledge-relations.json').write_text(json.dumps({
        'version': 1, 'relations': [{
            'sourceId': 'lifeweave-project', 'sourcePath': 'docs/plugin-system.md',
            'sourceVersion': sha(source), 'relation': 'implemented_by',
            'targetPath': 'src/real.py', 'targetVersion': sha(target),
            'evidenceQuote': 'This behavior is implemented here.',
        }]}))
    client.app.state.library.project_root = root
    params = {'sourceId': 'lifeweave-project', 'path': 'docs/plugin-system.md'}
    url = '/api/lifeweave/personal/library/relations'
    current = client.get(url, params=params)
    assert current.status_code == 200, current.text
    relation = current.json()['items'][0]
    assert relation['status'] == 'current'
    assert relation['targetUrl'] is None  # Local version is not confirmed on GitHub.
    target.write_text('def real(): return False\n')
    assert client.get(url, params=params).json()['items'][0]['status'] == 'stale'
    target.unlink()
    assert client.get(url, params=params).json()['items'][0]['status'] == 'missing'
    assert client.get(url, params={'sourceId': 'local', 'path': 'docs/plugin-system.md'}).status_code == 404

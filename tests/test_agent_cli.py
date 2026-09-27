"""Public command contracts independent of an Agent's session memory."""
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest


@pytest.fixture
def cli():
    spec = importlib.util.spec_from_file_location('lifeweave_client', Path(__file__).parents[1] / 'scripts/lifeweave.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runs_without_item_filter_reads_every_page(cli, monkeypatch, capsys):
    urls = []

    def response(request, **_):
        urls.append(request.full_url)
        return io.BytesIO(json.dumps({'items': [{'id': str(len(urls))}], 'total': 2}).encode())

    monkeypatch.setattr(cli, 'urlopen', response)
    assert cli.main(['runs']) == 0
    assert json.loads(capsys.readouterr().out) == {'items': [{'id': '1'}, {'id': '2'}], 'total': 2}
    assert 'offset=0' in urls[0] and 'offset=1' in urls[1]
    assert all('itemId' not in url for url in urls)


@pytest.mark.parametrize(('options', 'item_id', 'expected_url'), [
    ([], 'item-123', 'http://127.0.0.1:8010/api/lifeweave/personal/items/item-123/development/choices'),
    (['--workspace', 'team', '--url', 'http://localhost:8123/'], 'item-123',
     'http://localhost:8123/api/lifeweave/team/items/item-123/development/choices'),
    ([], '事项 /?#%',
     'http://127.0.0.1:8010/api/lifeweave/personal/items/%E4%BA%8B%E9%A1%B9%20%2F%3F%23%25/development/choices'),
])
def test_development_choices_read_only_contract(cli, monkeypatch, capsys, options, item_id, expected_url):
    requests = []
    payload = {
        'itemId': item_id,
        'recommendedRepositoryPath': '/tmp/项目',
        'agents': [{'id': 'development', 'title': '开发 Agent', 'available': True}],
        'executors': {'codex': {'available': True, 'reason': None}},
        'methodId': None,
        'knowledgeRefs': ['lifeweave-project:docs/architecture.md'],
    }

    def response(request, **_):
        requests.append(request)
        return io.BytesIO(json.dumps(payload, ensure_ascii=False).encode())

    monkeypatch.setattr(cli, 'urlopen', response)
    assert cli.main([*options, 'development-choices', item_id]) == 0
    assert len(requests) == 1
    assert requests[0].full_url == expected_url
    assert requests[0].get_method() == 'GET'
    assert requests[0].data is None
    captured = capsys.readouterr()
    assert captured.err == ''
    assert json.loads(captured.out) == payload
    assert captured.out == json.dumps(payload, ensure_ascii=False, indent=2) + '\n'


def test_development_choices_http_error(cli, monkeypatch, capsys):
    requests = []

    def response(request, **_):
        requests.append(request)
        raise HTTPError(request.full_url, 404, 'Not Found', {},
                        io.BytesIO('{"detail":"开发事项不存在"}'.encode()))

    monkeypatch.setattr(cli, 'urlopen', response)
    assert cli.main(['development-choices', 'missing-item']) == 1
    assert len(requests) == 1
    assert requests[0].full_url == 'http://127.0.0.1:8010/api/lifeweave/personal/items/missing-item/development/choices'
    assert requests[0].get_method() == 'GET'
    assert requests[0].data is None
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'LifeWeave HTTP 404' in captured.err
    assert '开发事项不存在' in captured.err


def test_work_plan_keeps_explicit_version_and_does_not_start_run(cli, monkeypatch, tmp_path, capsys):
    plan = {'version': 7, 'title': '研究方案', 'provider': 'research', 'nodes': [
        {'id': 'source', 'title': '核对原文', 'description': '', 'state': 'planned',
         'summary': '', 'dependsOn': [], 'outputIds': []}]}
    source = tmp_path / '计划.json'
    source.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    requests = []

    def response(request, **_):
        requests.append(request)
        return io.BytesIO(b'{"itemVersion":8}')

    monkeypatch.setattr(cli, 'urlopen', response)
    assert cli.main(['--workspace', 'team', 'work-plan', 'item-123', '--file', str(source)]) == 0
    assert len(requests) == 1
    assert requests[0].get_method() == 'PUT'
    assert requests[0].full_url.endswith('/team/items/item-123/work-plan')
    assert json.loads(requests[0].data) == plan
    assert json.loads(capsys.readouterr().out)['itemVersion'] == 8


def test_work_plan_conflict_does_not_retry_or_replace_version(cli, monkeypatch, tmp_path, capsys):
    source = tmp_path / 'plan.json'
    source.write_text('{"version":1,"title":"旧方案","provider":"manual","nodes":[]}', encoding='utf-8')
    calls = []

    def response(request, **_):
        calls.append(request)
        raise HTTPError(request.full_url, 409, 'Conflict', {}, io.BytesIO(b'{"detail":"stale version"}'))

    monkeypatch.setattr(cli, 'urlopen', response)
    assert cli.main(['work-plan', 'item-123', '--file', str(source)]) == 1
    assert len(calls) == 1
    assert '409' in capsys.readouterr().err


def test_work_view_is_read_only(cli, monkeypatch, capsys):
    calls = []

    def response(request, **_):
        calls.append(request)
        return io.BytesIO(b'{"itemVersion":1,"plan":{"nodes":[]}}')

    monkeypatch.setattr(cli, 'urlopen', response)
    assert cli.main(['work-view', 'item-123']) == 0
    assert len(calls) == 1 and calls[0].get_method() == 'GET'
    assert calls[0].full_url.endswith('/items/item-123/work-view')
    assert json.loads(capsys.readouterr().out)['plan']['nodes'] == []


@pytest.mark.parametrize('content', ['[]', '{"version":true}', '{"title":"未固定版本"}', '{invalid'])
def test_invalid_local_work_plan_never_sends(cli, monkeypatch, tmp_path, content):
    source = tmp_path / 'plan.json'
    source.write_text(content, encoding='utf-8')
    monkeypatch.setattr(cli, 'urlopen', lambda *_args, **_kwargs: pytest.fail('must not send invalid input'))
    with pytest.raises(SystemExit):
        cli.main(['work-plan', 'item-123', '--file', str(source)])

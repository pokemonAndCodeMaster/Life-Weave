"""Public command contracts independent of an Agent's session memory."""
import importlib.util
import io
import json
from pathlib import Path


def test_runs_without_item_filter_reads_every_page(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('lifeweave_client', Path(__file__).parents[1] / 'scripts/lifeweave.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    urls = []

    def response(request, **_):
        urls.append(request.full_url)
        return io.BytesIO(json.dumps({'items': [{'id': str(len(urls))}], 'total': 2}).encode())

    monkeypatch.setattr(module, 'urlopen', response)
    assert module.main(['runs']) == 0
    assert json.loads(capsys.readouterr().out) == {'items': [{'id': '1'}, {'id': '2'}], 'total': 2}
    assert 'offset=0' in urls[0] and 'offset=1' in urls[1]
    assert all('itemId' not in url for url in urls)

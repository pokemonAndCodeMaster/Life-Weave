from pathlib import Path
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.lifeweave_knowledge.library import Library
from src.lifeweave_knowledge.library_router import router
from src.lifeweave_knowledge.document_assets import MAX_ASSET_BYTES

PNG = b'\x89PNG\r\n\x1a\n' + b'fixture'

@pytest.fixture
def library(tmp_path):
    (tmp_path/'docs').mkdir()
    (tmp_path/'docs/current-sources.json').write_text(json.dumps({'id':'project','title':'项目','paths':['docs/guide.md']}))
    (tmp_path/'docs/guide.md').write_text('# 文档\n\n![图](<images/图 one.png>)\n![上级](../shared.png)\n![引用图][img]\n\n[img]: images/100%25.png\n\n```md\n![例](unregistered.png)\n```')
    (tmp_path/'docs/images').mkdir()
    (tmp_path/'docs/images/图 one.png').write_bytes(PNG)
    (tmp_path/'docs/images/100%.png').write_bytes(PNG)
    (tmp_path/'shared.png').write_bytes(PNG)
    return Library(SimpleNamespace(fetch_all=lambda *args: []), {'personal':tmp_path/'personal','team':tmp_path/'team'}, tmp_path)


def test_allowed_document_relative_images_are_versioned_and_keep_scope(library):
    app=FastAPI();app.include_router(router);app.state.library=library
    with TestClient(app) as client:
        document=client.get('/api/lifeweave/personal/library/document',params={'sourceId':'project','path':'docs/guide.md'}).json()
        refs=document['references']['images']
        assert set(refs)=={'images/图 one.png','../shared.png','images/100%.png'}
        for reference,url in refs.items():
            parsed=parse_qs(urlsplit(url).query)
            assert parsed['version']==[document['version']]
            assert parsed['documentPath']==['docs/guide.md']
            assert parsed['path']==[reference]
            response=client.get(url)
            assert response.status_code==200
            assert response.content==PNG
            assert response.headers['x-content-type-options']=='nosniff'
        # A project image is not a newly allowed Markdown document.
        assert client.get('/api/lifeweave/personal/library/document',params={'sourceId':'project','path':'docs/other.md'}).status_code==409
        (library.project_root/'docs/guide.md').write_text('# 已变化')
        assert client.get(next(iter(refs.values()))).status_code==409


def asset(library, reference, content=None):
    path=library.project_root/'docs/guide.md'
    if content is not None:path.write_text(content)
    doc=library.document('personal','project','docs/guide.md')
    return library.asset('personal','project','docs/guide.md',doc['version'],reference)


def test_unreferenced_traversal_and_symlink_are_not_media(library,tmp_path):
    with pytest.raises(ValueError,match='未被'):asset(library,'shared.png')
    for ref in ['../../secret.png','../.runtime/secret.png','/etc/passwd','https://external.test/a.png']:
        with pytest.raises(ValueError):asset(library,ref,f'# 文档\n![图]({ref})')
    (tmp_path/'docs/images/out.png').symlink_to('/etc/passwd')
    with pytest.raises(ValueError,match='符号链接'):asset(library,'images/out.png','# 文档\n![图](images/out.png)')
    (tmp_path/'docs/images/inside.png').symlink_to(tmp_path/'shared.png')
    with pytest.raises(ValueError,match='符号链接'):asset(library,'images/inside.png','# 文档\n![图](images/inside.png)')


def test_source_media_does_not_override_imported_run_identity(library):
    library.reference_provider=lambda *args:{'images':{'images/图 one.png':'/api/lifeweave/personal/runs/old/assets?path=original.png'},'links':{},'warnings':[]}
    doc=library.document('personal','project','docs/guide.md')
    assert '/runs/old/' in doc['references']['images']['images/图 one.png']
    with pytest.raises(ValueError,match='其他已登记来源'):asset(library,'images/图 one.png')


def test_missing_invalid_svg_and_asset_size_boundary(library,tmp_path):
    with pytest.raises(KeyError):asset(library,'images/missing.png','# 文档\n![图](images/missing.png)')
    file=tmp_path/'docs/images/large.png';file.write_bytes(PNG+b'x'*(MAX_ASSET_BYTES-len(PNG)))
    assert len(asset(library,'images/large.png','# 文档\n![图](images/large.png)')[0])==MAX_ASSET_BYTES
    with file.open('ab') as handle:handle.write(b'x')
    with pytest.raises(ValueError,match='10 MB'):asset(library,'images/large.png')
    svg=tmp_path/'docs/images/a.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')
    assert asset(library,'images/a.svg','# 文档\n![图](images/a.svg)')[1]=='image/svg+xml'
    for body in ['<svg><script>alert(1)</script></svg>','<svg><use href="https://remote.test/a.svg"/></svg>','<svg onload="alert(1)"/>']:
        svg.write_text(body)
        with pytest.raises(ValueError):asset(library,'images/a.svg')

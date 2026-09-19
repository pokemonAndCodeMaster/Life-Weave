import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_research_outputs import output_client, completed_run, PNG
from test_live_database import client, post
from src.lifeweave.research_archive import ResearchArchive, ArchiveSettings
from src.lifeweave.research_bundle import build_bundle, rewrite_markdown, MAX_FILES


def specimen(c):
    item=post(c,'/items',{'itemType':'research','title':'可携带研究'})['id']
    body='# 原正文\n\n![图](<research/a b.png>)\n\n[证据][src]\n\n[src]: research/source.md\n\n|符号|值|\n|---|---|\n|$x$|2|\n\n```md\n![代码示例](private.png)\n```\n'
    run=completed_run(c,item,body)
    root=c.app.state.research_outputs.root/'.runtime/executions/personal'/run['id']/'repo'
    (root/'research').mkdir(parents=True)
    (root/'research/a b.png').write_bytes(PNG)
    (root/'research/source.md').write_text('# 证据\n\n[下一层](nested.txt)')
    (root/'research/nested.txt').write_text('真的嵌套材料')
    (root/'.env').write_text('NOT_IN_ARCHIVE')
    return item,run,root,body


def test_portable_zip_contains_images_nested_sources_and_preserves_original(output_client):
    c=output_client;item,run,root,body=specimen(c)
    response=c.get(f'/api/lifeweave/personal/runs/{run["id"]}/research-output/bundle')
    assert response.status_code==200,response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        assert z.read('original.md').decode()==body
        m=json.loads(z.read('manifest.json'))
        assert not m['warnings'] and len(m['files'])==3
        image=next(f for f in m['files'] if f['mime']=='image/png')
        assert z.read(image['file'])==PNG
        assert image['file'] in z.read('report.md').decode()
        source=next(f for f in m['files'] if f['path'].endswith('source.md'))
        nested=next(f for f in m['files'] if f['path'].endswith('nested.txt'))
        assert '../'+nested['file'] in z.read(source['file']).decode()
        assert z.read(nested['file']).decode()=='真的嵌套材料'
        assert '$x$' in z.read('report.md').decode() and 'private.png' in z.read('report.md').decode()
        assert all('NOT_IN_ARCHIVE' not in z.read(p).decode(errors='ignore') for p in z.namelist())
    assert c.get(f'/api/lifeweave/team/runs/{run["id"]}/research-output/bundle').status_code==404
    (root/'research/a b.png').unlink()
    (root/'research/a b.png').symlink_to(root/'.env')
    assert c.get(f'/api/lifeweave/personal/runs/{run["id"]}/research-output/bundle').status_code==409


def test_bundle_limit_and_missing_reference_are_not_silent(output_client):
    c=output_client
    item=post(c,'/items',{'itemType':'research','title':'材料上限'})['id']
    body='\n'.join(f'[材料{i}](research/{i}.txt)' for i in range(MAX_FILES))
    run=completed_run(c,item,body)
    root=c.app.state.research_outputs.root/'.runtime/executions/personal'/run['id']/'repo/research';root.mkdir(parents=True)
    for i in range(MAX_FILES+1):(root/f'{i}.txt').write_text(str(i))
    files,m,_=build_bundle(c.app.state.research_outputs,'personal',run['id'])
    assert len(m['files'])==128
    db=c.app.state.database_manager.postgres()
    db.execute('UPDATE workbench.t_lifeweave_run SET result=%s WHERE id=%s',(body+'\n[多一个](research/128.txt)',run['id']))
    with pytest.raises(ValueError,match='完整包'):build_bundle(c.app.state.research_outputs,'personal',run['id'])
    db.execute('UPDATE workbench.t_lifeweave_run SET result=%s WHERE id=%s',('[missing](research/missing.md)',run['id']))
    assert build_bundle(c.app.state.research_outputs,'personal',run['id'])[1]['warnings']


def test_archive_targets_retry_independently_and_preserve_remote_changes(output_client,tmp_path,monkeypatch):
    c=output_client;_,run,root,_=specimen(c)
    service=ResearchArchive(tmp_path,c.app.state.research_outputs,None)
    service.configure('personal',ArchiveSettings(enabled=True,githubRepository='https://github.com/test/repo',linearProjectId='project'))
    calls=[]
    def github(*args):calls.append('github');return {'url':'https://github.com/test/repo/snapshot','commit':'abc'}
    def failed(*args):calls.append('linear');raise ValueError('远端暂时失败')
    monkeypatch.setattr(service,'github',github);monkeypatch.setattr(service,'publish_linear',failed)
    first=service.archive('personal',run['id'])
    assert first['github']['status']=='confirmed' and first['linear']['status']=='failed'
    monkeypatch.setattr(service,'publish_linear',lambda *args: {'url':'https://linear.app/document/version'})
    second=service.archive('personal',run['id'])
    assert second['linear']['status']=='confirmed' and calls.count('github')==1
    service.archive('personal',run['id']);assert calls.count('github')==1
    (root/'research/nested.txt').write_text('引用已变化')
    with pytest.raises(ValueError,match='旧版'):service.archive('personal',run['id'])


def test_worker_automatically_archives_success_and_skips_failed_runs(output_client,tmp_path,monkeypatch):
    c=output_client;_,run,_,_=specimen(c)
    service=ResearchArchive(tmp_path,c.app.state.research_outputs,None)
    settings=service.configure('personal',ArchiveSettings(enabled=True))
    settings['since']='2000-01-01T00:00:00+00:00';service.save(service.folder/'personal/settings.json',settings)
    seen=[]
    monkeypatch.setattr(service,'archive',lambda workspace,rid:seen.append(rid))
    service.tick()
    assert run['id'] in seen
    assert all(c.app.state.lifeweave_runtime_service.get_run_snapshot('personal',r)['state']=='succeeded' for r in seen)


def test_markdown_rewriting_only_changes_actual_links():
    text='[link][x]\n\n[x]: a.png\n\n```md\n[not link](a.png)\n```\n\n$$\nx^2\n$$\n'
    changed=rewrite_markdown(text,lambda u,i:'new.png')
    assert '[link](new.png)' in changed and '[not link](a.png)' in changed and '$$\nx^2\n$$' in changed


def test_linear_readback_preserves_semantics_and_detects_lost_content():
    from src.lifeweave.research_archive import document_content
    submitted='|A|B|\n|---|---|\n|1|2|\n\n$x+\\theta$ [证据](https://example.com/a)\n\n![图](https://example.com/p.png)\n'
    normalized='|A|B|\n|--|--|\n|1|2|\n\n$x+\\\\theta$ [证据](<https://example.com/a>)\n\n![图](https://example.com/p.png)\n'
    assert document_content(submitted)==document_content(normalized)
    for altered in [normalized.replace('|1|2|','|1|3|'),normalized.replace('p.png','q.png'),normalized.replace('theta','alpha'),normalized.replace('证据','另一项')]:
        assert document_content(submitted)!=document_content(altered)


def test_linear_create_recovers_same_document_without_duplicate(tmp_path,monkeypatch):
    from uuid import UUID
    from src.lifeweave.research_archive import digest
    documents={};creates=[]
    class Linear:
        def query(self,query,variables):
            if 'documentCreate' in query:
                value=variables['input'];assert UUID(value['id']).version==4
                creates.append(value['id']);documents[value['id']]={**value,'url':'https://linear.app/document/test'}
                return {'documentCreate':{'success':True,'document':{'id':value['id']}}}
            return {'documents':{'nodes':[documents[variables['id']]] if variables['id'] in documents else []}}
    service=ResearchArchive(tmp_path,None,Linear());monkeypatch.setattr(service,'upload',lambda *args:'https://uploads.linear.app/test')
    files={'report.md':b'# Report\n\nData: 2\n'};manifest={'workspace':'personal','runId':'run','version':'123','title':'Paper','files':[]}
    state={'linear':{}};path=tmp_path/'state.json'
    a=service.publish_linear(files,b'zip',manifest,'project',state,path)
    b=service.publish_linear(files,b'zip',manifest,'project',state,path)
    assert a==b and len(creates)==1
    documents[creates[0]]['content']+='\nHuman edit\n'
    with pytest.raises(ValueError,match='不一致'):
        service.publish_linear(files,b'zip',manifest,'project',state,path)


def test_linear_math_projection_keeps_equations_out_of_markdown_headings():
    import mistune
    formula='\\begin{pmatrix}x\\\\y\\end{pmatrix}\n=\n\\frac1{2}\n-\na'
    source='Inline $x_i+\\theta$\n\n$$\n'+formula+'\n$$\n'
    rendered=rewrite_markdown(source,lambda url,image:url,math_as_code=True)
    tokens=mistune.create_markdown(renderer='ast')(rendered)
    assert tokens[-1]['type']=='block_code' and tokens[-1]['raw'].strip()==formula
    assert tokens[0]['children'][-1]=={'type':'codespan','raw':'x_i+\\theta'}

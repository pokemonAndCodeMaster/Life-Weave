"""Read run/manual outputs and propose traceable, explicitly reviewed knowledge."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field

from src.lifeweave.models import WireModel, WorkspaceKey
from src.lifeweave_knowledge.library import fingerprint
from src.lifeweave_runtime.storage_text import result_text_storage
from .research_references import references, merge_references
from .research_bundle import build_bundle


class ResearchOutputs:
    def __init__(self, work, runtime, library, root: Path):
        self.work, self.runtime, self.library = work, runtime, library
        self.root = Path(root)

    @staticmethod
    def _content(run):
        payload = run.get('result_payload') or {}
        if isinstance(payload.get('report'), str):
            return payload['report']
        result = str(run.get('result') or '')
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                for key in ('report', 'content'):
                    if isinstance(data.get(key), str):
                        return data[key]
        except (ValueError, TypeError):
            pass
        return result

    def read(self, workspace: str, item_id: str):
        item = self.work.get_item(workspace, item_id)
        versions = []
        offset = 0
        while True:
            runs, total = self.runtime.list_runs(workspace, item_id=item_id, limit=100, offset=offset)
            for run in runs:
                content = self._content(run)
                if not content.strip():
                    continue
                base = f'/api/lifeweave/{workspace}/runs/{quote(run["id"], safe="")}'
                storage_note = result_text_storage(run)[1]
                versions.append({'id':run['id'], 'kind':'run', 'title':item['title'],
                    'content':content, 'version':fingerprint(content), 'runId':run['id'],
                    'state':run['state'], 'createdAt':run.get('finished_at') or run['created_at'],
                    'sourceBase':base+'/source', 'assetBase':base+'/assets',
                    'downloadUrl':base+'/research-output/download',
                    'bundleUrl':base+'/research-output/bundle',
                    'storageNote':storage_note,
                    'rawDownloadUrl':base+'/artifacts/result' if storage_note and run.get('result') is not None else None})
            offset += len(runs)
            if offset >= total:
                break
            if not runs:
                raise ValueError('运行列表在读取时变化，请重新读取成果')
        for relation in self.work.repository.list_relations(workspace, item_id):
            if (relation['fromKind'], relation['fromId'], relation['toKind'], relation['relationType']) != ('item', item_id, 'entity', 'produces'):
                continue
            entity = self.work.repository.get_entity(workspace, relation['toId'])
            if not entity or entity.get('entityType') != 'artifact':
                continue
            content = str(entity.get('payload', {}).get('body') or '')
            if content.strip():
                versions.append({'id':entity['id'], 'kind':'manual', 'title':entity['title'],
                    'content':content, 'version':fingerprint(content), 'runId':None, 'state':'manual',
                    'createdAt':entity['updatedAt'], 'sourceBase':None, 'assetBase':None, 'downloadUrl':None})
        versions.sort(key=lambda output:str(output['createdAt']), reverse=True)
        current = next((out for out in versions if out['kind'] == 'run' and out['state'] == 'succeeded'), None)
        if current is None:
            current = next((out for out in versions if out['kind'] == 'manual'), None)
        return {'current':current, 'versions':versions}

    def _run(self, workspace, item_id, run_id):
        self.work.get_item(workspace, item_id)
        run = self.runtime.get_run_snapshot(workspace, run_id)
        if run['item_id'] != item_id:
            raise ValueError('此轮成果不属于当前事项')
        if run['state'] != 'succeeded' or not self._content(run).strip():
            raise ValueError('请先取得成功运行的成果，再提出知识修订')
        return run

    def _candidate(self, row):
        return {**row, 'itemId':row['item_id'], 'runId':row['run_id'], 'runVersion':row['run_version'],
                'references':self.document_references(row['workspace'],row['source_id'],row['path'],row['content']),
                'sourceUrl':f'/api/lifeweave/{row["workspace"]}/runs/{row["run_id"]}/research-output/download'}

    def document_references(self, workspace, source_id, path, content):
        if source_id!='local' or '/research-output/download' not in content:
            return {'links':{},'images':{},'warnings':[]}
        rows = self.library.db.fetch_all('''SELECT c.run_id,c.run_version FROM workbench.research_knowledge_candidate c
            JOIN workbench.document_revision r ON r.id=c.revision_id
            WHERE c.workspace=%s AND r.source_id=%s AND r.path=%s AND r.status IN ('accepted','draft')''',
            (workspace,source_id,path))
        groups=[]
        for row in rows:
            source=f'/api/lifeweave/{workspace}/runs/{row["run_id"]}/research-output/download'
            if source not in content:
                continue
            run=self.runtime.get_run_snapshot(workspace,row['run_id'])
            original=self._content(run)
            if fingerprint(original)==row['run_version']:
                mapping=references(original,workspace,row['run_id'])
                storage_note=result_text_storage(run)[1]
                if storage_note:
                    mapping['warnings'].append(storage_note)
                groups.append(mapping)
        return merge_references(groups)

    def candidates(self, workspace, item_id):
        self.work.get_item(workspace, item_id)
        rows = self.library.db.fetch_all('''SELECT r.*, c.item_id,c.run_id,c.run_version
            FROM workbench.research_knowledge_candidate c JOIN workbench.document_revision r ON r.id=c.revision_id
            WHERE c.workspace=%s AND c.item_id=%s ORDER BY c.created_at DESC''', (workspace,item_id))
        return [self._candidate(self.library.with_diff(row)) for row in rows]

    def propose_from_run(self, workspace, item_id, run_id, path, content, base_version, reason, request_id):
        if not all(isinstance(value, str) and value.strip() for value in (path,content,base_version,reason,request_id)):
            raise ValueError('知识正文、路径、版本、说明和请求标识不能为空')
        if len(content)>1_000_000 or len(path)>1000 or len(reason)>2000 or len(request_id)>128:
            raise ValueError('知识修订内容超出允许长度')
        run = self._run(workspace,item_id,run_id)
        run_version = fingerprint(self._content(run))
        request_hash = fingerprint(json.dumps([run_id,path,content,base_version,reason],ensure_ascii=False))
        source_url = f'/api/lifeweave/{workspace}/runs/{run_id}/research-output/download'
        provenance = f'\n\n---\n来源：[研究成果]({source_url}) · 事项 `{item_id}` · 运行 `{run_id}` · 版本 `{run_version}`\n'
        if len((content+provenance).encode('utf-8')) > 2_000_000:
            raise ValueError('知识正文和来源超过 2 MB，请拆分后提出修订')
        # The review and its origin share a transaction, so a retried request cannot
        # leave a duplicate review if the process dies between the two inserts.
        with self.library.db.transaction() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('research-'+workspace+'-'+item_id+'-'+request_id,))
            existing = conn.execute('''SELECT r.*,c.item_id,c.run_id,c.run_version,c.request_fingerprint
                FROM workbench.research_knowledge_candidate c JOIN workbench.document_revision r ON r.id=c.revision_id
                WHERE c.workspace=%s AND c.item_id=%s AND c.request_id=%s''', (workspace,item_id,request_id)).fetchone()
            if existing:
                if existing['request_fingerprint'] != request_hash:
                    raise ValueError('请求标识已经用于另一份知识修订，请刷新后重试')
                existing.pop('request_fingerprint')
                return self._candidate(self.library.with_diff(existing))
            revision = self.library.propose(workspace,'local',path,content+provenance,base_version,reason,connection=conn)
            conn.execute('''INSERT INTO workbench.research_knowledge_candidate
                (revision_id,workspace,item_id,run_id,run_version,request_id,request_fingerprint)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''', (revision['id'],workspace,item_id,run_id,run_version,request_id,request_hash))
        return self._candidate({**revision,'item_id':item_id,'run_id':run_id,'run_version':run_version})

    def asset(self, workspace, run_id, path):
        run = self.runtime.get_run_snapshot(workspace, run_id)
        if run['state'] not in {'succeeded','failed','cancelled','paused'}:
            raise KeyError('运行结束后才能读取图片')
        relative = Path(path)
        if not path or relative.is_absolute() or any(part in {'..','node_modules','__pycache__'} or part.startswith('.') for part in relative.parts):
            raise ValueError('图片必须来自本轮工作目录')
        folder = relative.parts[0] if relative.parts[0] in {'repo','artifacts'} else 'repo'
        relative = Path(*relative.parts[1:]) if relative.parts[0] in {'repo','artifacts'} else relative
        # Only these two owned folders are addressable, never home/auth or the
        # worker supplied actualDirectory (which can point outside the run).
        executions = (self.root/'.runtime/executions').resolve()
        run_root = executions/workspace/run_id
        root = run_root/folder
        if not root.resolve().is_relative_to(run_root):
            raise ValueError('图片目录越界')
        target = (root/relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('图片路径越界')
        if not target.is_file():
            raise KeyError('本机没有此图片，可能未生成或位于远端节点')
        if target.stat().st_size > 10_000_000:
            raise ValueError('图片超过 10 MB')
        data = target.read_bytes()
        mime = None
        if data.startswith(b'\x89PNG\r\n\x1a\n'): mime = 'image/png'
        elif data.startswith(b'\xff\xd8\xff'): mime = 'image/jpeg'
        elif data[:6] in {b'GIF87a',b'GIF89a'}: mime = 'image/gif'
        elif data.startswith(b'RIFF') and data[8:12] == b'WEBP': mime = 'image/webp'
        if mime is None:
            raise ValueError('文件不是支持的 PNG、JPEG、GIF 或 WebP 图片')
        return data, mime


router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['research-outputs'])


class CandidateCreate(WireModel):
    run_id: str = Field(alias='runId', min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(min_length=1, max_length=1_000_000)
    base_version: str = Field(alias='baseVersion', min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(alias='requestId', min_length=1, max_length=128)


def _call(request, method, *args, **kwargs):
    try:
        return getattr(request.app.state.research_outputs,method)(*args,**kwargs)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,OSError,UnicodeError) as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get('/items/{item_id}/research-output')
def read(request: Request, workspace: WorkspaceKey, item_id: str):
    return _call(request,'read',workspace,item_id)


@router.get('/research-catalog')
def catalog(request: Request, workspace: WorkspaceKey):
    service=request.app.state.research_outputs
    items,_=service.work.list_items(workspace,limit=None)
    results=[]
    for item in items:
        current=service.read(workspace,item['id'])['current']
        if current:
            results.append({k:current[k] for k in ('title','runId','version','createdAt')} | {'itemId':item['id']})
    return {'items':results}


@router.get('/items/{item_id}/knowledge-candidates')
def candidates(request: Request, workspace: WorkspaceKey, item_id: str):
    return _call(request,'candidates',workspace,item_id)


@router.post('/items/{item_id}/knowledge-candidates', status_code=201)
def propose(request: Request, workspace: WorkspaceKey, item_id: str, body: CandidateCreate):
    return _call(request,'propose_from_run',workspace,item_id,**body.model_dump())


@router.get('/runs/{run_id}/assets')
def asset(request: Request, workspace: WorkspaceKey, run_id: str, path: str):
    data, mime = _call(request,'asset',workspace,run_id,path)
    return Response(data, media_type=mime, headers={'X-Content-Type-Options':'nosniff', 'Cache-Control':'private, no-cache'})


@router.get('/runs/{run_id}/research-output/download')
def download(request: Request, workspace: WorkspaceKey, run_id: str):
    service = request.app.state.research_outputs
    try:
        run = service.runtime.get_run_snapshot(workspace,run_id)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    content = service._content(run)
    if not content.strip():
        raise HTTPException(404,'本轮还没有成果正文')
    return Response(content,media_type='text/markdown; charset=utf-8',headers={
        'X-Content-Type-Options':'nosniff','Content-Disposition':'attachment; filename="research-output.md"',
        'ETag':'"'+fingerprint(content)+'"'})


@router.get('/runs/{run_id}/research-output/bundle')
def bundle(request: Request, workspace: WorkspaceKey, run_id: str):
    try:
        _, manifest, data = build_bundle(request.app.state.research_outputs, workspace, run_id)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,OSError) as exc:
        raise HTTPException(409,str(exc)) from exc
    return Response(data, media_type='application/zip', headers={
        'Content-Disposition':f'attachment; filename="research-{run_id}.zip"',
        'ETag':'"'+manifest['version']+'"', 'X-Content-Type-Options':'nosniff'})

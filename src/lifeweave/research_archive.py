"""Opt-in, durable per-version archive delivery. Each destination confirms independently."""
import asyncio
import fcntl
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
import mistune
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .models import WorkspaceKey
from .research_bundle import build_bundle, rewrite_markdown


def digest(data):
    return hashlib.sha256(data).hexdigest()


def document_content(content):
    """Compare full Markdown structure after harmless serializer normalization.

    Linear escapes literal math as ordinary Markdown text; parsing without a
    math extension decodes those escapes on both sides without changing TeX.
    Keep text, code, links, images, tables, heading levels and list ordering.
    """
    def normalize(value):
        if isinstance(value,list):
            result=[]
            for token in value:
                if token['type']=='blank_line':
                    continue
                if token['type'] in {'strong','emphasis'}:
                    # Linear moves emphasis around inline code. It is presentation;
                    # retain the ordered children, including code and every character.
                    for child in normalize(token['children']):
                        if child['type']=='text' and result and result[-1]['type']=='text':
                            result[-1]['raw']+=child['raw']
                        else:
                            result.append(child)
                    continue
                token=normalize(token)
                if token['type']=='text' and result and result[-1]['type']=='text':
                    result[-1]['raw']+=token['raw']
                else:
                    result.append(token)
            return result
        if isinstance(value,dict):
            return {key:normalize(part) for key,part in value.items()
                    if key not in {'position','bullet','tight','style','align'}}
        return value
    return normalize(mistune.create_markdown(renderer='ast',plugins=['table','strikethrough'])(content))


class ArchiveSettings(BaseModel):
    enabled: bool = False
    githubRepository: str = Field(default='', max_length=300)
    linearProjectId: str = Field(default='', max_length=64)


class ResearchArchive:
    def __init__(self, root, outputs, linear, notion=None):
        self.root, self.outputs, self.linear = Path(root), outputs, linear
        self.notion = notion
        self.folder = self.root/'.runtime/research-archives'
        self.task = None
        self.stopping = False
        self.wakeup = asyncio.Event()

    @contextmanager
    def locked(self, workspace):
        folder = self.folder/workspace
        folder.mkdir(parents=True, exist_ok=True)
        with (folder/'lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield folder
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    @staticmethod
    def load(path, default):
        return json.loads(path.read_text()) if path.exists() else default

    @staticmethod
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2))
        temp.chmod(0o600)
        temp.replace(path)

    def settings(self, workspace):
        return self.load(self.folder/workspace/'settings.json', {**ArchiveSettings().model_dump(), 'since':None})

    def configure(self, workspace, settings):
        value = settings.model_dump()
        repo = value['githubRepository'].removesuffix('.git').rstrip('/')
        if repo and not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('请输入 GitHub 仓库的 HTTPS 地址，不在地址中包含凭证')
        value['githubRepository'] = repo
        with self.locked(workspace) as folder:
            old = self.settings(workspace)
            value['since'] = old.get('since') or datetime.now(timezone.utc).isoformat()
            self.save(folder/'settings.json', value)
        return value

    def status(self, workspace, run_id):
        self.outputs.runtime.get_run_snapshot(workspace,run_id)
        return self.load(self.folder/workspace/run_id/'state.json', {
            'runId':run_id, 'local':{'status':'pending'}, 'github':{'status':'pending'},
            'notion':{'status':'unconfigured'}, 'linear':{'status':'historical_read_only'}})

    def archive(self, workspace, run_id):
        # One process/worker owns transitions and git checkout at a time, including retries.
        with self.locked(workspace) as folder:
            settings = self.settings(workspace)
            run = self.outputs.runtime.get_run_snapshot(workspace,run_id)
            destination = folder/run_id
            state_file = destination/'state.json'
            state = self.status(workspace,run_id)
            try:
                files, manifest, zipped = build_bundle(self.outputs,workspace,run_id)
            except (ValueError,OSError) as exc:
                state['local']={'status':'failed','error':str(exc)[:500]}
                state['retryAfter']=time.time()+300
                self.save(state_file,state)
                raise
            if state.get('version') and state['version'] != manifest['version']:
                raise ValueError('运行正文已变化，不能覆盖已经固定的归档')
            state.update(runId=run_id, itemId=run['item_id'], version=manifest['version'],
                         updatedAt=datetime.now(timezone.utc).isoformat())
            bundle_dir = destination/'bundle'
            for name,data in {**files,'research.zip':zipped}.items():
                path = bundle_dir/name
                path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists() and path.read_bytes() != data:
                    raise ValueError('已归档的引用材料发生变化，保留旧版并停止覆盖')
                path.write_bytes(data)
            state['local'] = {'status':'confirmed','path':str(bundle_dir.relative_to(self.root)),
                              'zipSha256':digest(zipped),'warnings':manifest['warnings']}
            self.save(state_file,state)
            if state.get('linear', {}).get('status') != 'confirmed':
                state['linear'] = {'status': 'historical_read_only', 'error': 'Linear 已转为历史只读；新版本不再归档到 Linear'}
                self.save(state_file, state)
            for target, configured in [('github',settings['githubRepository'])]:
                previous = state.get(target,{})
                if previous.get('status') == 'confirmed' and previous.get('target') == configured:
                    continue
                if not configured:
                    state[target] = {'status':'unconfigured','error':'尚未配置归档目标'}
                    self.save(state_file,state)
                    continue
                if previous.get('target') != configured:
                    previous = {}
                state[target] = {**previous,'status':'sending','target':configured}
                self.save(state_file,state)
                try:
                    result = self.github(folder,bundle_dir,manifest,configured)
                    state[target] = {**state[target],**result,'status':'confirmed',
                                     'confirmedAt':datetime.now(timezone.utc).isoformat()}
                    state[target].pop('error',None)
                except Exception as exc:
                    # Never expose command stderr, tokens, signed URLs or HTTP request headers.
                    state[target]['status'] = 'failed'
                    state[target]['error'] = str(exc)[:500] if isinstance(exc,ValueError) else '归档传输失败；本地成果保留，可重试'
                self.save(state_file,state)
            if self.notion and self.notion.settings(workspace)['enabled']:
                previous = state.get('notion', {})
                try:
                    if state.get('github', {}).get('status') != 'confirmed':
                        raise ValueError('GitHub 正文尚未归档，Notion 镜像等待可访问的原文地址')
                    # sync_report re-reads even an unchanged source version, so a
                    # human edit or deleted page cannot remain silently confirmed.
                    state['notion'] = self.notion.sync_report(
                        workspace, manifest, files['report.md'].decode(), state['github']['url'])
                except Exception as exc:
                    message = str(exc)[:500] if isinstance(exc, ValueError) else 'Notion 镜像失败；本地与 GitHub 成果保留'
                    state['notion'] = {**previous, 'status': 'failed', 'error': message}
                    self.notion.record_failure(workspace, f'research:{run_id}', manifest['version'], message)
                self.save(state_file, state)
            elif self.notion:
                state['notion'] = {'status': 'unconfigured'}
                self.save(state_file, state)
            state['retryAfter'] = time.time()+300
            self.save(state_file,state)
            return state

    @staticmethod
    def git(folder, *args, check=True):
        result = subprocess.run(['git',*args],cwd=folder,env={**os.environ,'GIT_TERMINAL_PROMPT':'0',
            'GIT_SSH_COMMAND':'ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes'},
            capture_output=True,text=True,timeout=90)
        if check and result.returncode:
            raise ValueError('GitHub 归档未确认：请检查 Git SSH 认证、远端分支冲突和网络后重试')
        return result

    def github(self, folder, bundle_dir, manifest, repository):
        git_dir = folder/'git'
        git_dir.mkdir(exist_ok=True)
        remote = 'git@github.com:'+repository.removeprefix('https://github.com/')+'.git'
        if not (git_dir/'.git').exists():
            self.git(git_dir,'init','-b','research-archive')
            self.git(git_dir,'config','user.name','LifeWeave Archive')
            self.git(git_dir,'config','user.email','archive@lifeweave.local')
            self.git(git_dir,'remote','add','origin',remote)
        elif self.git(git_dir,'remote','get-url','origin').stdout.strip() != remote:
            raise ValueError('更换仓库需先迁移本地归档 checkout，未向旧仓库写入')
        refs = self.git(git_dir,'ls-remote','origin','refs/heads/research-archive').stdout.strip()
        if refs:
            self.git(git_dir,'fetch','origin','research-archive')
            head = self.git(git_dir,'rev-parse','--verify','HEAD',check=False)
            if head.returncode:
                self.git(git_dir,'checkout','-B','research-archive','FETCH_HEAD')
            else:
                self.git(git_dir,'merge','--ff-only','FETCH_HEAD')
        relative = Path('research')/manifest['workspace']/manifest['itemId']/manifest['runId']
        for path in bundle_dir.rglob('*'):
            if path.is_file():
                dest = git_dir/relative/path.relative_to(bundle_dir)
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists() and dest.read_bytes() != path.read_bytes():
                    raise ValueError('GitHub 中的同一归档已被修改，未覆盖远端内容')
                dest.write_bytes(path.read_bytes())
        # Rebuild a browsable index from immutable manifests, including prior versions.
        entries=[]
        for path in sorted((git_dir/'research').rglob('manifest.json')):
            data=json.loads(path.read_text())
            link=(path.parent/'report.md').relative_to(git_dir).as_posix()
            entries.append(f'- [{data["title"].replace("[","(").replace("]",")")}]({link}) · `{data["runId"]}`')
        (git_dir/'README.md').write_text('# LifeWeave 研究归档\n\n成功运行的版本快照；不是已采纳的正式知识。\n\n'+'\n'.join(entries)+'\n')
        self.git(git_dir,'add','--',str(relative),'README.md')
        if self.git(git_dir,'diff','--cached','--quiet',check=False).returncode:
            self.git(git_dir,'commit','-m','Archive '+manifest['runId'])
        commit=self.git(git_dir,'rev-parse','HEAD').stdout.strip()
        self.git(git_dir,'push','origin','HEAD:refs/heads/research-archive')
        actual=self.git(git_dir,'ls-remote','origin','refs/heads/research-archive').stdout.split()[0]
        if actual != commit:
            raise ValueError('GitHub 分支回读不一致，请重试核对')
        return {'commit':commit,'url':repository+'/blob/'+commit+'/'+relative.as_posix()+'/report.md'}

    def upload(self, name, data, mime):
        result=self.linear.query('''mutation($type:String!,$name:String!,$size:Int!){
            fileUpload(contentType:$type,filename:$name,size:$size){success uploadFile{assetUrl uploadUrl headers{key value}}}}''',
            {'type':mime,'name':Path(name).name,'size':len(data)})['fileUpload']
        if not result['success']:
            raise ValueError('Linear 未接受附件上传')
        upload=result['uploadFile']
        headers={'Content-Type':mime,'Cache-Control':'public, max-age=31536000',
                 **{h['key']:h['value'] for h in upload['headers']}}
        with httpx.Client(timeout=60) as client:
            response=client.put(upload['uploadUrl'],headers=headers,content=data)
            if not response.is_success:
                raise ValueError('Linear 附件传输未成功')
            # File storage requires authentication; verify the bytes, not just PUT status.
            response=client.get(upload['assetUrl'],headers={'Authorization':self.linear.token()},follow_redirects=True)
            if not response.is_success or digest(response.content) != digest(data):
                raise ValueError('Linear 附件回读不一致')
        return upload['assetUrl']

    def publish_linear(self, files, zipped, manifest, project, state, state_file):
        record=state['linear']
        uploads=record.setdefault('uploads',{})
        for name,data in {**files,'research.zip':zipped}.items():
            key=digest(data)
            if key not in uploads:
                mime='application/zip' if name.endswith('.zip') else next((f['mime'] for f in manifest['files'] if f['file']==name),'text/plain')
                uploads[key]=self.upload(name,data,mime)
                self.save(state_file,state)
        # Inline only report references. The ZIP remains the complete portable source.
        content=rewrite_markdown(files['report.md'].decode(),lambda url,image: uploads[digest(files[url.split('#')[0]])] if url.split('#')[0] in files else url,math_as_code=True)
        # Linear accepts the UUIDv4 format. Derive stable bits so a lost create
        # response can be recovered without creating a duplicate document.
        identity='lifeweave:'+project+':'+manifest['workspace']+':'+manifest['runId']+':'+manifest['version']
        archive_id=str(UUID(hex=digest(identity.encode())[:32],version=4))
        header=(f'研究归档 · `{manifest["runId"]}` · 正文版本 `{manifest["version"]}`\n\n'
                f'[下载正文与图片 ZIP]({uploads[digest(zipped)]})\n\n研究成果快照，尚未作为正式知识采纳。公式在此以 LaTeX 原文显示，完整 Markdown 在 ZIP 中。\n\n---\n\n')
        body=header+content
        record['documentId']=archive_id
        record['submittedBodyHash']=digest(body.encode())
        self.save(state_file,state)
        def read_document():
            data=self.linear.query('query($id:ID!){documents(filter:{id:{eq:$id}}){nodes{id title content url}}}',{'id':archive_id})
            return next(iter(data['documents']['nodes']),None)
        current=read_document()
        if current is None:
            created=self.linear.query('''mutation($input:DocumentCreateInput!){documentCreate(input:$input){success document{id}}}''',
                {'input':{'id':archive_id,'projectId':project,'title':manifest['title']+' · '+manifest['runId'], 'content':body}})['documentCreate']
            if not created['success']:
                raise ValueError('Linear 未接受归档文档')
            current=read_document()
        # Linear normalizes Markdown; a stored readback hash detects later human changes.
        if not current or document_content(current['content'] or '') != document_content(body):
            raise ValueError('Linear 文档全文回读与提交内容不一致，保留远端正文，未确认同步')
        if record.get('readbackHash') and record['readbackHash'] != digest(current['content'].encode()):
            raise ValueError('Linear 归档正文已被修改，未覆盖远端内容')
        return {'url':current['url'],'readbackHash':digest(current['content'].encode()),'zipUrl':uploads[digest(zipped)]}

    def tick(self):
        for workspace in ('personal','team'):
            settings=self.settings(workspace)
            if not settings['enabled']:
                continue
            offset=0
            while not self.stopping:
                rows,total=self.outputs.runtime.list_runs(workspace,limit=100,offset=offset)
                for run in rows:
                    if run['state']!='succeeded' or not self.outputs._content(run).strip():
                        continue
                    status=self.status(workspace,run['id'])
                    finished=str(run.get('finished_at') or run['created_at'])
                    if settings.get('since') and datetime.fromisoformat(finished)<datetime.fromisoformat(settings['since']) and not status.get('retryAfter'):
                        continue
                    github_done = (status.get('github',{}).get('status')=='confirmed' and
                                   status['github'].get('target')==settings['githubRepository'])
                    notion_enabled = bool(self.notion and self.notion.settings(workspace)['enabled'])
                    notion_done = not notion_enabled or status.get('notion',{}).get('status')=='confirmed'
                    if github_done and notion_done and not notion_enabled:
                        continue
                    if status.get('retryAfter',0)>time.time():
                        continue
                    try:
                        self.archive(workspace,run['id'])
                    except Exception:
                        logging.exception('研究归档失败：%s',run['id'])
                offset+=len(rows)
                if offset>=total or not rows:
                    break

    async def start(self):
        self.stopping=False
        self.wakeup.clear()
        async def loop():
            while not self.stopping:
                try:
                    await asyncio.to_thread(self.tick)
                except Exception:
                    logging.exception('归档扫描失败，下轮重试')
                try:
                    await asyncio.wait_for(self.wakeup.wait(),timeout=20)
                except asyncio.TimeoutError:
                    pass
        self.task=asyncio.create_task(loop())

    async def close(self):
        self.stopping=True
        self.wakeup.set()
        if self.task:
            await asyncio.gather(self.task,return_exceptions=True)


router=APIRouter(prefix='/api/lifeweave/{workspace}',tags=['research-archive'])

@router.get('/archive-settings')
def settings(request:Request,workspace:WorkspaceKey):
    return request.app.state.research_archive.settings(workspace)

@router.put('/archive-settings')
def configure(request:Request,workspace:WorkspaceKey,body:ArchiveSettings):
    try:
        return request.app.state.research_archive.configure(workspace,body)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc

@router.get('/runs/{run_id}/archive')
def status(request:Request,workspace:WorkspaceKey,run_id:str):
    try:
        return request.app.state.research_archive.status(workspace,run_id)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc

@router.post('/runs/{run_id}/archive')
def archive(request:Request,workspace:WorkspaceKey,run_id:str):
    try:
        return request.app.state.research_archive.archive(workspace,run_id)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,OSError) as exc:
        raise HTTPException(409,str(exc)) from exc

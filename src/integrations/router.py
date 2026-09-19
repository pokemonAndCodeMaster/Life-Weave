from pathlib import Path
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,Field
from src.lifeweave.models import WorkspaceKey
router=APIRouter(prefix='/api/lifeweave/{workspace}',tags=['connections'])
class ConnectionInput(BaseModel):
 token:str=''
 credentialFile:str=''
class ImportInput(BaseModel):
 issueId:str=Field(min_length=1,max_length=256)
class PublicationInput(BaseModel):
 itemId:str
 body:str=Field(min_length=1,max_length=100000)
def call(fn,*args):
 try:return fn(*args)
 except (ValueError,OSError,KeyError) as exc:raise HTTPException(409,str(exc)) from exc
@router.get('/settings')
def settings(request:Request,workspace:WorkspaceKey):
 health={name:executor.health().__dict__ for name,executor in request.app.state.executors.items()}
 return {'executors':health,'linearConfigured':request.app.state.linear.connection.configured(),'existingCredentialAvailable':(Path.home()/'.config/omni-brain/linear-api-key').is_file(),'localWorker':request.app.state.local_workers.status(workspace),'identityMode':'本机单用户','workspace':workspace}
@router.post('/connections/linear')
def connect(request:Request,workspace:WorkspaceKey,body:ConnectionInput):
 return call(request.app.state.linear.connection.save,body.token,body.credentialFile)
@router.get('/connections/linear')
def connection(request:Request,workspace:WorkspaceKey):return call(request.app.state.linear.connection.viewer)
@router.get('/linear/issues')
def issues(request:Request,workspace:WorkspaceKey,after:str|None=None):return call(request.app.state.linear.connection.issues,after)
@router.get('/linear/bindings')
def bindings(request:Request,workspace:WorkspaceKey):return call(request.app.state.linear.bindings,workspace)
@router.post('/linear/import')
def import_issue(request:Request,workspace:WorkspaceKey,body:ImportInput):return call(request.app.state.linear.import_issue,workspace,body.issueId)
@router.post('/linear/publications')
def prepare(request:Request,workspace:WorkspaceKey,body:PublicationInput):return call(request.app.state.linear.prepare,workspace,body.itemId,body.body)
@router.post('/linear/publications/{publication_id}/publish')
def publish(request:Request,workspace:WorkspaceKey,publication_id:str):return call(request.app.state.linear.publish,workspace,publication_id)

class MethodsInput(BaseModel):
 root:str=Field(min_length=1,max_length=4096)
@router.get('/methods')
def methods(request:Request,workspace:WorkspaceKey):return call(request.app.state.task_sources.catalog,workspace)
@router.get('/methods/{method_id}')
def read_method(request:Request,workspace:WorkspaceKey,method_id:str):
 return call(request.app.state.task_sources.snapshot,workspace,method_id,[])[0]
@router.post('/methods/roots')
def methods_root(request:Request,workspace:WorkspaceKey,body:MethodsInput):return call(request.app.state.task_sources.add_root,workspace,body.root)

class LocalWorkerInput(BaseModel):
 enabled:bool
 useLocalAccount:bool=False
@router.put('/settings/local-worker')
async def local_worker(request:Request,workspace:WorkspaceKey,body:LocalWorkerInput):
 try:return await request.app.state.local_workers.configure(workspace,body.enabled,body.useLocalAccount)
 except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

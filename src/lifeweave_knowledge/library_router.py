from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from src.lifeweave.models import WorkspaceKey

router = APIRouter(prefix='/api/lifeweave/{workspace}/library', tags=['library'])

class SourceCreate(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    root: str = Field(min_length=1,max_length=4096)

class RevisionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sourceId: str = 'local'
    path: str = Field(min_length=1,max_length=1000)
    content: str = Field(min_length=1,max_length=1_000_000)
    baseVersion: str
    reason: str = Field(min_length=1,max_length=2000)

class Decision(BaseModel):
    accept: bool

def call(request, method, *args):
    try:
        return getattr(request.app.state.library,method)(*args)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,OSError,UnicodeError) as exc:
        raise HTTPException(409,str(exc)) from exc

@router.get('/sources')
def sources(request: Request,workspace:WorkspaceKey):
    return call(request,'sources',workspace)

@router.post('/sources',status_code=201)
def add_source(request:Request,workspace:WorkspaceKey,body:SourceCreate):
    return call(request,'add_source',workspace,body.title,body.root)

@router.get('/documents')
def catalog(request:Request,workspace:WorkspaceKey,q:str='',sourceId:str|None=None):
    return call(request,'catalog',workspace,q,sourceId)

@router.get('/document')
def document(request:Request,workspace:WorkspaceKey,path:str,sourceId:str='local'):
    return call(request,'document',workspace,sourceId,path)

@router.get('/links')
def links(request:Request,workspace:WorkspaceKey,path:str,sourceId:str='local'):
    try:
        return request.app.state.knowledge_links.document_links(workspace,sourceId,path)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,OSError,UnicodeError) as exc:
        raise HTTPException(409,str(exc)) from exc

@router.get('/relations')
def relations(request:Request,workspace:WorkspaceKey,path:str,sourceId:str='local'):
    try:
        return request.app.state.knowledge_links.semantic_relations(workspace,sourceId,path)
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,OSError,UnicodeError) as exc:
        raise HTTPException(409,str(exc)) from exc

@router.get('/revisions')
def revisions(request:Request,workspace:WorkspaceKey):
    return call(request,'revisions',workspace)

@router.post('/revisions',status_code=201)
def propose(request:Request,workspace:WorkspaceKey,body:RevisionCreate):
    return call(request,'propose',workspace,body.sourceId,body.path,body.content,body.baseVersion,body.reason)

@router.post('/revisions/{revision_id}/decision')
def decide(request:Request,workspace:WorkspaceKey,revision_id:str,body:Decision):
    return call(request,'decide',workspace,revision_id,body.accept)

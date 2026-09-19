from fastapi import APIRouter, Request, HTTPException, Query
from .models import WorkspaceKey
from .conversation_models import ConversationCreate, TurnCreate, PersonalModelUpdate
from .repository import ConcurrentUpdateError

router = APIRouter(prefix='/api/lifeweave/{workspace}',tags=['conversation'])


def fail(exc):
    return HTTPException(404 if isinstance(exc,KeyError) else 409 if isinstance(exc,ConcurrentUpdateError) else 400,str(exc))


@router.get('/conversations')
def conversations(request:Request, workspace:WorkspaceKey, itemId:str|None=None):
    return request.app.state.conversations.repository.list(workspace,itemId)


@router.post('/conversations',status_code=201)
def create(request:Request, workspace:WorkspaceKey, body:ConversationCreate):
    try: return request.app.state.conversations.create(workspace,body)
    except (KeyError,ValueError) as exc: raise fail(exc) from exc


@router.get('/conversations/{cid}')
def read(request:Request, workspace:WorkspaceKey, cid:str):
    try: return request.app.state.conversations.read(workspace,cid)
    except (KeyError,ValueError) as exc: raise fail(exc) from exc


@router.post('/conversations/{cid}/turns',status_code=202)
async def submit(request:Request, workspace:WorkspaceKey, cid:str, body:TurnCreate):
    try: return await request.app.state.conversations.submit(workspace,cid,body)
    except (KeyError,ValueError) as exc: raise fail(exc) from exc


@router.post('/conversations/{cid}/turns/{tid}/cancel')
async def cancel(request:Request, workspace:WorkspaceKey, cid:str, tid:str):
    try: return await request.app.state.conversations.cancel(workspace,cid,tid)
    except (KeyError,ValueError) as exc: raise fail(exc) from exc


@router.get('/personal-model')
def profile(request:Request, workspace:WorkspaceKey):
    return request.app.state.conversations.repository.profile(workspace)


@router.put('/personal-model')
def update_profile(request:Request, workspace:WorkspaceKey, body:PersonalModelUpdate):
    try: return request.app.state.conversations.repository.save_profile(workspace,body)
    except (KeyError,ValueError) as exc: raise fail(exc) from exc

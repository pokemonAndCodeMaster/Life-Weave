from typing import Annotated

from fastapi import APIRouter, Depends, Request, Query
from pydantic import Field

from src.api.deps import get_actor_id
from .models import WireModel
from .router import _fail

router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['continuation'])


class FeedbackCreate(WireModel):
    body: str = Field(min_length=1, max_length=100_000)
    run_id: str | None = Field(default=None, alias='runId', max_length=64)
    request_id: str = Field(alias='requestId', min_length=1, max_length=128)
    anchor: str | None = Field(default=None, max_length=256)


@router.get('/work-discovery')
def discover(request: Request, workspace: str, query: str = Query(default='', max_length=10_000)):
    try:
        return request.app.state.work_continuation.discover(workspace, query)
    except (KeyError, ValueError) as exc:
        raise _fail(exc) from exc


@router.get('/items/{item_id}/continuation')
def continuation(request: Request, workspace: str, item_id: str):
    try:
        return request.app.state.work_continuation.read(workspace, item_id)
    except (KeyError, ValueError) as exc:
        raise _fail(exc) from exc


@router.get('/items/{item_id}/input-recommendations')
def recommendations(request: Request, workspace: str, item_id: str, query: str = Query(default='', max_length=10_000)):
    try:
        work = request.app.state.lifeweave_service
        item = work.get_item(workspace, item_id)
        context = work.current_context_snapshot(workspace, item_id)
        return request.app.state.task_sources.recommend(workspace, item, context, query)
    except (KeyError, ValueError) as exc:
        raise _fail(exc) from exc


@router.post('/items/{item_id}/feedback', status_code=201)
def feedback(request: Request, workspace: str, item_id: str, payload: FeedbackCreate,
             actor_id: Annotated[str, Depends(get_actor_id)]):
    try:
        return request.app.state.lifeweave_service.record_feedback(workspace, item_id, actor_id=actor_id, **payload.model_dump())
    except (KeyError, ValueError) as exc:
        raise _fail(exc) from exc

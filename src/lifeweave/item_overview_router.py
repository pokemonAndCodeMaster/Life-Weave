from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.deps import get_actor_id

from .item_overview import ItemOverviewService
from .item_overview_models import ItemOverviewInput
from .repository import ConcurrentUpdateError
from .work_view import WorkViewService


router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['lifeweave'])
Actor = Annotated[str, Depends(get_actor_id)]


@router.put('/items/{item_id}/overview')
def save_overview(workspace: str, item_id: str, body: ItemOverviewInput,
                  request: Request, actor_id: Actor) -> dict[str, Any]:
    work = request.app.state.lifeweave_service
    view = WorkViewService(work, request.app.state.lifeweave_runtime_service, request.app.state.development)
    try:
        return ItemOverviewService(work).save(workspace, item_id, version=body.version,
                                              background=body.background, intent=body.intent,
                                              expected_result=body.expected_result,
                                              actor_id=actor_id, view_service=view)
    except KeyError as exc:
        raise HTTPException(404, detail=f'对象不存在：{exc.args[0]}') from exc
    except ConcurrentUpdateError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

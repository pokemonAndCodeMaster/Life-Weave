from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from src.lifeweave.models import WorkspaceKey

router = APIRouter(prefix="/api/lifeweave/{workspace}", tags=["plugins"])


class PluginEnableInput(BaseModel):
    enabled: bool
    expectedVersion: int = Field(ge=1)


@router.get("/plugins")
def catalog(request: Request, workspace: WorkspaceKey):
    return request.app.state.plugins.catalog(workspace)


@router.get("/plugins/{plugin_id}")
def detail(request: Request, workspace: WorkspaceKey, plugin_id: str):
    try:
        return request.app.state.plugins.detail(workspace, plugin_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/plugins/{plugin_id}/enabled")
def enable(request: Request, workspace: WorkspaceKey, plugin_id: str, payload: PluginEnableInput):
    try:
        return request.app.state.plugins.set_enabled(
            workspace, plugin_id, enabled=payload.enabled, expected_version=payload.expectedVersion)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/items/{item_id}/plugin-process")
def process(request: Request, workspace: WorkspaceKey, item_id: str, assignmentId: str | None = None):
    try:
        return request.app.state.plugins.process(workspace, item_id, assignmentId)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/plugins/{plugin_id}/calls")
def calls(request: Request, workspace: WorkspaceKey, plugin_id: str, limit: int = 30):
    try:
        request.app.state.plugins.detail(workspace, plugin_id)
        return {"items": request.app.state.plugins.public_calls(
            request.app.state.plugin_host.calls(workspace, plugin_id=plugin_id, limit=limit))}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

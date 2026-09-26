from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .models import WorkspaceKey


router = APIRouter(prefix="/api/lifeweave/{workspace}", tags=["development"])


class DevelopmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requestId: str = Field(min_length=1, max_length=128)
    itemId: str = Field(min_length=1, max_length=64)
    instruction: str = Field(min_length=1, max_length=100_000)
    repositoryPath: str = Field(min_length=1, max_length=4096)
    agentId: Literal["development"] = "development"
    engine: Literal["codex", "opencode"] = "codex"
    model: str | None = Field(default=None, max_length=256)
    methodId: str | None = Field(default=None, max_length=64)
    knowledgeRefs: list[str] | None = Field(default=None, max_length=10)
    reviewMode: Literal["independent", "self"] = "independent"
    acknowledgeExcludedChanges: bool = False


def error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, "开发事项不存在")
    return HTTPException(409, str(exc))


@router.get("/items/{item_id}/development/choices")
def choices(request: Request, workspace: WorkspaceKey, item_id: str):
    try:
        return request.app.state.development.choices(workspace, item_id)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.get("/items/{item_id}/development")
def list_assignments(request: Request, workspace: WorkspaceKey, item_id: str):
    try:
        return {"items": request.app.state.development.list(workspace, item_id)}
    except (ValueError, KeyError) as exc:
        raise error(exc) from exc


@router.post("/development", status_code=202)
def create(request: Request, workspace: WorkspaceKey, body: DevelopmentCreate):
    try:
        return request.app.state.development.create(
            workspace, item_id=body.itemId, request_id=body.requestId,
            instruction=body.instruction, repository_path=body.repositoryPath,
            engine=body.engine, model=body.model, method_id=body.methodId,
            knowledge_refs=body.knowledgeRefs, review_mode=body.reviewMode,
            acknowledge_excluded_changes=body.acknowledgeExcludedChanges)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.get("/development/{assignment_id}")
def read(request: Request, workspace: WorkspaceKey, assignment_id: str):
    try:
        return request.app.state.development.get(workspace, assignment_id)
    except KeyError as exc:
        raise error(exc) from exc


@router.get("/development/{assignment_id}/diff")
def diff(request: Request, workspace: WorkspaceKey, assignment_id: str):
    try:
        return request.app.state.development.diff(workspace, assignment_id)
    except (KeyError, ValueError, OSError) as exc:
        raise error(exc) from exc


@router.post("/development/{assignment_id}/cancel")
def cancel(request: Request, workspace: WorkspaceKey, assignment_id: str):
    try:
        return request.app.state.development.cancel(workspace, assignment_id)
    except (KeyError, ValueError) as exc:
        raise error(exc) from exc

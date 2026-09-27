from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
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
    executionScope: Literal["plan_only", "implement"] = "plan_only"
    acknowledgeExcludedChanges: bool = False
    stepId: str | None = Field(default=None, min_length=1, max_length=128)
    planVersion: int | None = Field(default=None, ge=1)


class IntegrationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commit: str = Field(min_length=40, max_length=64)


class DeliveryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requestId: str = Field(min_length=1, max_length=128)
    artifactSha256: str = Field(min_length=64, max_length=64)
    decision: Literal["accepted", "rejected"]
    scope: Literal["patch", "integrated"]
    reason: str = Field(default="", max_length=10000)


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
            execution_scope=body.executionScope,
            acknowledge_excluded_changes=body.acknowledgeExcludedChanges,
            step_id=body.stepId, plan_version=body.planVersion)
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


@router.get("/development/{assignment_id}/delivery")
def delivery(request: Request, workspace: WorkspaceKey, assignment_id: str):
    try:
        value = request.app.state.development.delivery(workspace, assignment_id)
        if value is None:
            raise ValueError("此委托尚无固定交付包")
        return value
    except (KeyError, ValueError) as exc:
        raise error(exc) from exc


@router.get("/development/{assignment_id}/delivery.zip")
def download_delivery(request: Request, workspace: WorkspaceKey, assignment_id: str):
    try:
        content = request.app.state.development.delivery_bytes(workspace, assignment_id)
        return Response(content, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="lifeweave-{assignment_id}.zip"',
            "X-Content-Type-Options": "nosniff"})
    except (KeyError, ValueError, OSError) as exc:
        raise error(exc) from exc


@router.post("/development/{assignment_id}/integration-check")
def integration_check(request: Request, workspace: WorkspaceKey, assignment_id: str, body: IntegrationCheck):
    try:
        return request.app.state.development.verify_integration(workspace, assignment_id, body.commit)
    except (KeyError, ValueError, OSError) as exc:
        raise error(exc) from exc


@router.post("/development/{assignment_id}/decision")
def decide_delivery(request: Request, workspace: WorkspaceKey, assignment_id: str, body: DeliveryDecision):
    try:
        return request.app.state.development.decide_delivery(
            workspace, assignment_id, artifact_sha256=body.artifactSha256,
            decision=body.decision, scope=body.scope, reason=body.reason,
            request_id=body.requestId, actor_id="local-user")
    except (KeyError, ValueError, OSError) as exc:
        raise error(exc) from exc


@router.post("/development/{assignment_id}/cancel")
def cancel(request: Request, workspace: WorkspaceKey, assignment_id: str):
    try:
        return request.app.state.development.cancel(workspace, assignment_id)
    except (KeyError, ValueError) as exc:
        raise error(exc) from exc

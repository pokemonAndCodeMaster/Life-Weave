from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.lifeweave.models import WorkspaceKey


router = APIRouter(prefix="/api/lifeweave/{workspace}", tags=["agents"])


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    capability: Literal["development", "research", "general", "organization"]
    methodId: str | None = Field(default=None, max_length=64)
    engine: Literal["codex", "opencode", "builtin"] | None = None
    model: str | None = Field(default=None, max_length=256)
    runtime: Literal["native", "docker"] = "native"
    permission: Literal["read-only", "workspace-write"] = "read-only"
    enabled: bool = True


class AgentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    methodId: str | None = Field(default=None, max_length=64)
    engine: Literal["codex", "opencode", "builtin"] | None = None
    model: str | None = Field(default=None, max_length=256)
    runtime: Literal["native", "docker"] | None = None
    permission: Literal["read-only", "workspace-write"] | None = None
    enabled: bool | None = None


class OrganizationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["propose", "apply"]
    proposalId: str | None = None
    itemIds: list[str] = Field(default_factory=list, max_length=100)


class AgentDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requestId: str = Field(min_length=1, max_length=128)
    agentId: str = Field(min_length=2, max_length=64)
    mode: Literal["managed_development", "managed_run", "organization"]
    engine: Literal["codex", "opencode", "builtin"] | None = None
    model: str | None = Field(default=None, max_length=256)
    runtime: Literal["native", "docker"] | None = None
    image: str | None = Field(default=None, max_length=512)
    permission: Literal["read-only", "workspace-write"] | None = None
    instruction: str | None = Field(default=None, max_length=100_000)
    repositoryPath: str | None = Field(default=None, max_length=4096)
    directory: str | None = Field(default=None, max_length=4096)
    branch: str | None = Field(default=None, max_length=256)
    machineId: str | None = Field(default=None, max_length=64)
    capabilityCandidateId: str | None = Field(default=None, max_length=64)
    methodId: str | None = Field(default=None, max_length=64)
    knowledgeRefs: list[str] = Field(default_factory=list, max_length=10)
    reviewMode: Literal["independent", "self"] | None = None
    executionScope: Literal["plan_only", "implement"] | None = None
    stepId: str | None = Field(default=None, max_length=128)
    planVersion: int | None = Field(default=None, ge=1)
    acknowledgeExcludedChanges: bool = False
    organization: OrganizationChoice | None = None


def error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, "Agent、事项或执行不存在")
    return HTTPException(409, str(exc))


@router.get("/agents")
def catalog(request: Request, workspace: WorkspaceKey):
    try:
        return request.app.state.agent_registry.catalog(workspace)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.post("/agents", status_code=201)
def create(request: Request, workspace: WorkspaceKey, body: AgentCreate):
    try:
        return request.app.state.agent_registry.create(workspace, body.model_dump())
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.get("/agents/{agent_id}")
def read(request: Request, workspace: WorkspaceKey, agent_id: str):
    try:
        return request.app.state.agent_registry.get(workspace, agent_id)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.patch("/agents/{agent_id}")
def patch(request: Request, workspace: WorkspaceKey, agent_id: str, body: AgentPatch):
    try:
        changes = body.model_dump(exclude_unset=True)
        changes.pop("version")
        return request.app.state.agent_registry.patch(workspace, agent_id, body.version, changes)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.get("/items/{item_id}/agent-choices")
def choices(request: Request, workspace: WorkspaceKey, item_id: str):
    try:
        return request.app.state.agent_registry.choices(workspace, item_id, request.app.state.lifeweave_service)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.post("/items/{item_id}/agent-dispatch", status_code=202)
def dispatch(request: Request, workspace: WorkspaceKey, item_id: str, body: AgentDispatch):
    try:
        return request.app.state.agent_service.dispatch(workspace, item_id, body.model_dump(exclude_unset=True, exclude_none=True))
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.get("/agent-executions")
def executions(request: Request, workspace: WorkspaceKey,
               agent_id: str | None = Query(default=None, alias="agentId"),
               item_id: str | None = Query(default=None, alias="itemId"),
               status: str | None = None, limit: int = Query(default=50, ge=1, le=100),
               offset: int = Query(default=0, ge=0)):
    try:
        return request.app.state.agent_service.executions(
            workspace, agent_id=agent_id, item_id=item_id, status=status, limit=limit, offset=offset)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc


@router.get("/agent-executions/{kind}/{execution_id}")
def detail(request: Request, workspace: WorkspaceKey, kind: str, execution_id: str):
    try:
        return request.app.state.agent_service.detail(workspace, kind, execution_id)
    except (ValueError, KeyError, OSError) as exc:
        raise error(exc) from exc

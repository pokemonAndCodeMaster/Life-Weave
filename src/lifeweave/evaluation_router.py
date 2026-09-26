from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .models import WorkspaceKey

router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['lifeweave-evaluations'])


class Input(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra='forbid')


class EvaluationCreate(Input):
    item_id: str = Field(min_length=1, max_length=64)
    target_kind: Literal['system', 'capability']
    candidate_id: str | None = Field(default=None, max_length=64)
    repeat_of: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    instruction: str = Field(min_length=1, max_length=100_000)
    criteria: str = Field(min_length=1, max_length=20_000)


class EvaluationStart(Input):
    engine: Literal['codex', 'opencode'] = 'codex'
    permission: Literal['read-only', 'workspace-write'] = 'read-only'
    model: str | None = Field(default=None, max_length=256)
    directory: str | None = Field(default=None, max_length=2000)
    method_id: str | None = Field(default=None, max_length=100)
    knowledge_refs: list[str] = Field(default_factory=list, max_length=10)


class EvaluationAssessment(Input):
    outcome: Literal['passed', 'failed', 'inconclusive']
    assessment: str = Field(min_length=1, max_length=20_000)
    evidence_id: str | None = Field(default=None, max_length=64)


class EvaluationImprovement(Input):
    target_kind: Literal['knowledge', 'skill', 'agent', 'harness']
    problem: str = Field(min_length=1, max_length=20_000)
    desired_behavior: str = Field(min_length=1, max_length=20_000)
    validation_plan: str = Field(min_length=1, max_length=20_000)


def call(request: Request, name: str, workspace: str, *args, **kwargs):
    try:
        return getattr(request.app.state.lifeweave_evaluations, name)(workspace, *args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, '评测目标或所属事项不存在') from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/evaluations')
def evaluations(request: Request, workspace: WorkspaceKey,
                limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    return call(request, 'list', workspace, limit, offset)


@router.get('/capabilities/{candidate_id}/evaluations')
def candidate_history(request: Request, workspace: WorkspaceKey, candidate_id: str,
                      limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return call(request, 'candidate_history', workspace, candidate_id, limit, offset)


@router.post('/evaluations', status_code=201)
def create(request: Request, workspace: WorkspaceKey, body: EvaluationCreate):
    return call(request, 'create', workspace, body.model_dump(by_alias=True))


@router.get('/evaluations/{evaluation_id}')
def get(request: Request, workspace: WorkspaceKey, evaluation_id: str):
    return call(request, 'get', workspace, evaluation_id)


@router.post('/evaluations/{evaluation_id}/start')
def start(request: Request, workspace: WorkspaceKey, evaluation_id: str, body: EvaluationStart):
    return call(request, 'start', workspace, evaluation_id, **body.model_dump())


@router.post('/evaluations/{evaluation_id}/assess')
def assess(request: Request, workspace: WorkspaceKey, evaluation_id: str, body: EvaluationAssessment):
    return call(request, 'assess', workspace, evaluation_id, **body.model_dump())


@router.post('/evaluations/{evaluation_id}/improvement')
def create_improvement(request: Request, workspace: WorkspaceKey, evaluation_id: str,
                       body: EvaluationImprovement):
    return call(request, 'create_improvement', workspace, evaluation_id, **body.model_dump())

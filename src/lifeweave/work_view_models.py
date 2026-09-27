"""Shared request contract for an item's declared work graph."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import WireModel


MAX_WORK_STEPS = 80
MAX_STEP_DEPENDENCIES = MAX_WORK_STEPS - 1
WorkStepState = Literal['planned', 'running', 'waiting', 'succeeded', 'failed', 'cancelled', 'unobserved']
StepId = Annotated[str, Field(min_length=1, max_length=128)]
OutputId = Annotated[str, Field(min_length=1, max_length=256)]


class WorkContextRef(WireModel):
    title: str = Field(min_length=1, max_length=256)
    uri: str | None = Field(default=None, max_length=2048)


class WorkStepInput(WireModel):
    id: StepId
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default='', max_length=5000)
    state: WorkStepState = 'planned'
    summary: str = Field(default='', max_length=2000)
    depends_on: list[StepId] = Field(default_factory=list, alias='dependsOn', max_length=MAX_STEP_DEPENDENCIES)
    output_ids: list[OutputId] = Field(default_factory=list, alias='outputIds', max_length=MAX_WORK_STEPS)
    run_id: str | None = Field(default=None, alias='runId', max_length=128)
    assignment_id: str | None = Field(default=None, alias='assignmentId', max_length=128)
    context_refs: list[WorkContextRef] = Field(default_factory=list, alias='contextRefs', max_length=20)
    provenance: str | None = Field(default=None, max_length=256)


class WorkPlanInput(WireModel):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=256)
    provider: str = Field(min_length=1, max_length=128)
    nodes: list[WorkStepInput] = Field(max_length=MAX_WORK_STEPS)

    @model_validator(mode='after')
    def valid_graph(self) -> 'WorkPlanInput':
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError('步骤 ID 不能重复')
        known = set(ids)
        graph = {node.id: node.depends_on for node in self.nodes}
        for node in self.nodes:
            if len(node.depends_on) != len(set(node.depends_on)):
                raise ValueError(f'步骤 {node.id} 有重复依赖')
            if node.id in node.depends_on:
                raise ValueError(f'步骤 {node.id} 不能依赖自身')
            missing = set(node.depends_on) - known
            if missing:
                raise ValueError(f'步骤 {node.id} 引用了不存在的依赖：{sorted(missing)[0]}')
            if len(node.output_ids) != len(set(node.output_ids)):
                raise ValueError(f'步骤 {node.id} 有重复成果引用')
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError('步骤依赖不能形成环路')
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in graph[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        return self

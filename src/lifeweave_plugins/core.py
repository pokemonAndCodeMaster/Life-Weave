"""Versioned plugin identity and real invocation recording.

The registry is a contract around existing services, not another task engine.
Only `invoke` may record an actual call; listing a descriptor never does.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, TypeVar
from uuid import uuid4

from psycopg.types.json import Jsonb


T = TypeVar("T")
_parent_call: ContextVar[str | None] = ContextVar("lifeweave_plugin_parent", default=None)


@dataclass(frozen=True)
class PluginDefinition:
    id: str
    name: str
    description: str
    kind: str
    version: str
    operations: tuple[str, ...]
    requires: tuple[str, ...] = ()
    composed_of: tuple[str, ...] = ()
    implementation_paths: tuple[str, ...] = ()
    configuration_link: str | None = None
    observation_boundary: str = "仅记录 LifeWeave 受管调用；第三方内部行为按原生事件覆盖范围显示"


class PluginRegistry:
    def __init__(self, root: Path, definitions: list[PluginDefinition]):
        self.root = root
        self.definitions: dict[str, PluginDefinition] = {}
        for definition in definitions:
            if definition.id in self.definitions:
                raise ValueError(f"重复插件 ID：{definition.id}")
            self.definitions[definition.id] = definition
        for definition in definitions:
            for dependency in definition.requires + definition.composed_of:
                if dependency not in self.definitions:
                    raise ValueError(f"插件 {definition.id} 引用了不存在的插件：{dependency}")
        def visit(identity: str, trail: set[str], done: set[str]) -> None:
            if identity in trail:
                raise ValueError(f"插件依赖循环：{identity}")
            if identity in done:
                return
            trail.add(identity)
            for dependency in self.definitions[identity].requires:
                visit(dependency, trail, done)
            trail.remove(identity)
            done.add(identity)
        done: set[str] = set()
        for identity in self.definitions:
            visit(identity, set(), done)

    def require(self, identity: str, operation: str | None = None) -> PluginDefinition:
        try:
            definition = self.definitions[identity]
        except KeyError as exc:
            raise KeyError(f"插件不存在：{identity}") from exc
        if operation is not None and operation not in definition.operations:
            raise ValueError(f"插件 {identity} 不支持操作 {operation}")
        return definition

    def digest(self, definition: PluginDefinition) -> str:
        digest = hashlib.sha256()
        manifest = {key: value for key, value in definition.__dict__.items() if key != "implementation_paths"}
        digest.update(json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())
        for relative in definition.implementation_paths:
            path = (self.root / relative).resolve()
            if not path.is_relative_to(self.root.resolve()) or not path.is_file():
                raise ValueError(f"插件实现文件不可读取：{relative}")
            digest.update(relative.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def describe(self, identity: str) -> dict[str, Any]:
        definition = self.require(identity)
        return {**definition.__dict__, "implementationDigest": self.digest(definition)}

    def list(self) -> list[dict[str, Any]]:
        return [self.describe(identity) for identity in self.definitions]

    def register_method(self, *, legacy_id: str, title: str, description: str, version: str) -> str:
        identity = f"lifeweave.method.{legacy_id}"
        if identity in self.definitions and self.definitions[identity].kind != "skill":
            raise ValueError(f"方法插件 ID 冲突：{identity}")
        self.definitions[identity] = PluginDefinition(
            identity, title, description, "skill", version, ("bind",),
            observation_boundary="绑定和物化可观测；不能由此推断执行器遵循了全部方法步骤")
        return identity


def builtin_registry(root: Path) -> PluginRegistry:
    return PluginRegistry(root, [
        PluginDefinition("lifeweave.knowledge", "知识读取", "开发运行检索推荐并读取版本化知识；其他知识操作暂由现有接口负责", "foundation", "1.0.0",
                         ("recommend", "read"),
                         implementation_paths=("src/lifeweave_knowledge/library.py", "src/integrations/task_sources.py", "src/integrations/notion_mirror.py"),
                         configuration_link="knowledge"),
        PluginDefinition("lifeweave.context", "任务上下文", "按任务阶段固定背景、方法、知识和来源版本", "foundation", "1.0.0",
                         ("compile",), requires=("lifeweave.knowledge",),
                         implementation_paths=("src/lifeweave_runtime/service.py", "src/integrations/task_sources.py")),
        PluginDefinition("lifeweave.execution.codex", "Codex 执行", "受管工作树中的 Codex CLI 工具循环", "executor", "1.0.0",
                         ("run",), implementation_paths=("src/agent_runtime/codex_executor.py", "src/lifeweave_runtime/worker.py"),
                         configuration_link="settings"),
        PluginDefinition("lifeweave.execution.opencode", "OpenCode 执行", "当前开发委托暂停；保留历史运行与失败证据", "executor", "1.0.0",
                         ("run",), implementation_paths=("src/agent_runtime/opencode_executor.py",),
                         configuration_link="settings"),
        PluginDefinition("lifeweave.checks.repository", "代码与输入检查", "核对只读树、项目提交和固定材料", "script", "1.0.0",
                         ("verify_readonly", "verify_inputs"),
                         implementation_paths=("src/lifeweave/development.py", "src/agent_runtime/tree_snapshot.py")),
        PluginDefinition("lifeweave.development", "开发工作", "复用现有方案、审阅、隔离实施与验证的组合", "composite", "1.0.0",
                         ("plan", "review", "implement"),
                         requires=("lifeweave.context", "lifeweave.execution.codex", "lifeweave.checks.repository"),
                         composed_of=("lifeweave.context", "lifeweave.execution.codex", "lifeweave.checks.repository"),
                         implementation_paths=("src/lifeweave/development.py",),
                         configuration_link="items"),
        PluginDefinition("lifeweave.observation", "调用观测", "按原计划和真实调用读取过程；原生事件保留原来源", "foundation", "1.0.0",
                         ("compare",), implementation_paths=("src/lifeweave_plugins/core.py",)),
        PluginDefinition("lifeweave.evaluation", "效果评价", "现有评测尚未接入统一插件调用", "foundation", "1.0.0",
                         ("assess",), implementation_paths=("src/lifeweave/evaluations.py",)),
    ])


class PluginHost:
    """Record a real call while leaving business state with the existing owner."""
    def __init__(self, db: Any, registry: PluginRegistry):
        self.db = db
        self.registry = registry
        self.service: Any = None

    def invoke(self, identity: str, operation: str, *, workspace: str, item_id: str,
               handler: Callable[[], T], assignment_id: str | None = None,
               run_id: str | None = None, plan_id: str | None = None,
               step_id: str | None = None, input_ref: dict[str, Any] | None = None,
               output_ref: Callable[[T], dict[str, Any]] | None = None,
               accepted: bool = False) -> T:
        definition = self.registry.require(identity, operation)
        if self.service is not None:
            if plan_id:
                self.service.require_bound(workspace, plan_id, identity, operation)
            else:
                self.service.require_runnable(workspace, identity, operation)
        call_id = "pcall-" + uuid4().hex[:24]
        self.db.execute(
            "INSERT INTO workbench.lifeweave_plugin_call "
            "(id,workspace,item_id,assignment_id,run_id,plan_id,step_id,parent_call_id,plugin_id,plugin_version,"
            "implementation_digest,operation,state,input_ref,observed_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'started',%s,'platform')",
            (call_id, workspace, item_id, assignment_id, run_id, plan_id, step_id,
             _parent_call.get(), identity, definition.version, self.registry.digest(definition),
             operation, Jsonb(input_ref or {})))
        token = _parent_call.set(call_id)
        try:
            result = handler()
        except Exception as exc:
            self.db.execute("UPDATE workbench.lifeweave_plugin_call SET state='failed',error=%s,finished_at=now() WHERE id=%s",
                            (str(exc)[:2000], call_id))
            raise
        else:
            self.db.execute("UPDATE workbench.lifeweave_plugin_call SET state=%s,output_ref=%s,finished_at=now() WHERE id=%s",
                            ("accepted" if accepted else "succeeded", Jsonb(output_ref(result) if output_ref else {}), call_id))
            return result
        finally:
            _parent_call.reset(token)

    def calls(self, workspace: str, *, item_id: str | None = None,
              plugin_id: str | None = None, assignment_id: str | None = None,
              limit: int = 100) -> list[dict[str, Any]]:
        if not item_id and not plugin_id and not assignment_id:
            raise ValueError("调用查询必须指定事项、委托或插件")
        if not 1 <= limit <= 200:
            raise ValueError("调用数量必须在 1 到 200 之间")
        where = ["workspace=%s"]
        values: list[Any] = [workspace]
        if item_id:
            where.append("item_id=%s"); values.append(item_id)
        if plugin_id:
            where.append("plugin_id=%s"); values.append(plugin_id)
        if assignment_id:
            where.append("assignment_id=%s"); values.append(assignment_id)
        values.append(limit)
        return self.db.fetch_all("SELECT * FROM workbench.lifeweave_plugin_call WHERE " + " AND ".join(where) +
                                 " ORDER BY started_at DESC,id DESC LIMIT %s", values)

    def worker_transition(self, *, workspace: str, item_id: str, run_id: str,
                          scope: dict[str, Any], engine: str, outcome: str,
                          exit_code: int | None = None, error: str | None = None) -> None:
        """Project lease-validated worker reports into one execution call."""
        assignment_id = scope.get("assignmentId")
        plan_id = scope.get("planId")
        stage = scope.get("stage")
        label = {"plan": "plan", "review": "review", "implementation": "implement"}.get(stage)
        if not assignment_id or not plan_id or not label:
            return
        identity = f"lifeweave.execution.{engine}"
        definition = self.registry.require(identity, "run")
        if outcome == "running":
            parent = self.db.fetch_one(
                "SELECT id FROM workbench.lifeweave_plugin_call "
                "WHERE workspace=%s AND assignment_id=%s AND plan_id=%s AND step_id=%s "
                "AND plugin_id='lifeweave.development' ORDER BY started_at DESC LIMIT 1",
                (workspace, assignment_id, plan_id, f"{label}.development"))
            self.db.execute(
                "INSERT INTO workbench.lifeweave_plugin_call "
                "(id,workspace,item_id,assignment_id,run_id,plan_id,step_id,parent_call_id,plugin_id,plugin_version,"
                "implementation_digest,operation,state,input_ref,observed_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'run','started',%s,'worker-report') "
                "ON CONFLICT (workspace,run_id,plugin_id,operation) WHERE run_id IS NOT NULL AND observed_by = 'worker-report' DO NOTHING",
                ("pcall-" + uuid4().hex[:24], workspace, item_id, assignment_id, run_id,
                 plan_id, f"{label}.codex", parent["id"] if parent else None,
                 identity, definition.version, self.registry.digest(definition),
                 Jsonb({"runId": run_id, "stage": stage})))
        elif outcome in {"succeeded", "failed", "interrupted"}:
            state = outcome
            changed = self.db.execute(
                "UPDATE workbench.lifeweave_plugin_call SET state=%s,output_ref=%s,error=%s,finished_at=now() "
                "WHERE workspace=%s AND run_id=%s AND plugin_id=%s AND operation='run' AND state='started'",
                (state, Jsonb({"runId": run_id, "outcome": outcome, "exitCode": exit_code}),
                 (error or "")[:2000] or None, workspace, run_id, identity))
            if changed != 1:
                raise ValueError("执行插件尚未记录启动，不能接受结束事件")

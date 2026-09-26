"""Catalog and task-process views over the same plugin identities used by calls."""
from __future__ import annotations

from typing import Any
from psycopg.types.json import Jsonb

from .core import PluginHost, PluginRegistry


class PluginService:
    def __init__(self, db: Any, registry: PluginRegistry, host: PluginHost,
                 sources: Any, runtime: Any, work: Any):
        self.db, self.registry, self.host = db, registry, host
        self.sources, self.runtime, self.work = sources, runtime, work

    def _methods(self, workspace: str) -> set[str]:
        seen: set[str] = set()
        for row in self.sources.catalog(workspace)["items"]:
            try:
                snapshot = self.sources.snapshot(workspace, row["id"], [])
            except (ValueError, OSError, UnicodeError):
                continue
            identity = self.registry.register_method(
                legacy_id=row["id"], title=row["title"],
                description=row["description"], version=snapshot[0]["version"])
            seen.add(identity)
        return seen

    def _status(self, workspace: str, identity: str, methods: set[str]) -> dict[str, Any]:
        codex = self.runtime.executors["codex"].health()
        setting = self.db.fetch_one(
            "SELECT enabled,config_version FROM workbench.lifeweave_plugin_setting "
            "WHERE workspace=%s AND plugin_id=%s", (workspace, identity))
        if identity.startswith("lifeweave.method."):
            available = identity in methods
            reason = "方法正文和支持文件可读取" if available else "此空间没有登记该方法"
        elif identity == "lifeweave.execution.codex":
            available = codex.available
            reason = codex.reason or "CLI 可启动；具体账号与模型仍由真实任务验证"
        elif identity == "lifeweave.execution.opencode":
            # The development service owns the opt-in gate. Keeping the
            # catalog aligned also lets its isolated regression exercise it.
            from src.lifeweave.development import OPENCODE_DEVELOPMENT_ENABLED
            available = OPENCODE_DEVELOPMENT_ENABLED and self.runtime.executors["opencode"].health().available
            reason = ("显式实验开关已开启；仍需相同模型的工作区验证" if available else
                      "开发只读边界曾越权，隔离模型回归未完成，暂不可用于新开发委托")
        elif identity == "lifeweave.development":
            available = codex.available and any(
                self.registry.definitions[method].name == "lifeweave-development" for method in methods)
            reason = "Codex 与开发方法可用" if available else "Codex 或开发方法不可用"
        elif identity == "lifeweave.evaluation":
            available = False
            reason = "评测功能仍可从原入口使用，统一插件调用尚未接通"
        else:
            available = True
            reason = "本机实现可装配；实际效果以调用和评测为准"
        enabled = bool(setting["enabled"]) if setting else True
        dependencies = self.registry.require(identity).requires
        blocked = [dependency for dependency in dependencies
                   if not self._status(workspace, dependency, methods)["runnable"]]
        if not enabled:
            reason = "此空间已停用；不会接受新的插件调用"
        elif blocked:
            reason = "依赖不可运行：" + "、".join(blocked)
        return {"registered": True, "enabled": enabled, "configured": available,
                "runnable": available and enabled and not blocked, "verified": False, "reason": reason,
                "configVersion": setting["config_version"] if setting else 1,
                "verificationScope": "已有有界任务证据，统一插件接入仍待本轮实测" if identity == "lifeweave.development" else None}

    def set_enabled(self, workspace: str, identity: str, *, enabled: bool,
                    expected_version: int) -> dict[str, Any]:
        self.detail(workspace, identity)
        if expected_version < 1:
            raise ValueError("配置版本必须大于零")
        current = self.db.fetch_one(
            "SELECT config_version FROM workbench.lifeweave_plugin_setting WHERE workspace=%s AND plugin_id=%s",
            (workspace, identity))
        if current is None and expected_version != 1:
            raise ValueError("插件配置已变化，请刷新后重试")
        row = self.db.fetch_one(
            "INSERT INTO workbench.lifeweave_plugin_setting "
            "(workspace,plugin_id,enabled,config_version) VALUES (%s,%s,%s,2) "
            "ON CONFLICT (workspace,plugin_id) DO UPDATE SET "
            "enabled=EXCLUDED.enabled,config_version=lifeweave_plugin_setting.config_version+1,updated_at=now() "
            "WHERE lifeweave_plugin_setting.config_version=%s RETURNING config_version",
            (workspace, identity, enabled, expected_version))
        if not row:
            raise ValueError("插件配置已变化，请刷新后重试")
        return self.detail(workspace, identity)

    def catalog(self, workspace: str) -> dict[str, Any]:
        methods = self._methods(workspace)
        identities = [identity for identity, definition in self.registry.definitions.items()
                      if definition.kind != "skill" or identity in methods]
        return {"items": [{**self.registry.describe(identity), **self._status(workspace, identity, methods)}
                          for identity in identities], "total": len(identities)}

    def detail(self, workspace: str, identity: str) -> dict[str, Any]:
        methods = self._methods(workspace)
        if identity not in self.registry.definitions or (identity.startswith("lifeweave.method.") and identity not in methods):
            raise KeyError(identity)
        definition = self.registry.describe(identity)
        return {**definition, **self._status(workspace, identity, methods),
                "recentCalls": self.host.calls(workspace, plugin_id=identity, limit=20)}

    def require_runnable(self, workspace: str, identity: str, operation: str) -> dict[str, Any]:
        methods = self._methods(workspace)
        self.registry.require(identity, operation)
        status = self._status(workspace, identity, methods)
        if not status["runnable"]:
            raise ValueError(f"插件 {identity} 当前不可用：{status['reason']}")
        return self.registry.describe(identity)

    def method_binding(self, workspace: str, legacy_id: str) -> str:
        identity = f"lifeweave.method.{legacy_id}"
        if identity not in self._methods(workspace):
            raise ValueError(f"工作方法不可用：{legacy_id}")
        self.require_runnable(workspace, identity, "bind")
        return identity

    def require_bound(self, workspace: str, plan_id: str, identity: str, operation: str) -> None:
        self.require_runnable(workspace, identity, operation)
        plan = self.db.fetch_one("SELECT bindings FROM workbench.lifeweave_plugin_plan WHERE workspace=%s AND id=%s",
                                 (workspace, plan_id))
        if not plan:
            raise ValueError("固定插件计划不存在")
        binding = (plan["bindings"] or {}).get(identity)
        definition = self.registry.require(identity)
        if not binding or binding.get("version") != definition.version or \
                binding.get("implementationDigest") != self.registry.digest(definition):
            raise ValueError(f"插件 {identity} 的实现与固定计划不一致，请重新委托")

    def create_development_plan(self, conn: Any, row: dict[str, Any]) -> dict[str, Any]:
        workspace, engine = row["workspace"], row["engine"]
        executor_id = f"lifeweave.execution.{engine}"
        method_id = f"lifeweave.method.{row['method_id']}"
        self.require_runnable(workspace, "lifeweave.development", "plan")
        self.require_runnable(workspace, executor_id, "run")
        self.require_runnable(workspace, method_id, "bind")
        plugin_ids = ("lifeweave.development", "lifeweave.context", "lifeweave.knowledge",
                      method_id, executor_id, "lifeweave.checks.repository")
        bindings = {identity: {"version": self.registry.require(identity).version,
                               "implementationDigest": self.registry.digest(self.registry.require(identity))}
                    for identity in plugin_ids}
        steps = [
            {"id": "plan.development", "stage": "planning", "pluginId": "lifeweave.development", "operation": "plan", "required": True},
            {"id": "plan.context", "stage": "planning", "pluginId": "lifeweave.context", "operation": "compile", "required": True},
            {"id": "plan.recommend", "stage": "planning", "pluginId": "lifeweave.knowledge", "operation": "recommend", "required": True},
            {"id": "plan.method", "stage": "planning", "pluginId": method_id, "operation": "bind", "required": True},
            {"id": "plan.knowledge", "stage": "planning", "pluginId": "lifeweave.knowledge", "operation": "read", "required": bool(row["knowledge_refs"]), "condition": "selected-knowledge"},
            {"id": "plan.codex", "stage": "planning", "pluginId": executor_id, "operation": "run", "required": True},
            {"id": "plan.check", "stage": "planning", "pluginId": "lifeweave.checks.repository", "operation": "verify_readonly", "required": True},
            {"id": "plan.inputs", "stage": "planning", "pluginId": "lifeweave.checks.repository", "operation": "verify_inputs", "required": True},
            {"id": "review.development", "stage": "reviewing", "pluginId": "lifeweave.development", "operation": "review", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "review.context", "stage": "reviewing", "pluginId": "lifeweave.context", "operation": "compile", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "review.recommend", "stage": "reviewing", "pluginId": "lifeweave.knowledge", "operation": "recommend", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "review.method", "stage": "reviewing", "pluginId": method_id, "operation": "bind", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "review.knowledge", "stage": "reviewing", "pluginId": "lifeweave.knowledge", "operation": "read", "required": bool(row["knowledge_refs"]) and row["review_mode"] == "independent", "condition": "independent-review-and-selected-knowledge"},
            {"id": "review.codex", "stage": "reviewing", "pluginId": executor_id, "operation": "run", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "review.check", "stage": "reviewing", "pluginId": "lifeweave.checks.repository", "operation": "verify_readonly", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "review.inputs", "stage": "reviewing", "pluginId": "lifeweave.checks.repository", "operation": "verify_inputs", "required": row["review_mode"] == "independent", "condition": "independent-review"},
            {"id": "implement.development", "stage": "implementing", "pluginId": "lifeweave.development", "operation": "implement", "required": True},
            {"id": "implement.context", "stage": "implementing", "pluginId": "lifeweave.context", "operation": "compile", "required": True},
            {"id": "implement.recommend", "stage": "implementing", "pluginId": "lifeweave.knowledge", "operation": "recommend", "required": True},
            {"id": "implement.method", "stage": "implementing", "pluginId": method_id, "operation": "bind", "required": True},
            {"id": "implement.knowledge", "stage": "implementing", "pluginId": "lifeweave.knowledge", "operation": "read", "required": bool(row["knowledge_refs"]), "condition": "selected-knowledge"},
            {"id": "implement.codex", "stage": "implementing", "pluginId": executor_id, "operation": "run", "required": True},
        ]
        identity = "pplan-" + row["id"][4:]
        conn.execute("INSERT INTO workbench.lifeweave_plugin_plan "
                     "(id,workspace,item_id,assignment_id,version,steps,bindings) VALUES (%s,%s,%s,%s,1,%s,%s)",
                     (identity, workspace, row["item_id"], row["id"], Jsonb(steps), Jsonb(bindings)))
        return {"id": identity, "steps": steps, "bindings": bindings}

    def plan_for_assignment(self, workspace: str, assignment_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one("SELECT * FROM workbench.lifeweave_plugin_plan "
                                 "WHERE workspace=%s AND assignment_id=%s ORDER BY version DESC LIMIT 1",
                                 (workspace, assignment_id))

    def process(self, workspace: str, item_id: str, assignment_id: str | None = None) -> dict[str, Any]:
        self.work.get_item(workspace, item_id)
        if assignment_id:
            plans = self.db.fetch_all("SELECT * FROM workbench.lifeweave_plugin_plan "
                                      "WHERE workspace=%s AND item_id=%s AND assignment_id=%s ORDER BY version",
                                      (workspace, item_id, assignment_id))
            if not plans:
                raise KeyError(assignment_id)
            calls = self.host.calls(workspace, assignment_id=assignment_id, limit=200)
        else:
            plans = self.db.fetch_all("SELECT * FROM workbench.lifeweave_plugin_plan "
                                      "WHERE workspace=%s AND item_id=%s ORDER BY created_at,version", (workspace, item_id))
            calls = self.host.calls(workspace, item_id=item_id, limit=200)
        for plan in plans:
            for step in plan["steps"]:
                matched = [call for call in calls if call["plan_id"] == plan["id"] and call["step_id"] == step["id"]]
                step["observed"] = bool(matched)
                step["callIds"] = [call["id"] for call in matched]
                binding = plan["bindings"].get(step["pluginId"])
                drift = any(not binding or call["plugin_version"] != binding["version"] or
                            call["implementation_digest"] != binding["implementationDigest"] for call in matched)
                step["observation"] = ("binding-drift" if drift else "actual" if matched
                                       else "unknown-truncated" if len(calls) == 200
                                       else "conditional" if not step["required"] else "unobserved")
        return {"itemId": item_id, "plans": plans, "calls": calls,
                "truncated": len(calls) == 200,
                "boundary": "只显示 LifeWeave 受管插件边界的真实调用；未观测不等于没有发生，执行器内部按原生事件另查"}

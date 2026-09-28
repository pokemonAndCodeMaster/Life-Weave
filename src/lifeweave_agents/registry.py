"""Versioned, triggerable Agent configurations composed from installed plugins."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb


CAPABILITIES = {
    "development": ("lifeweave.development", ("managed_development",), "codex"),
    "research": ("lifeweave.research", ("managed_run",), "codex"),
    "general": ("lifeweave.general", ("managed_run",), "codex"),
    "organization": ("lifeweave.item-organization", ("organization",), "builtin"),
}
BUILTINS = {
    "development": ("开发 Agent", "形成方案、审阅并在隔离工作树实施代码", "development"),
    "research": ("研究 Agent", "读取资料并交付本轮研究结果", "research"),
    "general": ("通用 Agent", "处理当前事项中的一般任务", "general"),
    "item-steward": ("事项整理 Agent", "提出或应用有版本保护的事项整理建议", "organization"),
}
ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class AgentRegistry:
    def __init__(self, db: Any, plugins: Any, sources: Any, runtime: Any, local_workers: Any):
        self.db, self.plugins, self.sources = db, plugins, sources
        self.runtime, self.local_workers = runtime, local_workers

    def _method(self, workspace: str, title: str) -> str | None:
        return next((row["id"] for row in self.sources.catalog(workspace)["items"]
                     if row["title"] == title), None)

    def _capability_method(self, workspace: str, capability: str) -> str | None:
        title = {"development": "lifeweave-development", "research": "paper-research"}.get(capability)
        return self._method(workspace, title) if title else None

    def _base(self, workspace: str, identity: str) -> dict[str, Any]:
        name, description, capability = BUILTINS[identity]
        plugin_id, modes, engine = CAPABILITIES[capability]
        method = self._capability_method(workspace, capability)
        return {"id": identity, "name": name, "description": description, "version": 1,
                "capability": capability, "pluginId": plugin_id, "methodId": method,
                "engine": engine, "model": None, "runtime": "native",
                "permission": "read-only", "enabled": True, "modes": list(modes)}

    def _validate(self, value: dict[str, Any]) -> None:
        if not ID.fullmatch(str(value.get("id") or "")):
            raise ValueError("Agent ID 须为 2-64 位小写字母、数字或连字符")
        capability = value.get("capability")
        if capability not in CAPABILITIES:
            raise ValueError("Agent 只能绑定已实现的能力")
        plugin_id, modes, default_engine = CAPABILITIES[capability]
        if value.get("pluginId") != plugin_id or value.get("modes") != list(modes):
            raise ValueError("Agent 能力与插件或触发模式不匹配")
        if value.get("engine") not in ({"builtin"} if default_engine == "builtin" else {"codex", "opencode"}):
            raise ValueError("所选能力不支持此执行器")
        if value.get("runtime") not in {"native", "docker"}:
            raise ValueError("执行方式只能是 native 或 docker")
        if value.get("permission") not in {"read-only", "workspace-write"}:
            raise ValueError("目录权限不正确")
        if not str(value.get("name") or "").strip() or len(value["name"]) > 160:
            raise ValueError("Agent 名称须为 1-160 字")
        if len(str(value.get("description") or "")) > 2000:
            raise ValueError("Agent 描述过长")
        if value.get("methodId"):
            self.sources.snapshot(value["workspace"], value["methodId"], [])
        if value.get("model") and len(str(value["model"])) > 256:
            raise ValueError("模型名称过长")

    def _row(self, workspace: str, identity: str) -> dict[str, Any] | None:
        return self.db.fetch_one("SELECT version,configuration,created_at,updated_at FROM workbench.lifeweave_agent_config "
                                 "WHERE workspace=%s AND id=%s", (workspace, identity))

    def _definition(self, workspace: str, identity: str) -> dict[str, Any]:
        row = self._row(workspace, identity)
        if row:
            value = {**row["configuration"], "id": identity, "version": row["version"]}
        elif identity in BUILTINS:
            value = self._base(workspace, identity)
        else:
            raise KeyError(identity)
        value["workspace"] = workspace
        return value

    def _status(self, workspace: str, value: dict[str, Any]) -> dict[str, Any]:
        plugin = self.plugins.detail(workspace, value["pluginId"])
        engine = value["engine"]
        health = self.runtime.executors[engine].health() if engine != "builtin" else None
        available = bool(value["enabled"] and plugin["runnable"] and (health is None or health.available))
        reason = ("此 Agent 已停用" if not value["enabled"] else
                  plugin["reason"] if not plugin["runnable"] else
                  health.reason if health and not health.available else "可触发；账号和模型以实际运行结果为准")
        if value["capability"] == "development" and engine == "opencode":
            from src.lifeweave.development import OPENCODE_DEVELOPMENT_ENABLED
            if not OPENCODE_DEVELOPMENT_ENABLED:
                available, reason = False, "OpenCode 开发只读边界尚未通过回归，当前不可触发"
        if value.get("methodId"):
            try:
                self.sources.snapshot(workspace, value["methodId"], [])
            except (ValueError, OSError, UnicodeError) as exc:
                available, reason = False, f"方法不可用：{exc}"
        return {"available": available, "reason": reason}

    def get(self, workspace: str, identity: str) -> dict[str, Any]:
        value = self._definition(workspace, identity)
        value.pop("workspace")
        return {**value, **self._status(workspace, value)}

    def catalog(self, workspace: str) -> dict[str, Any]:
        rows = self.db.fetch_all("SELECT id FROM workbench.lifeweave_agent_config WHERE workspace=%s ORDER BY id", (workspace,))
        identities = list(dict.fromkeys([*BUILTINS, *(row["id"] for row in rows)]))
        return {"items": [self.get(workspace, identity) for identity in identities],
                "engines": self.engines(workspace)}

    def engines(self, workspace: str) -> list[dict[str, Any]]:
        result = []
        for identity, label in (("codex", "Codex"), ("opencode", "OpenCode")):
            health = self.runtime.executors[identity].health()
            reason = health.reason or "CLI 已安装；账号和模型以真实运行验证"
            if identity == "opencode":
                from src.lifeweave.development import OPENCODE_DEVELOPMENT_ENABLED
                if not OPENCODE_DEVELOPMENT_ENABLED:
                    reason = "OpenCode 开发任务仍受只读安全边界限制；普通任务实际状态以运行结果为准"
            result.append({"id": identity, "label": label, "available": health.available,
                           "reason": reason, "version": health.version})
        return result

    def environment(self, workspace: str) -> dict[str, Any]:
        # Read presence only. No credential bytes, key names or paths leave here.
        codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        return {"localWorker": self.local_workers.status(workspace),
                "authentication": {
                    "codex": {"kind": "local_cli_account", "configured": (codex_home / "auth.json").is_file() or bool(os.environ.get("OPENAI_API_KEY")),
                              "setup": "在本机 Codex CLI 登录；团队空间须显式启用本机账号或配置执行节点凭据"},
                    "opencode": {"kind": "local_cli_account", "configured": (data_home / "opencode/auth.json").is_file(),
                                 "setup": "在本机 OpenCode CLI 登录；团队空间须显式配置执行节点账号"}},
                "boundary": "只报告本机账号文件或环境凭据是否存在，不验证上游授权；不会读取或返回密钥"}

    def choices(self, workspace: str, item_id: str, work: Any) -> dict[str, Any]:
        item = work.get_item(workspace, item_id)
        preferred = {"requirement": "development", "fix": "development",
                     "research": "research"}.get(item.get("itemType"), "general")
        catalog = self.catalog(workspace)
        return {"itemId": item_id, "recommendedAgentId": preferred,
                "items": catalog["items"], "engines": catalog["engines"],
                "environment": self.environment(workspace)}

    def create(self, workspace: str, body: dict[str, Any]) -> dict[str, Any]:
        identity = body["id"]
        if identity in BUILTINS or self._row(workspace, identity):
            raise ValueError("Agent ID 已存在")
        capability = body["capability"]
        if capability not in CAPABILITIES:
            raise ValueError("Agent 只能绑定已实现的能力")
        plugin_id, modes, engine = CAPABILITIES[capability]
        value = {"id": identity, "name": body["name"], "description": body.get("description") or "",
                 "capability": capability, "pluginId": plugin_id,
                 "methodId": body.get("methodId") or self._capability_method(workspace, capability),
                 "engine": body.get("engine") or engine, "model": body.get("model"),
                 "runtime": body.get("runtime") or "native", "permission": body.get("permission") or "read-only",
                 "enabled": body.get("enabled", True), "modes": list(modes), "workspace": workspace}
        self._validate(value)
        value.pop("workspace")
        self.db.execute("INSERT INTO workbench.lifeweave_agent_config (workspace,id,version,configuration) VALUES (%s,%s,1,%s)",
                        (workspace, identity, Jsonb(value)))
        return self.get(workspace, identity)

    def patch(self, workspace: str, identity: str, version: int, changes: dict[str, Any]) -> dict[str, Any]:
        current = self._definition(workspace, identity)
        if current["version"] != version:
            raise ValueError("Agent 配置版本已变化，请刷新")
        value = {**current, **changes}
        value["id"], value["workspace"] = identity, workspace
        # Capability and its plugin identity are immutable. Register a distinct
        # Agent to bind another existing capability.
        if value["capability"] != current["capability"] or value["pluginId"] != current["pluginId"]:
            raise ValueError("不能改变已有 Agent 的能力绑定")
        self._validate(value)
        value.pop("workspace")
        value.pop("version")
        with self.db.atomic() as conn:
            row = conn.execute("INSERT INTO workbench.lifeweave_agent_config "
                               "(workspace,id,version,configuration) VALUES (%s,%s,2,%s) "
                               "ON CONFLICT (workspace,id) DO UPDATE SET version=lifeweave_agent_config.version+1,"
                               "configuration=EXCLUDED.configuration,updated_at=now() "
                               "WHERE lifeweave_agent_config.version=%s RETURNING version",
                               (workspace, identity, Jsonb(value), version)).fetchone()
            if not row:
                raise ValueError("Agent 配置版本已变化，请刷新")
        return self.get(workspace, identity)

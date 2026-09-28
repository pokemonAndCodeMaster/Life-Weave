"""One launch boundary and a read-only execution view over existing owners."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb


SECRET_KEY = re.compile(r"(?:api[_-]?key|password|secret|authorization|credential|access[_-]?token|refresh[_-]?token)", re.I)
SECRET_TEXT = re.compile(r"(?i)(bearer\s+)[^\s'\"]+|(sk-[A-Za-z0-9_-]{12,})|((?:OPENAI_API_KEY|ANTHROPIC_API_KEY)\s*[=:]\s*)[^\s'\"]+")
SECRET_ASSIGNMENT = re.compile(r"(?i)((?:api[_-]?key|password|secret|authorization|access[_-]?token|refresh[_-]?token)[\"']?\s*[:=]\s*[\"']?)[^\s,;\"'}]+")


def safe(value: Any, *, key: str = "") -> Any:
    """Keep observed structure and order while removing common credential forms."""
    if SECRET_KEY.search(key) and key not in {"credentialSource"}:
        return "[redacted]"
    if isinstance(value, dict):
        return {k: safe(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(entry) for entry in value]
    if isinstance(value, str):
        redacted = SECRET_TEXT.sub(lambda match: (match.group(1) or match.group(3) or "") + "[redacted]", value)
        return SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + "[redacted]", redacted)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class AgentService:
    def __init__(self, db: Any, registry: Any, runtime: Any, development: Any,
                 work: Any, plugin_host: Any, organization: Any = None):
        self.db, self.registry, self.runtime, self.development = db, registry, runtime, development
        self.work, self.plugin_host, self.organization = work, plugin_host, organization

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

    def _launch_row(self, workspace: str, item_id: str, request_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one("SELECT * FROM workbench.lifeweave_agent_launch "
                                 "WHERE workspace=%s AND item_id=%s AND request_id=%s",
                                 (workspace, item_id, request_id))

    def _record(self, workspace: str, item_id: str, request_id: str, fingerprint: str,
                agent: dict[str, Any], config: dict[str, Any], kind: str, reference_id: str) -> None:
        self.db.execute("INSERT INTO workbench.lifeweave_agent_launch "
                        "(id,workspace,item_id,request_id,request_fingerprint,agent_id,agent_version,"
                        "configuration_snapshot,kind,reference_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (workspace,item_id,request_id) DO NOTHING",
                        ("alaunch-" + uuid4().hex[:24], workspace, item_id, request_id, fingerprint,
                         agent["id"], agent["version"], Jsonb(config), kind, reference_id))

    def _configuration(self, agent: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        return {"agentId": agent["id"], "agentName": agent["name"], "agentVersion": agent["version"],
                "capability": agent["capability"], "pluginId": agent["pluginId"],
                "engine": body.get("engine") or agent["engine"], "model": body.get("model") if body.get("model") is not None else agent.get("model"),
                "runtime": body.get("runtime") or agent.get("runtime") or "native",
                "permission": body.get("permission") or agent.get("permission") or "read-only",
                "methodId": body.get("methodId") if body.get("_preserveLegacyMethod") else
                            body.get("methodId") if body.get("methodId") is not None else agent.get("methodId"),
                "knowledgeRefs": body["knowledgeRefs"] if "knowledgeRefs" in body else None}

    def dispatch(self, workspace: str, item_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self.work.get_item(workspace, item_id)
        request_id = body["requestId"]
        fingerprint = self._fingerprint(body)
        with self.db.atomic() as conn:
            conn.execute("SELECT id FROM workbench.t_lifeweave_item WHERE workspace_key=%s AND id=%s FOR UPDATE",
                         (workspace, item_id)).fetchone()
            existing = self._launch_row(workspace, item_id, request_id)
            if existing:
                if existing["request_fingerprint"] != fingerprint:
                    raise ValueError("此请求身份已用于不同任务")
                return self.execution_ref(workspace, existing["kind"], existing["reference_id"])
            agent = self.registry.get(workspace, body["agentId"])
            if not agent["enabled"]:
                raise ValueError("此 Agent 已停用")
            mode = body["mode"]
            if mode not in agent["modes"]:
                raise ValueError("Agent 不支持所选触发模式")
            config = self._configuration(agent, body)
            if config["engine"] not in ({"builtin"} if mode == "organization" else {"codex", "opencode"}):
                raise ValueError("执行器与 Agent 能力不匹配")
            plugin = self.registry.plugins.detail(workspace, agent["pluginId"])
            if not plugin["runnable"]:
                raise ValueError(plugin["reason"])
            if config["engine"] != "builtin":
                health = self.runtime.executors[config["engine"]].health()
                if not health.available:
                    raise ValueError(health.reason or "所选执行器不可用")
            if mode == "managed_development" and config["engine"] == "opencode":
                choice = self.development.choices(workspace, item_id)["executors"]["opencode"]
                if not choice["available"]:
                    raise ValueError(choice["reason"])
            if mode == "managed_development" and config["runtime"] != "native":
                raise ValueError("开发组合当前只支持本机隔离工作树")
            if mode == "managed_development":
                if not body.get("instruction") or not body.get("repositoryPath"):
                    raise ValueError("开发委托须说明任务并选择 Git 仓库")
                result = self.development.create(
                    workspace, item_id=item_id, request_id=request_id,
                    instruction=body["instruction"], repository_path=body["repositoryPath"],
                    engine=config["engine"], model=config["model"], method_id=config["methodId"],
                    knowledge_refs=config["knowledgeRefs"], review_mode=body.get("reviewMode") or "independent",
                    execution_scope=body.get("executionScope") or "plan_only",
                    acknowledge_excluded_changes=bool(body.get("acknowledgeExcludedChanges")),
                    step_id=body.get("stepId"), plan_version=body.get("planVersion"))
                kind, reference_id = "managed_development", result["id"]
                config.update({"methodId": result["methodId"], "knowledgeRefs": result["knowledgeRefs"],
                               "inputVersions": result["inputVersions"],
                               "repositoryRevision": result["repositoryRevision"]})
            elif mode == "managed_run":
                if not body.get("instruction"):
                    raise ValueError("委托内容不能为空")
                if config["runtime"] == "docker" and not body.get("image"):
                    raise ValueError("Docker 运行须选择已登记镜像")
                def run() -> dict[str, Any]:
                    return self.runtime.create_run(
                        workspace, item_id=item_id, instruction=body["instruction"],
                        engine=config["engine"], model=config["model"], runtime=config["runtime"],
                        image=body.get("image"), directory=body.get("repositoryPath") or body.get("directory"),
                        branch=body.get("branch"), permission=config["permission"],
                        method_id=config["methodId"], knowledge_refs=config["knowledgeRefs"] or [],
                        machine_id=body.get("machineId"),
                        capability_candidate_id=body.get("capabilityCandidateId"),
                        actor_id=body.get("actorId") or "agent-center")
                result = self.plugin_host.invoke(
                    agent["pluginId"], "run", workspace=workspace, item_id=item_id,
                    input_ref={"agentId": agent["id"], "agentVersion": agent["version"]},
                    handler=run, output_ref=lambda row: {"runId": row["id"]}, accepted=True)
                kind, reference_id = "managed_run", result["id"]
                run_snapshot = self.runtime.get_run_snapshot(workspace, reference_id)
                selected_inputs = (run_snapshot.get("environment_snapshot") or {}).get("selectedInputs") or {}
                config.update({"methodId": selected_inputs.get("methodId"),
                               "knowledgeRefs": selected_inputs.get("knowledgeRefs") or [],
                               "inputVersions": [{"id": entry.get("id"), "version": entry.get("version"),
                                                  "sourcePath": entry.get("sourcePath")}
                                                 for entry in run_snapshot.get("capability_snapshot") or []],
                               "repositoryRevision": run_snapshot.get("repository_revision")})
            else:
                if self.organization is None:
                    raise ValueError("事项整理服务尚未接入")
                selection = body.get("organization") or {}
                action = selection.get("action")
                if action == "propose":
                    from src.lifeweave.item_organization_models import OrganizationProposalInput
                    payload = OrganizationProposalInput.model_validate({
                        "requestId": request_id, "itemIds": selection.get("itemIds") or [item_id],
                        "reason": body.get("instruction") or "由事项整理 Agent 提出建议"})
                    result = self.plugin_host.invoke(
                        agent["pluginId"], "propose", workspace=workspace, item_id=item_id,
                        input_ref={"itemIds": selection.get("itemIds") or [item_id]},
                        handler=lambda: self.organization.propose(workspace, payload, "agent-center"),
                        output_ref=lambda row: {"proposalId": row["id"]})
                elif action == "apply" and selection.get("proposalId"):
                    result = self.plugin_host.invoke(
                        agent["pluginId"], "apply", workspace=workspace, item_id=item_id,
                        input_ref={"proposalId": selection["proposalId"]},
                        handler=lambda: self.organization.apply(workspace, selection["proposalId"], request_id, "agent-center"),
                        output_ref=lambda row: {"proposalId": row["id"], "status": row["status"]})
                else:
                    raise ValueError("事项整理须选择 propose 或提供建议 ID 后 apply")
                kind, reference_id = "organization", result["id"]
                config.update({"operation": action,
                               "inputSnapshot": safe({"organization": selection,
                                                      "instruction": body.get("instruction")}),
                               "outputSnapshot": safe(result)})
            self._record(workspace, item_id, request_id, fingerprint, agent, config, kind, reference_id)
        return self.execution_ref(workspace, kind, reference_id)

    def legacy_development(self, workspace: str, payload: Any) -> dict[str, Any]:
        """Keep the old response while routing through the same launch receipt."""
        body = payload.model_dump()
        earlier = self.db.fetch_one("SELECT id FROM workbench.lifeweave_development_assignment "
                                    "WHERE workspace=%s AND item_id=%s AND request_id=%s",
                                    (workspace, body["itemId"], body["requestId"]))
        if earlier and not self._launch_row(workspace, body["itemId"], body["requestId"]):
            # Preserve the owner's pre-registry request fingerprint, including
            # the distinction between unspecified and explicit method/knowledge.
            return self.development.create(
                workspace, item_id=body["itemId"], request_id=body["requestId"],
                instruction=body["instruction"], repository_path=body["repositoryPath"],
                engine=body["engine"], model=body["model"], method_id=body["methodId"],
                knowledge_refs=body["knowledgeRefs"], review_mode=body["reviewMode"],
                execution_scope=body["executionScope"],
                acknowledge_excluded_changes=body["acknowledgeExcludedChanges"],
                step_id=body["stepId"], plan_version=body["planVersion"])
        body.update({"agentId": "development", "mode": "managed_development"})
        ref = self.dispatch(workspace, body.pop("itemId"), body)
        return self.development.get(workspace, ref["id"])

    def legacy_run(self, workspace: str, payload: Any) -> dict[str, Any]:
        body = payload.model_dump()
        item_id = body.pop("item_id")
        item = self.work.get_item(workspace, item_id)
        agent_id = "research" if item.get("itemType") == "research" else "general"
        ref = self.dispatch(workspace, item_id, {
            "requestId": "legacy-run:" + uuid4().hex, "agentId": agent_id, "mode": "managed_run",
            "instruction": body["instruction"], "engine": body["engine"], "model": body.get("model"),
            "runtime": body.get("runtime"), "image": body.get("image"),
            "repositoryPath": body.get("directory"), "branch": body.get("branch"),
            "permission": body.get("permission"), "methodId": body.get("method_id"),
            "knowledgeRefs": body.get("knowledge_refs"),
            "machineId": body.get("machine_id"), "capabilityCandidateId": body.get("capability_candidate_id"),
            "actorId": "admin", "_preserveLegacyMethod": True,
        })
        return self.runtime.get_run(workspace, ref["id"])

    def external_start(self, request: Any, workspace: str, item_id: str, body: Any) -> dict[str, Any]:
        """Register an already running session; never start another model task."""
        from src.lifeweave.external_development import start_core
        with self.db.atomic():
            prior = self._launch_row(workspace, item_id, body.requestId)
            fingerprint = self._fingerprint(body.model_dump())
            if prior and (prior["kind"] != "external_session" or prior["request_fingerprint"] != fingerprint):
                raise ValueError("此请求身份已用于不同任务")
            result = start_core(request, workspace, item_id, body)
            agent = self.registry.get(workspace, "development")
            payload = result["event"].get("payload") or {}
            config = {"agentId": "development", "agentName": agent["name"],
                      "agentVersion": agent["version"],
                      "pluginId": agent["pluginId"], "engine": "codex",
                      "methodId": payload.get("methodId"), "declaredInputs": payload.get("declaredInputs") or [],
                      "nativeSessionId": payload.get("nativeSessionId"),
                      "observation": "External Codex session linked by user; no managed Run launched"}
            self._record(workspace, item_id, body.requestId,
                         fingerprint, agent, config,
                         "external_session", result["sessionId"])
        return result

    def _receipt(self, workspace: str, kind: str, reference_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one("SELECT * FROM workbench.lifeweave_agent_launch "
                                 "WHERE workspace=%s AND kind=%s AND reference_id=%s "
                                 "ORDER BY created_at DESC,id DESC LIMIT 1",
                                 (workspace, kind, reference_id))

    def _launches(self, workspace: str, kind: str, reference_id: str) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM workbench.lifeweave_agent_launch "
                                 "WHERE workspace=%s AND kind=%s AND reference_id=%s "
                                 "ORDER BY created_at,id", (workspace, kind, reference_id))

    def _reference(self, workspace: str, kind: str, reference_id: str) -> dict[str, Any]:
        launch = self._receipt(workspace, kind, reference_id)
        organization_launches = self._launches(workspace, kind, reference_id) if kind == "organization" else []
        if kind == "managed_development":
            row = self.development.get(workspace, reference_id)
            item_id, status = row["itemId"], row["status"]
            created, updated = row["createdAt"], row["updatedAt"]
            engine, model = row["engine"], row["model"]
            children = [row[key] for key in ("planRunId", "reviewRunId", "implementationRunId") if row.get(key)]
            title, failure = row["instruction"][:160], row.get("error")
        elif kind == "managed_run":
            row = self.runtime.get_run_snapshot(workspace, reference_id)
            item_id, status = row["item_id"], row["state"]
            created, updated = row["created_at"], row["updated_at"]
            engine, model = row["engine"], row["model"]
            children = []
            title, failure = str(row["instruction"])[:160], row.get("error")
            parent = self.db.fetch_one(
                "SELECT id FROM workbench.lifeweave_development_assignment WHERE workspace=%s "
                "AND %s IN (plan_run_id,review_run_id,implementation_run_id)",
                (workspace, reference_id))
        elif kind == "external_session":
            # The existing external owner validates both workspace and item.
            activity = self.db.fetch_one(
                "SELECT * FROM workbench.t_lifeweave_activity WHERE workspace_key=%s "
                "AND kind='external_development_start' AND payload->>'sessionId'=%s",
                (workspace, reference_id))
            if not activity:
                raise KeyError(reference_id)
            item_id = activity["item_id"]
            events = [row for row in self.work.repository.list_activities(workspace, item_id)
                      if row["payload"].get("sessionId") == reference_id]
            status = ("blocked" if any(row["kind"] == "external_development_event" and
                                       row["payload"].get("phase") == "blocked" for row in events) else
                      "finished" if any(row["kind"] == "external_development_event" and
                                        row["payload"].get("phase") == "finished" for row in events) else
                      "reported" if len(events) > 1 else "started")
            created = activity["created_at"]
            updated = max((row["createdAt"] for row in events), default=created)
            engine, model = "codex", None
            children = []
            title, failure = activity["body"][:160], None
        elif kind == "organization":
            if not organization_launches:
                raise KeyError(reference_id)
            launch = organization_launches[0]
            row = self.organization.get_proposal(workspace, reference_id)
            item_id, status = launch["item_id"], row["status"]
            created, updated = launch["created_at"], row.get("appliedAt") or launch["created_at"]
            engine, model, children = "builtin", None, []
            title, failure = row.get("reason") or "事项整理", None
        else:
            raise KeyError(kind)
        parent_launch = self._receipt(workspace, "managed_development", parent["id"]) if kind == "managed_run" and parent else None
        agent_id = (launch["agent_id"] if launch else
                    parent_launch["agent_id"] if parent_launch else
                    "development" if kind == "managed_run" and parent else
                    "development" if kind in {"managed_development", "external_session"} else
                    "research" if self.work.get_item(workspace, item_id).get("itemType") == "research" else "general")
        agent_name = ((launch or parent_launch)["configuration_snapshot"].get("agentName")
                      if launch or parent_launch else None)
        if not agent_name:
            try:
                agent_name = self.registry.get(workspace, agent_id)["name"]
            except KeyError:
                agent_name = agent_id
        if kind == "external_session":
            coverage = ("bound_hook_partial" if any(row["kind"] == "external_development_hook" for row in events)
                        else "reported_only")
        else:
            coverage = "managed_events" if kind in {"managed_development", "managed_run"} else "platform_action"
        item_ids = [item_id]
        if organization_launches:
            for entry in organization_launches:
                item_ids.append(entry["item_id"])
                selection = (entry["configuration_snapshot"].get("inputSnapshot") or {}).get("organization") or {}
                item_ids.extend(selection.get("itemIds") or [])
            item_ids.extend(change["itemId"] for change in row.get("changes") or [])
            for group in row.get("groups") or []:
                item_ids.extend(group.get("itemIds") or [])
        return {"kind": kind, "id": reference_id, "itemId": item_id,
                "itemIds": list(dict.fromkeys(item_ids)),
                "agentId": agent_id, "agentName": agent_name,
                "agentIds": list(dict.fromkeys(entry["agent_id"] for entry in organization_launches)) if organization_launches else [agent_id],
                "agentIdentity": "registered" if launch else "parent_assignment" if parent_launch else "inferred",
                "status": status, "createdAt": created.isoformat() if isinstance(created, datetime) else created,
                "updatedAt": updated.isoformat() if isinstance(updated, datetime) else updated,
                "engine": engine, "model": model, "runIds": children,
                "traceCoverage": coverage, "title": title, "error": safe(failure) if failure else None,
                "parentExecution": {"kind": "managed_development", "id": parent["id"]} if kind == "managed_run" and parent else None}

    def execution_ref(self, workspace: str, kind: str, reference_id: str) -> dict[str, Any]:
        return self._reference(workspace, kind, reference_id)

    def executions(self, workspace: str, *, agent_id: str | None = None,
                   item_id: str | None = None, status: str | None = None,
                   limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if workspace not in {"personal", "team"} or not 1 <= limit <= 100 or offset < 0:
            raise ValueError("执行目录查询参数不正确")
        # The canonical owners are queried directly; launch receipts only add
        # configuration identity. Stage Runs are excluded from top-level rows.
        rows = self.db.fetch_all("""
            SELECT 'managed_development' AS kind,id AS reference_id,item_id,created_at
              FROM workbench.lifeweave_development_assignment WHERE workspace=%s
            UNION ALL
            SELECT 'managed_run',r.id,r.item_id,r.created_at
              FROM workbench.t_lifeweave_run r WHERE r.workspace=%s
                AND NOT EXISTS (SELECT 1 FROM workbench.lifeweave_development_assignment d
                  WHERE d.workspace=r.workspace AND r.id IN (d.plan_run_id,d.review_run_id,d.implementation_run_id))
            UNION ALL
            SELECT 'external_session',a.payload->>'sessionId',a.item_id,a.created_at
              FROM workbench.t_lifeweave_activity a WHERE a.workspace_key=%s
                AND a.kind='external_development_start'
            UNION ALL
            SELECT 'organization',l.reference_id,MIN(l.item_id),MIN(l.created_at)
              FROM workbench.lifeweave_agent_launch l WHERE l.workspace=%s AND l.kind='organization'
              GROUP BY l.reference_id
            ORDER BY created_at DESC,reference_id DESC
        """, (workspace, workspace, workspace, workspace))
        refs = []
        for row in rows:
            ref = self._reference(workspace, row["kind"], row["reference_id"])
            if item_id and item_id not in ref["itemIds"]:
                continue
            if agent_id and agent_id not in ref["agentIds"]:
                continue
            if status and ref["status"] != status:
                continue
            refs.append(ref)
        return {"items": refs[offset:offset + limit], "total": len(refs),
                "limit": limit, "offset": offset}

    def _run_events(self, workspace: str, run_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        after = 0
        while True:
            page = self.runtime.events(workspace, run_id, after_sequence=after, limit=200)
            for row in page:
                events.append({"id": str(row["id"]), "source": row["source"],
                               "observed": "native" if row["source"] in {"codex", "opencode"} else "platform",
                               "eventType": row["event_type"], "summary": safe(row["summary"]),
                               "occurredAt": row["occurred_at"].isoformat(),
                               "sequence": row["sequence"], "runId": run_id,
                               "channel": row.get("channel"), "payload": safe(row["payload"])})
            if len(page) < 200:
                return events
            after = page[-1]["sequence"]

    def detail(self, workspace: str, kind: str, reference_id: str) -> dict[str, Any]:
        execution = self._reference(workspace, kind, reference_id)
        launch = self._receipt(workspace, kind, reference_id)
        launches = self._launches(workspace, kind, reference_id) if kind == "organization" else []
        if launches:
            launch = launches[0]
        if kind == "managed_run" and not launch and execution.get("parentExecution"):
            launch = self._receipt(workspace, "managed_development", execution["parentExecution"]["id"])
        configuration = safe(launch["configuration_snapshot"]) if launch else {
            "agentId": execution["agentId"], "identity": "inferred from existing owner record"}
        item_id = execution["itemId"]
        events: list[dict[str, Any]] = []
        inputs: dict[str, Any] = {}
        outputs: list[dict[str, Any]] = []
        children: list[dict[str, Any]] = []
        if kind == "managed_development":
            row = self.development.get(workspace, reference_id)
            inputs = safe({key: row.get(key) for key in ("instruction", "repositoryPath", "repositoryRevision",
                           "contextVersionId", "methodId", "knowledgeRefs", "inputVersions", "reviewMode", "executionScope")})
            for stage, key in (("plan", "planRunId"), ("review", "reviewRunId"), ("implementation", "implementationRunId")):
                if row.get(key):
                    run_id = row[key]
                    children.append({"stage": stage, "kind": "managed_run", "id": run_id,
                                     "status": self.runtime.get_run_snapshot(workspace, run_id)["state"]})
                    events.extend(self._run_events(workspace, run_id))
            if row.get("plan"):
                outputs.append({"kind": "plan", "content": safe(row["plan"]), "sha256": row.get("planSha256")})
            if row.get("review"):
                outputs.append({"kind": "review", "content": safe(row["review"]), "decision": row.get("reviewDecision")})
            try:
                delivery = self.development.delivery(workspace, reference_id)
            except (ValueError, KeyError):
                delivery = None
            if delivery:
                outputs.append({"kind": "delivery", "id": delivery["id"],
                                "artifactSha256": delivery["artifactSha256"]})
            calls = self.db.fetch_all("SELECT * FROM workbench.lifeweave_plugin_call "
                                      "WHERE workspace=%s AND assignment_id=%s ORDER BY started_at,id",
                                      (workspace, reference_id))
        elif kind == "managed_run":
            row = self.runtime.get_run_snapshot(workspace, reference_id)
            inputs = safe({"instruction": row["instruction"], "promptSnapshot": row["prompt_snapshot"],
                           "contextVersionId": row["context_version_id"],
                           "repositoryPath": row["repository_path"], "repositoryRevision": row["repository_revision"],
                           "capabilities": [{key: entry.get(key) for key in ("id", "version", "sourcePath", "target")}
                                            for entry in row["capability_snapshot"] or []],
                           "environment": row["environment_snapshot"]})
            events = self._run_events(workspace, reference_id)
            if row.get("result"):
                outputs.append({"kind": "result", "content": safe(row["result"])})
            outputs.extend(safe(row.get("artifact_candidates") or []))
            calls = self.db.fetch_all("SELECT * FROM workbench.lifeweave_plugin_call "
                                      "WHERE workspace=%s AND run_id=%s ORDER BY started_at,id",
                                      (workspace, reference_id))
        elif kind == "external_session":
            activities = [row for row in self.work.repository.list_activities(workspace, item_id)
                          if row["payload"].get("sessionId") == reference_id]
            start = next(row for row in activities if row["kind"] == "external_development_start")
            inputs = safe({"observedGit": start["payload"].get("observedGit"),
                           "declaredInputs": start["payload"].get("declaredInputs"),
                           "methodId": start["payload"].get("methodId"),
                           "nativeSessionId": start["payload"].get("nativeSessionId"),
                           "stepId": start["payload"].get("stepId"), "planVersion": start["payload"].get("planVersion")})
            for row in activities:
                events.append({"id": row["id"], "source": "codex_hook" if row["kind"] == "external_development_hook" else "external_report",
                               "observed": "native" if row["kind"] == "external_development_hook" else "reported",
                               "eventType": row["kind"], "summary": safe(row["body"]),
                               "occurredAt": row["createdAt"].isoformat() if isinstance(row["createdAt"], datetime) else row["createdAt"],
                               "payload": safe(row["payload"])})
            fixed = self.db.fetch_all(
                "SELECT id,title,payload FROM workbench.t_lifeweave_entity WHERE workspace_key=%s "
                "AND payload->'fixedDelivery'->>'sessionId'=%s ORDER BY created_at,id",
                (workspace, reference_id))
            outputs = [{"kind": "delivery", "id": row["id"], "title": row["title"],
                        "version": row["payload"]["fixedDelivery"]["sha256"]} for row in fixed]
            calls = []
        else:
            proposal = self.organization.get_proposal(workspace, reference_id)
            inputs = {"proposalId": reference_id}
            outputs = [{"kind": "organization_proposal", "proposal": safe(proposal)}]
            calls = self.db.fetch_all("SELECT * FROM workbench.lifeweave_plugin_call "
                                      "WHERE workspace=%s AND output_ref->>'proposalId'=%s "
                                      "ORDER BY started_at,id", (workspace, reference_id))
        for row in calls:
            events.append({"id": row["id"], "source": "plugin", "observed": "platform",
                           "eventType": row["operation"], "summary": f"{row['plugin_id']} · {row['state']}",
                           "occurredAt": row["started_at"].isoformat(),
                           "payload": safe({"pluginId": row["plugin_id"], "pluginVersion": row["plugin_version"],
                                            "state": row["state"], "inputRef": row["input_ref"],
                                            "outputRef": row["output_ref"], "error": row["error"]})})
        events.sort(key=lambda value: (value["occurredAt"], value.get("runId") or "", value.get("sequence") or 0, value["id"]))
        missing = (["第三方私有推理与未输出的内部动作无法采集"] if kind in {"managed_development", "managed_run"} else
                   ["Hook 未收到；工具输入与输出未采集", "阶段和检查由本机会话主动报告"] if execution["traceCoverage"] == "reported_only" else
                   ["Hook 只覆盖实际收到的事件；工具输入与输出未采集", "阶段和检查由本机会话主动报告"] if kind == "external_session" else
                   ["整理服务只记录提议、应用及插件调用边界"])
        coverage = {"level": execution["traceCoverage"], "description": "只展示实际保存的事件；历史缺口不能重建",
                    "missing": missing, "eventCount": len(events)}
        links = {"item": f"/lifeweave/{workspace}/items/{item_id}/overview"}
        if kind == "managed_development":
            links["development"] = f"/api/lifeweave/{workspace}/development/{reference_id}"
        elif kind == "managed_run":
            links["run"] = f"/api/lifeweave/{workspace}/runs/{reference_id}"
        elif kind == "external_session":
            links["external"] = f"/api/lifeweave/{workspace}/items/{item_id}/external-development/sessions"
        recorded_launches = [{"id": row["id"], "requestId": row["request_id"],
                              "itemId": row["item_id"], "agentId": row["agent_id"],
                              "agentName": row["configuration_snapshot"].get("agentName") or row["agent_id"],
                              "agentVersion": row["agent_version"],
                              "operation": row["configuration_snapshot"].get("operation"),
                              "configuration": safe({key: value for key, value in row["configuration_snapshot"].items()
                                                     if key not in {"inputSnapshot", "outputSnapshot"}}),
                              "input": safe(row["configuration_snapshot"].get("inputSnapshot")),
                              "output": safe(row["configuration_snapshot"].get("outputSnapshot")),
                              "createdAt": row["created_at"].isoformat()}
                             for row in launches]
        return {"execution": execution, "configuration": configuration, "inputs": inputs,
                "events": events, "outputs": outputs, "children": children,
                "launches": recorded_launches, "coverage": coverage, "links": links}

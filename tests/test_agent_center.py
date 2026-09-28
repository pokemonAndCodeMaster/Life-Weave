"""The Agent center reads the same owners as the established launch routes."""
from __future__ import annotations

from test_live_database import dedicated_client, post


BASE = "/api/lifeweave/personal"


def test_registry_dispatch_snapshot_idempotency_and_trace(dedicated_client):
    client = dedicated_client
    item = post(client, "/items", {"itemType": "research", "title": "研究执行归总",
                                   "payload": {"goal": "查看同一 Agent 的真实执行"}})
    catalog = client.get(BASE + "/agents").json()
    assert {row["id"] for row in catalog["items"]} >= {
        "development", "research", "general", "item-steward"}
    assert client.get(BASE + f"/items/{item['id']}/agent-choices").json()["recommendedAgentId"] == "research"
    assert client.get(BASE + f"/items/{item['id']}/agent-choices").json()["environment"]["authentication"]["codex"]["kind"] == "local_cli_account"

    created = client.post(BASE + "/agents", json={
        "id": "study-helper", "name": "研究助手", "capability": "research",
        "description": "交付指定研究结果"})
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["pluginId"] == "lifeweave.research"
    assert first["methodId"] == next(row["methodId"] for row in catalog["items"] if row["id"] == "research")
    dispatched = client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "study-once", "agentId": "study-helper", "mode": "managed_run",
        "instruction": "阅读材料并说明结论", "engine": "codex"})
    assert dispatched.status_code == 202, dispatched.text
    ref = dispatched.json()
    assert ref["kind"] == "managed_run" and ref["agentId"] == "study-helper"
    assert client.get(BASE + "/agent-executions", params={"itemId": item["id"]}).json()["total"] == 1
    detail = client.get(BASE + f"/agent-executions/managed_run/{ref['id']}").json()
    assert detail["configuration"]["agentId"] == "study-helper"
    assert detail["inputs"]["contextVersionId"]
    assert detail["coverage"]["level"] == "managed_events"
    assert any(row["eventType"] == "run.queued" for row in detail["events"])

    changed = client.patch(BASE + "/agents/study-helper", json={"version": 1, "name": "研究助手二版", "enabled": False})
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    # An exact retry returns the original receipt even after defaults and
    # availability changed. Different content under the same key conflicts.
    assert client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "study-once", "agentId": "study-helper", "mode": "managed_run",
        "instruction": "阅读材料并说明结论", "engine": "codex"}).json()["id"] == ref["id"]
    assert client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "study-once", "agentId": "study-helper", "mode": "managed_run",
        "instruction": "另一项任务"}).status_code == 409
    detail_after = client.get(BASE + f"/agent-executions/managed_run/{ref['id']}").json()
    assert detail_after["configuration"]["agentVersion"] == 1
    assert client.get("/api/lifeweave/team/agent-executions", params={"itemId": item["id"]}).json()["total"] == 0

    db = client.app.state.database_manager.postgres()
    db.execute("UPDATE workbench.t_lifeweave_run SET state='unavailable',error=%s WHERE id=%s",
               ("Bearer hidden-secret", ref["id"]))
    client.app.state.lifeweave_runtime_service.repository.append_event(
        workspace="personal", run_id=ref["id"], event_type="executor.diagnostic",
        source="codex", channel="stderr", summary="OPENAI_API_KEY=hidden-secret",
        payload={"authorization": "Bearer hidden-secret", "message": "sk-1234567890abcdefghijkl"})
    terminal = client.get(BASE + f"/agent-executions/managed_run/{ref['id']}")
    assert terminal.status_code == 200
    assert terminal.json()["execution"]["status"] == "unavailable"
    assert "hidden-secret" not in terminal.text and "sk-1234567890" not in terminal.text


def test_legacy_run_and_external_session_are_visible_without_duplicate_run(dedicated_client, tmp_path):
    client = dedicated_client
    item = post(client, "/items", {"itemType": "fix", "title": "旧入口归总"})
    old = client.post(BASE + "/runs", json={"itemId": item["id"], "instruction": "核对现状", "engine": "codex"})
    assert old.status_code == 202, old.text
    run_id = old.json()["id"]
    rows = client.get(BASE + "/agent-executions", params={"itemId": item["id"]}).json()
    assert rows["total"] == 1 and rows["items"][0]["id"] == run_id
    assert rows["items"][0]["agentId"] == "general"
    assert client.get(BASE + f"/agent-executions/managed_run/{run_id}").json()["configuration"]["methodId"] is None
    research = post(client, "/items", {"itemType": "research", "title": "旧研究 Run"})
    research_run = client.post(BASE + "/runs", json={"itemId": research["id"],
                                                      "instruction": "核对资料", "engine": "codex"})
    assert research_run.status_code == 202, research_run.text
    research_detail = client.get(BASE + f"/agent-executions/managed_run/{research_run.json()['id']}").json()
    assert research_detail["execution"]["agentId"] == "research"
    assert research_detail["configuration"]["methodId"] is None

    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "file.txt").write_text("original\n")
    subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "baseline"], check=True)
    start = client.post(BASE + f"/items/{item['id']}/external-development/sessions", json={
        "requestId": "bound-external", "repositoryPath": str(repo), "summary": "现有 Codex 会话记录"})
    assert start.status_code == 201, start.text
    session = start.json()["sessionId"]
    listing_response = client.get(BASE + "/agent-executions", params={"itemId": item["id"]})
    assert listing_response.status_code == 200, listing_response.text
    listing = listing_response.json()
    assert listing["total"] == 2
    external = client.get(BASE + f"/agent-executions/external_session/{session}").json()
    assert external["execution"]["traceCoverage"] == "reported_only"
    assert external["coverage"]["missing"]
    assert all(row["observed"] == "reported" for row in external["events"])


def test_item_steward_uses_organization_owner_and_keeps_proposal_trace(dedicated_client):
    client = dedicated_client
    item = post(client, "/items", {"itemType": "other", "title": "待整理工作"})
    response = client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "organize-once", "agentId": "item-steward", "mode": "organization",
        "organization": {"action": "propose", "itemIds": [item["id"]]}})
    assert response.status_code == 202, response.text
    execution = response.json()
    assert execution["kind"] == "organization" and execution["status"] == "proposed"
    detail = client.get(BASE + f"/agent-executions/organization/{execution['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["outputs"][0]["proposal"]["id"] == execution["id"]
    assert any(row["source"] == "plugin" for row in detail.json()["events"])
    second = client.post(BASE + "/agents", json={"id": "steward-reviewer", "name": "整理复核",
                                                  "capability": "organization"})
    assert second.status_code == 201, second.text
    applied = client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "apply-once", "agentId": "steward-reviewer", "mode": "organization",
        "organization": {"action": "apply", "proposalId": execution["id"]}})
    assert applied.status_code == 202, applied.text
    assert applied.json()["status"] == "applied"
    detail = client.get(BASE + f"/agent-executions/organization/{execution['id']}").json()
    assert detail["execution"]["agentId"] == "item-steward"
    assert detail["execution"]["agentIds"] == ["item-steward", "steward-reviewer"]
    assert [entry["operation"] for entry in detail["launches"]] == ["propose", "apply"]
    assert [entry["agentId"] for entry in detail["launches"]] == ["item-steward", "steward-reviewer"]
    assert [entry["output"]["status"] for entry in detail["launches"]] == ["proposed", "applied"]
    assert [entry["configuration"]["agentVersion"] for entry in detail["launches"]] == [1, 1]
    filtered = client.get(BASE + "/agent-executions", params={"agentId": "steward-reviewer"}).json()
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == execution["id"]
    replay = client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "organize-once", "agentId": "item-steward", "mode": "organization",
        "organization": {"action": "propose", "itemIds": [item["id"]]}})
    assert replay.status_code == 202 and replay.json()["id"] == execution["id"]
    assert len(client.get(BASE + f"/agent-executions/organization/{execution['id']}").json()["launches"]) == 2


def test_development_stage_run_is_child_not_second_top_level_execution(dedicated_client, tmp_path):
    import subprocess
    client = dedicated_client
    item = post(client, "/items", {"itemType": "fix", "title": "开发步骤归总"})
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "README.md").write_text("baseline\n")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "baseline"], check=True)
    client.app.state.development.project_root = repo.resolve()
    started = client.post(BASE + f"/items/{item['id']}/agent-dispatch", json={
        "requestId": "dev-first", "agentId": "development", "mode": "managed_development",
        "instruction": "说明并修复 README 中的工作入口", "repositoryPath": str(repo),
        "executionScope": "plan_only", "reviewMode": "self"})
    assert started.status_code == 202, started.text
    assignment = started.json()
    assert assignment["kind"] == "managed_development"
    assert len(assignment["runIds"]) == 1
    from src.lifeweave.development import DEFAULT_PROJECT_REFS
    detail = client.get(BASE + f"/agent-executions/managed_development/{assignment['id']}").json()
    assert detail["configuration"]["knowledgeRefs"] == DEFAULT_PROJECT_REFS
    assert detail["inputs"]["knowledgeRefs"] == DEFAULT_PROJECT_REFS
    top = client.get(BASE + "/agent-executions", params={"itemId": item["id"]}).json()
    assert top["total"] == 1 and top["items"][0]["id"] == assignment["id"]
    child = client.get(BASE + f"/agent-executions/managed_run/{assignment['runIds'][0]}")
    assert child.status_code == 200, child.text
    assert child.json()["execution"]["agentId"] == "development"
    assert child.json()["execution"]["parentExecution"]["id"] == assignment["id"]

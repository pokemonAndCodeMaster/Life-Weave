"""Plugin process must reflect fixed intent and lease-validated calls, not labels."""
from pathlib import Path

import pytest

from test_live_database import dedicated_client, post
from test_development import repository
from src.lifeweave_plugins.core import PluginDefinition, PluginRegistry


def test_registry_rejects_missing_dependencies_and_cycles(tmp_path: Path):
    with pytest.raises(ValueError, match="不存在"):
        PluginRegistry(tmp_path, [PluginDefinition("a", "A", "", "foundation", "1", ("run",), requires=("b",))])
    with pytest.raises(ValueError, match="循环"):
        PluginRegistry(tmp_path, [
            PluginDefinition("a", "A", "", "foundation", "1", ("run",), requires=("b",)),
            PluginDefinition("b", "B", "", "foundation", "1", ("run",), requires=("a",)),
        ])


def test_development_process_shows_plan_then_actual_worker_call(dedicated_client, tmp_path):
    client = dedicated_client
    root = repository(tmp_path)
    item = post(client, "/items", {"itemType": "requirement", "title": "Trace one real execution"})
    base = "/api/lifeweave/personal"
    catalog = client.get(f"{base}/plugins")
    assert catalog.status_code == 200
    plugins = {row["id"]: row for row in catalog.json()["items"]}
    assert plugins["lifeweave.execution.codex"]["runnable"]
    assert not plugins["lifeweave.execution.opencode"]["runnable"]
    assert plugins["lifeweave.development"]["composed_of"]

    created = client.post(f"{base}/development", json={
        "requestId": "plugin-process-1", "itemId": item["id"], "instruction": "Inspect the README and propose a change",
        "repositoryPath": str(root), "reviewMode": "self",
    })
    assert created.status_code == 202, created.text
    assignment = created.json()
    url = f"{base}/items/{item['id']}/plugin-process"
    before = client.get(url).json()
    assert len(before["plans"]) == 1
    plan = before["plans"][0]
    assert plan["assignment_id"] == assignment["id"]
    assert {"plan.context", "plan.method", "plan.codex", "plan.check"} <= {step["id"] for step in plan["steps"]}
    assert any(call["plugin_id"] == "lifeweave.context" for call in before["calls"])
    assert not any(call["plugin_id"] == "lifeweave.execution.codex" for call in before["calls"])
    assert client.get(f"/api/lifeweave/team/items/{item['id']}/plugin-process").status_code == 404

    runtime = client.app.state.lifeweave_runtime_service
    runtime.registration_tokens["personal"] = "test-registration"
    machine = runtime.register_machine("personal", registration_token="test-registration",
                                       name="plugin-test", capacity=1, engines=["codex"],
                                       runtimes=["native"], images=[], labels={})
    run_id = assignment["planRunId"]
    claimed = runtime.claim("personal", machine["id"], machine["worker_token"], lease_seconds=30)
    assert claimed["id"] == run_id
    disabled = client.put(f"{base}/plugins/lifeweave.execution.codex/enabled",
                          json={"enabled": False, "expectedVersion": 1})
    assert disabled.status_code == 200 and not disabled.json()["runnable"]
    assert client.put(f"{base}/plugins/lifeweave.execution.codex/enabled",
                      json={"enabled": True, "expectedVersion": 1}).status_code == 409
    assert not next(row for row in client.get(f"{base}/plugins").json()["items"]
                    if row["id"] == "lifeweave.development")["runnable"]
    assert client.post(f"{base}/development", json={
        "requestId": "plugin-process-disabled", "itemId": item["id"], "instruction": "Another request",
        "repositoryPath": str(root), "reviewMode": "self",
    }).status_code == 409
    with pytest.raises(ValueError, match="不可用"):
        runtime.worker_report("personal", machine["id"], machine["worker_token"], run_id,
                              {"lease_id": claimed["lease_id"], "outcome": "running", "environment": {}})
    assert not any(call["plugin_id"] == "lifeweave.execution.codex" for call in client.get(url).json()["calls"])
    enabled = client.put(f"{base}/plugins/lifeweave.execution.codex/enabled",
                         json={"enabled": True, "expectedVersion": disabled.json()["configVersion"]})
    assert enabled.status_code == 200 and enabled.json()["runnable"]
    runtime.worker_report("personal", machine["id"], machine["worker_token"], run_id,
                          {"lease_id": claimed["lease_id"], "outcome": "running", "environment": {}})
    assert not any(call["plugin_id"] == "lifeweave.execution.codex" for call in client.get(url).json()["calls"])
    runtime.worker_event("personal", machine["id"], machine["worker_token"], run_id,
                         lease_id=claimed["lease_id"], event_type="plugin.execution.started",
                         source="worker", channel="plugin", summary="adapter entered", payload={})
    started = client.get(url).json()
    execution_calls = [call for call in started["calls"] if call["plugin_id"] == "lifeweave.execution.codex"]
    assert len(execution_calls) == 1 and execution_calls[0]["state"] == "started"
    assert execution_calls[0]["step_id"] == "plan.codex"
    runtime.worker_event("personal", machine["id"], machine["worker_token"], run_id,
                         lease_id=claimed["lease_id"], event_type="plugin.execution.finished",
                         source="worker", channel="plugin", summary="adapter returned",
                         payload={"outcome": "succeeded", "exitCode": 0})
    runtime.worker_report("personal", machine["id"], machine["worker_token"], run_id,
                          {"lease_id": claimed["lease_id"], "outcome": "succeeded", "exit_code": 0,
                           "result": "A plan was produced", "environment": {}})
    after = client.get(url).json()
    final = next(call for call in after["calls"] if call["id"] == execution_calls[0]["id"])
    assert final["state"] == "succeeded" and final["observed_by"] == "worker-report"
    step = next(row for row in after["plans"][0]["steps"] if row["id"] == "plan.codex")
    assert step["observed"] and step["callIds"] == [final["id"]]

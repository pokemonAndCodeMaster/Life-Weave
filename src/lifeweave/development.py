"""A development assignment binds planning, review and implementation to one item.

The existing Run/Worker owns execution. This module only advances a fixed,
recoverable workflow after reading the real terminal state of each Run.
"""
from __future__ import annotations

import hashlib
import difflib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb
from src.agent_runtime.tree_snapshot import tree_sha256
from .development_delivery import _git as delivery_git, _tree_entries, freeze_delivery


ACTIVE = {"planning", "reviewing", "implementing"}
TERMINAL_RUNS = {"succeeded", "failed", "unavailable", "cancelled", "paused"}
DEFAULT_PROJECT_REFS = [
    "lifeweave-project:docs/product.md",
    "lifeweave-project:docs/architecture.md",
    "lifeweave-project:docs/status.md",
    "lifeweave-project:docs/development.md",
]
# Re-enable only after the read-only stage bypass found in the browser run is
# prevented and a fresh end-to-end assignment verifies the guard.
OPENCODE_DEVELOPMENT_ENABLED = False


class DevelopmentService:
    def __init__(self, db, work, runtime, sources, project_root: Path):
        self.db, self.work, self.runtime, self.sources = db, work, runtime, sources
        self.project_root = project_root.resolve()

    @staticmethod
    def _git(*args: str, cwd: Path) -> str:
        result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                                text=True, timeout=10, check=False)
        if result.returncode:
            raise ValueError("项目目录必须是可读取且已有提交的 Git 仓库")
        return result.stdout.strip()

    def _project(self, value: str) -> tuple[str, str, bool]:
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("项目目录不存在")
        root = Path(self._git("rev-parse", "--show-toplevel", cwd=path)).resolve()
        revision = self._git("rev-parse", "HEAD", cwd=root)
        dirty = bool(self._git("status", "--porcelain", cwd=root))
        return str(root), revision, dirty

    def choices(self, workspace: str, item_id: str) -> dict[str, Any]:
        item = self.work.get_item(workspace, item_id)
        method = next((row for row in self.sources.catalog(workspace)["items"]
                       if row["title"] == "lifeweave-development"), None)
        codex = self.runtime.executors["codex"].health()
        opencode = self.runtime.executors["opencode"].health()
        # A binary on PATH is insufficient evidence that an account can call a
        # model. Offer only the explicit model most recently completed by the
        # actual worker in this workspace, and require a fresh result.
        tested = (self.db.fetch_one(
            "SELECT model,finished_at FROM workbench.t_lifeweave_run "
            "WHERE workspace=%s AND engine='opencode' AND state='succeeded' "
            "AND model IS NOT NULL AND model<>'' AND exit_code=0 AND length(btrim(result))>0 "
            "AND environment_snapshot->>'effectiveModel'=model "
            "AND finished_at>now()-interval '7 days' "
            "ORDER BY finished_at DESC LIMIT 1", (workspace,))
            if OPENCODE_DEVELOPMENT_ENABLED and opencode.available else None)
        opencode_ready = bool(OPENCODE_DEVELOPMENT_ENABLED and opencode.available and tested)
        if not OPENCODE_DEVELOPMENT_ENABLED:
            opencode_reason = "只读越权反例和隔离账号调用失败待回归，OpenCode 开发委托暂不可选"
        elif opencode_ready:
            opencode_reason = "仅开放近七天实际成功的指定模型；开发链仍需逐次审阅"
        else:
            opencode_reason = "当前空间没有近七天指定模型的真实成功运行，或 OpenCode CLI 不可用"
        return {
            "itemId": item_id,
            "recommendedRepositoryPath": str(self.project_root),
            "agents": [
                {"id": "development", "title": "开发 Agent", "version": method["id"] if method else "builtin-v1",
                 "available": bool(method and (codex.available or opencode_ready)), "reason": "适用于代码项目的方案、审查、实施和验证"},
                {"id": "general", "title": "通用助理", "version": "conversation-v1", "available": True,
                 "reason": "适用于讨论、研究与记录，不自动修改代码"},
            ],
            "recommendedAgentId": "development" if item.get("itemType") in {"requirement", "fix"} else "general",
            "executors": {"codex": {"available": codex.available, "version": codex.version,
                                    "reason": codex.reason},
                          "opencode": {"available": opencode_ready, "version": opencode.version,
                                       "verifiedModel": tested["model"] if opencode_ready else None,
                                       "lastSucceededAt": tested["finished_at"].isoformat() if opencode_ready else None,
                                       "reason": opencode_reason}},
            "methodId": method["id"] if method else None,
            "knowledgeRefs": DEFAULT_PROJECT_REFS,
        }

    def _input_versions(self, workspace: str, method_id: str | None, refs: list[str]) -> list[dict[str, str]]:
        return [{"id": entry["id"], "version": entry["version"],
                 "sourcePath": entry["sourcePath"]}
                for entry in self.sources.snapshot(workspace, method_id, refs)]

    @staticmethod
    def _effective_context_sha256(context: dict[str, Any]) -> str:
        """Fingerprint accepted context and local working intent, not item status or steps."""
        value = {key: context.get(key) for key in ('versionId', 'content', 'focus', 'contextRefs')}
        value['localIntentGoal'] = (context.get('localIntent') or {}).get('goal')
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _bind_business_plan(self, workspace: str, item_id: str, assignment_id: str,
                            execution_scope: str, review_mode: str,
                            step_id: str | None, plan_version: int | None) -> dict[str, Any]:
        """Make the item plan authoritative and retain the assignment's plan identity."""
        from .work_view import WorkViewService
        from .work_view_models import WorkPlanInput

        item = self.work.get_item(workspace, item_id)
        raw = (item.get('payload') or {}).get('workPlan')
        if raw:
            if plan_version is not None and raw['version'] != plan_version:
                raise ValueError('业务计划版本已变更，请刷新步骤后重试')
            nodes = raw.get('nodes') or []
            if step_id:
                selected = next((node for node in nodes if node['id'] == step_id), None)
                if not selected:
                    raise ValueError('所选步骤不在当前业务计划中')
            else:
                required_kind = 'code' if execution_scope == 'implement' else 'plan'
                possible = [node for node in nodes if node.get('state') not in {'cancelled'} and
                            any(row.get('kind') == required_kind for row in node.get('expectedOutputs', []))]
                if len(possible) != 1:
                    raise ValueError('业务计划中无法唯一确定开发步骤，请指定 stepId 和 planVersion')
                selected = possible[0]
            return {'planId': raw['id'], 'planVersion': raw['version'],
                    'stageSteps': {'plan': selected['id'], 'review': selected['id'],
                                   'implementation': selected['id']}}
        if step_id or plan_version:
            raise ValueError('事项尚无业务计划，不能指定步骤或计划版本')

        # The plan is committed before the first Run is launched. Its expected
        # results remain visible even if the worker never starts.
        plan_step = f'{assignment_id}:plan'
        review_step = f'{assignment_id}:review'
        implementation_step = f'{assignment_id}:implementation'
        nodes = [{
            'id': plan_step, 'title': '形成方案', 'description': '明确范围、步骤和验证办法',
            'state': 'planned', 'dependsOn': [], 'assignmentId': assignment_id,
            'expectedOutputs': [{'id': 'plan', 'title': '固定版本开发方案', 'kind': 'plan', 'required': True}],
            'acceptance': '方案说明用户结果、受影响模块、实施顺序、验证和未决风险',
        }]
        last = plan_step
        if review_mode == 'independent':
            nodes.append({
                'id': review_step, 'title': '独立审阅方案', 'description': '独立核对方案与原目标',
                'state': 'planned', 'dependsOn': [plan_step], 'assignmentId': assignment_id,
                'expectedOutputs': [{'id': 'review', 'title': '固定版本审阅结论',
                                     'kind': 'decision', 'required': True}],
                'acceptance': '审阅结论明确通过或需修订，并说明依据',
            })
            last = review_step
        if execution_scope == 'implement':
            nodes.append({
                'id': implementation_step, 'title': '实施与交付', 'description': '在隔离工作树实施并固定代码交付',
                'state': 'planned', 'dependsOn': [last], 'assignmentId': assignment_id,
                'expectedOutputs': [{'id': 'code', 'title': '固定版本代码变更', 'kind': 'code', 'required': True}],
                'acceptance': '交付包包含完整变更清单、差异、必要文件快照和实际检查证据',
            })
        view = WorkViewService(self.work, self.runtime, self).save(
            workspace, item_id, WorkPlanInput.model_validate({
                'version': item['version'], 'title': '开发工作步骤', 'provider': 'development',
                'revisionReason': '受管开发启动时登记预期交付', 'nodes': nodes}), 'development-agent')
        return {'planId': view['plan']['id'], 'planVersion': view['plan']['version'],
                'stageSteps': {'plan': plan_step, 'review': review_step if review_mode == 'independent' else plan_step,
                               'implementation': implementation_step if execution_scope == 'implement' else plan_step}}

    def _business_binding(self, row: dict[str, Any]) -> dict[str, Any] | None:
        activity = self.db.fetch_one(
            "SELECT payload FROM workbench.t_lifeweave_activity WHERE workspace_key=%s AND item_id=%s "
            "AND kind='work_assignment_binding' AND payload->>'assignmentId'=%s ORDER BY created_at DESC LIMIT 1",
            (row['workspace'], row['item_id'], row['id']))
        return activity['payload'] if activity else None

    def _report_business_stage(self, row: dict[str, Any], stage: str, run_id: str,
                               outcome: str, summary: str) -> None:
        binding = self._business_binding(row)
        if not binding:
            return  # Assignments created before the shared protocol remain readable.
        from .work_step_reports import StepReportInput, StepReportService

        expected_kind = {'plan': 'plan', 'review': 'decision', 'implementation': 'code'}[stage]
        step_id = binding['stageSteps'][stage]
        plan = (self.work.get_item(row['workspace'], row['item_id']).get('payload') or {}).get('workPlan') or {}
        step = next((node for node in plan.get('nodes', []) if node['id'] == step_id), None)
        requirement = next((value for value in (step or {}).get('expectedOutputs', [])
                            if value.get('kind') == expected_kind), None)
        output_id = (f'delivery:{row["id"]}' if stage == 'implementation' else f'run:{run_id}')
        deliverables = ([{'expectationId': requirement['id'], 'outputId': output_id}]
                        if outcome == 'succeeded' and requirement else [])
        # Intermediate stages of one business step are attempts, not completion.
        business_outcome = outcome if outcome != 'succeeded' or requirement else 'running'
        body = StepReportInput.model_validate({
            'requestId': f'managed:{row["id"]}:{stage}:{run_id}:{outcome}',
            'planVersion': binding['planVersion'], 'stepId': step_id,
            'outcome': business_outcome, 'summary': summary or f'{stage} 阶段已结束',
            'deliverables': deliverables,
            'checks': ([{'label': f'{stage} 阶段实际检查', 'result': 'passed',
                         'evidence': f'run:{run_id}'}] if business_outcome == 'succeeded' else []),
            'runId': run_id, 'assignmentId': row['id'],
        })
        StepReportService(self.work, self.runtime, self, self.output_files).submit(
            row['workspace'], row['item_id'], body, 'development-agent')

    def create(self, workspace: str, *, item_id: str, request_id: str,
               instruction: str, repository_path: str, engine: str = "codex",
               model: str | None = None, method_id: str | None = None,
               knowledge_refs: list[str] | None = None,
               review_mode: str = "independent",
               execution_scope: str = "plan_only",
               acknowledge_excluded_changes: bool = False,
               step_id: str | None = None, plan_version: int | None = None) -> dict[str, Any]:
        if engine not in {"codex", "opencode"}:
            raise ValueError("执行器必须是 Codex 或 OpenCode")
        if review_mode not in {"independent", "self"}:
            raise ValueError("审查方式只能是独立审阅或轻量自检")
        if execution_scope not in {"plan_only", "implement"}:
            raise ValueError("执行范围必须是仅方案或允许实施")
        if engine == "opencode":
            option = self.choices(workspace, item_id)["executors"]["opencode"]
            if not option["available"]:
                raise ValueError(option["reason"])
            if not model or model != option["verifiedModel"]:
                raise ValueError("OpenCode 只能使用当前空间近七天实际运行成功的指定模型；请先检查执行器和模型")
        elif not self.runtime.executors["codex"].health().available:
            raise ValueError("Codex CLI 不可用，请先检查本机执行设置")
        self.work.get_item(workspace, item_id)
        request_content = {
            "instruction": instruction, "repositoryPath": str(Path(repository_path).expanduser().resolve()),
            "engine": engine, "model": model, "methodId": method_id,
            "knowledgeRefs": knowledge_refs, "reviewMode": review_mode,
            "executionScope": execution_scope,
        }
        if step_id is not None or plan_version is not None:
            request_content.update({'stepId': step_id, 'planVersion': plan_version})
        fingerprint = hashlib.sha256(json.dumps(request_content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        existing = self.db.fetch_one("SELECT * FROM workbench.lifeweave_development_assignment "
                                     "WHERE workspace=%s AND item_id=%s AND request_id=%s",
                                     (workspace, item_id, request_id))
        if existing:
            if existing["request_fingerprint"] != fingerprint:
                raise ValueError("此请求身份已用于不同开发内容")
            return self._wire(existing)
        root, revision, dirty = self._project(repository_path)
        if dirty and not acknowledge_excluded_changes:
            raise ValueError("所选仓库有未提交改动；受管 Run 只读取已提交版本。请确认排除这些改动后重试")
        if method_id is None:
            method_id = self.choices(workspace, item_id)["methodId"]
        if not method_id:
            raise ValueError("开发方法未接入，无法固定 Agent 版本")
        refs = list(dict.fromkeys(knowledge_refs if knowledge_refs is not None else
                                  (DEFAULT_PROJECT_REFS if Path(root) == self.project_root else [])))
        if len(refs) > 10:
            raise ValueError("一次开发最多选择 10 篇知识")
        versions = self._input_versions(workspace, method_id, refs)
        identity = "dev-" + hashlib.sha256(f"{workspace}:{item_id}:{request_id}".encode()).hexdigest()[:32]
        with self.db.atomic() as conn:
            # Serialize different request IDs for the same item before checking the
            # active assignment; an empty SELECT ... FOR UPDATE cannot lock a row.
            conn.execute("SELECT id FROM workbench.t_lifeweave_item "
                         "WHERE workspace_key=%s AND id=%s FOR UPDATE", (workspace, item_id)).fetchone()
            context = self.work.current_context_snapshot(workspace, item_id)
            existing = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                                    "WHERE workspace=%s AND item_id=%s AND request_id=%s FOR UPDATE",
                                    (workspace, item_id, request_id)).fetchone()
            if existing:
                if existing["request_fingerprint"] != fingerprint:
                    raise ValueError("此请求身份已用于不同开发内容")
                return self._wire(existing)
            active = conn.execute("SELECT id FROM workbench.lifeweave_development_assignment "
                                  "WHERE workspace=%s AND item_id=%s AND status IN ('planning','reviewing','implementing') "
                                  "FOR UPDATE", (workspace, item_id)).fetchone()
            if active:
                raise ValueError("此事项仍有开发委托进行中，请先查看原委托")
            from .work_binding import WorkBindingInput, WorkBindingService
            WorkBindingService(self.work).resolve(workspace, WorkBindingInput.model_validate({
                'requestId': f'development:{request_id}', 'decision': 'continue',
                'itemId': item_id,
            }), 'development-agent')
            row = conn.execute("INSERT INTO workbench.lifeweave_development_assignment "
                               "(id,workspace,item_id,request_id,request_fingerprint,instruction,agent_id,agent_version,"
                               "engine,model,repository_path,repository_revision,working_tree_excluded,context_version_id,"
                               "method_id,knowledge_refs,input_versions,review_mode,execution_scope,status) "
                               "VALUES (%s,%s,%s,%s,%s,%s,'development',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planning') RETURNING *",
                               (identity, workspace, item_id, request_id, fingerprint, instruction,
                                next((entry["version"] for entry in versions if entry["id"] == method_id), "unknown"),
                                engine, model, root, revision, dirty, context["versionId"], method_id,
                                Jsonb(refs), Jsonb(versions), review_mode, execution_scope)).fetchone()
            binding = self._bind_business_plan(workspace, item_id, identity,
                                               execution_scope, review_mode, step_id, plan_version)
            self.plugins.create_development_plan(conn, row)
            run = self._stage_run(row, "plan", instruction)
            row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                               "SET plan_run_id=%s,updated_at=now() WHERE id=%s RETURNING *",
                               (run["id"], identity)).fetchone()
            self.work.append_activity(workspace, item_id, kind='work_assignment_binding',
                                      body='受管开发已绑定业务计划步骤',
                                      payload={**binding, 'assignmentId': identity,
                                               'planRunId': run['id'],
                                               'effectiveContextSha256': self._effective_context_sha256(
                                                   self.work.current_context_snapshot(workspace, item_id))},
                                      actor_id='development-agent')
            self._report_business_stage(row, 'plan', run['id'], 'running', '受管开发已启动方案阶段')
        return self._wire(row)

    def _stage_run(self, assignment: dict[str, Any], stage: str, instruction: str) -> dict[str, Any]:
        common = dict(item_id=assignment["item_id"], engine=assignment["engine"],
                      model=assignment["model"], directory=assignment["repository_path"],
                      method_id=assignment["method_id"], knowledge_refs=assignment["knowledge_refs"],
                      actor_id="development-agent")
        if stage == "plan":
            prompt = ("开发委托的只读方案阶段。只能阅读仓库与已选知识，不能修改文件。"
                      "请写用户将看到的行为、受影响模块和接口、实现顺序、风险、验证、知识变化。"
                      "结尾必须有“自检”及尚未解决的问题。\n\n用户任务：" + instruction)
            permission = "read-only"
        elif stage == "review":
            prompt = ("你是独立方案审阅者，本次为全新只读 Run。请核对用户原目标、项目提交、方案的遗漏和可验证性，"
                      "不得实施或修改文件。结束时单独一行写 REVIEW_DECISION: PASS 或 "
                      "REVIEW_DECISION: NEEDS_REVISION，并解释具体问题。\n\n"
                      f"用户任务：{assignment['instruction']}\n"
                      f"审查方案 SHA-256：{assignment['plan_sha256']}\n\n"
                      f"方案正文：\n{assignment['plan']}")
            permission = "read-only"
        else:
            prompt = ("按已审方案在本轮隔离工作树实施，运行与改动相称的真实验证。"
                      "交付时给出实际文件差异、测试结果、未完成项和知识更新；不要声称代码已合回原仓。\n\n"
                      f"用户任务：{assignment['instruction']}\n"
                      f"已审方案 SHA-256：{assignment['plan_sha256']}\n{assignment['plan']}\n\n"
                      f"审阅记录：{assignment['review']}")
            permission = "workspace-write"
        plan = self.plugins.plan_for_assignment(assignment["workspace"], assignment["id"])
        if plan is None:
            # Assignments created before the plugin migration retain their old
            # workflow. Do not backfill a plan after execution has begun.
            return self.runtime.create_run(assignment["workspace"], instruction=prompt,
                                           permission=permission, **common)
        step = {"plan": "plan.development", "review": "review.development", "implementation": "implement.development"}[stage]
        operation = {"plan": "plan", "review": "review", "implementation": "implement"}[stage]
        scope = {"assignmentId": assignment["id"], "planId": plan["id"], "stage": stage}
        return self.plugin_host.invoke(
            "lifeweave.development", operation, workspace=assignment["workspace"], item_id=assignment["item_id"],
            assignment_id=assignment["id"], plan_id=plan["id"], step_id=step,
            input_ref={"repositoryRevision": assignment["repository_revision"], "stage": stage},
            handler=lambda: self.runtime.create_run(assignment["workspace"], instruction=prompt,
                                                    permission=permission, plugin_scope=scope, **common),
            output_ref=lambda run: {"runId": run["id"], "state": "queued"}, accepted=True)

    def _assert_unchanged(self, row: dict[str, Any]) -> None:
        root, revision, _ = self._project(row["repository_path"])
        if root != row["repository_path"] or revision != row["repository_revision"]:
            raise ValueError("项目提交已变化；旧方案不能直接用于新源码，请重新委托")
        context = self.work.current_context_snapshot(row["workspace"], row["item_id"])
        if context["versionId"] != row["context_version_id"]:
            raise ValueError("事项背景已更新；请按新共识重新形成方案")
        binding = self._business_binding(row)
        if binding and binding.get('effectiveContextSha256') and self._effective_context_sha256(context) != binding['effectiveContextSha256']:
            raise ValueError("事项工作目标或背景已更新；旧方案不能直接继续，请重新委托")
        if self._input_versions(row["workspace"], row["method_id"], row["knowledge_refs"]) != row["input_versions"]:
            raise ValueError("所选方法或知识版本已变化；请重新形成方案")

    def _assert_readonly_clean(self, run: dict[str, Any], base: str) -> None:
        environment = run.get("environment_snapshot") or {}
        actual = environment.get("actualDirectory")
        if not actual:
            raise ValueError("只读阶段缺少执行目录，无法核对是否修改过代码")
        directory = Path(actual).resolve()
        if not directory.is_relative_to(self.project_root / ".runtime" / "executions") or not directory.is_dir():
            raise ValueError("只读阶段执行目录不可核对")
        expected_tree = environment.get("readonlyTreeSha256")
        if not isinstance(expected_tree, str) or len(expected_tree) != 64:
            raise ValueError("只读阶段缺少运行前文件快照，无法核对是否修改过代码")
        if tree_sha256(directory) != expected_tree:
            raise ValueError("只读阶段修改了隔离工作树，已阻止进入下一阶段")
        if self._git("rev-parse", "HEAD", cwd=directory) != base:
            raise ValueError("只读阶段改变了 Git 提交，已阻止进入下一阶段")
        generated = set(environment.get("materializedInputFiles") or
                        environment.get("materializedCapabilities") or [])
        if generated:
            generated.add(".lifeweave/capability-manifest.json")
        tracked = subprocess.run(["git", "-C", str(directory), "diff", "--name-only", "-z", base],
                                 capture_output=True, timeout=10, check=False)
        untracked = subprocess.run(["git", "-C", str(directory), "ls-files", "--others", "--exclude-standard", "-z"],
                                   capture_output=True, timeout=10, check=False)
        # `git status` omits ignored outputs, but a read-only stage may still
        # write them. Check those too before allowing the next stage.
        ignored = subprocess.run(["git", "-C", str(directory), "ls-files", "--others", "--ignored",
                                  "--exclude-standard", "-z"], capture_output=True, timeout=10, check=False)
        if tracked.returncode or untracked.returncode or ignored.returncode:
            raise ValueError("只读阶段的 Git 差异无法核对")
        paths = [part.decode("utf-8", "replace") for part in
                 (tracked.stdout + untracked.stdout + ignored.stdout).split(b"\0") if part]
        changed = [path for path in paths if path not in generated]
        if changed:
            raise ValueError("只读阶段修改了隔离工作树，已阻止进入下一阶段：" + ", ".join(changed[:8]))

    def advance(self, identity: str) -> None:
        with self.db.atomic() as conn:
            row = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                               "WHERE id=%s FOR UPDATE", (identity,)).fetchone()
            if not row or row["status"] not in ACTIVE:
                return
            status = row["status"]
            run_id = {"planning": row["plan_run_id"], "reviewing": row["review_run_id"],
                      "implementing": row["implementation_run_id"]}[status]
            if not run_id:
                raise RuntimeError("开发委托缺少当前阶段的 Run")
            run = self.runtime.get_run_snapshot(row["workspace"], run_id)
            if run["state"] not in TERMINAL_RUNS:
                return
            def complete(outcome: str) -> None:
                self.plugin_host.complete_development_stage(
                    workspace=row["workspace"], assignment_id=identity,
                    run_id=run_id, outcome=outcome)
                stage = {'planning': 'plan', 'reviewing': 'review',
                         'implementing': 'implementation'}[status]
                report_outcome = ('succeeded' if outcome == 'succeeded' else
                                  'cancelled' if outcome == 'interrupted' else 'failed')
                result = str(run.get('result') or '').strip()
                summary = (f'{stage} 阶段完成：{result[:3800]}' if report_outcome == 'succeeded' else
                           f'{stage} 阶段未完成：{str(run.get("error") or outcome)[:3800]}')
                self._report_business_stage(row, stage, run_id, report_outcome, summary)
            if run["state"] != "succeeded":
                target = "cancelled" if run["state"] == "cancelled" else "failed"
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status=%s,error=%s,updated_at=now() WHERE id=%s",
                             (target, f"{status} 阶段 {run['state']}：{str(run.get('error') or '')[:1500]}", identity))
                complete("interrupted" if target == "cancelled" else "failed")
                return
            if status in {"planning", "reviewing"}:
                try:
                    plan = self.plugins.plan_for_assignment(row["workspace"], row["id"])
                    label = "plan" if status == "planning" else "review"
                    self.plugin_host.invoke(
                        "lifeweave.checks.repository", "verify_readonly", workspace=row["workspace"],
                        item_id=row["item_id"], assignment_id=row["id"], plan_id=plan["id"] if plan else None,
                        run_id=run_id, step_id=f"{label}.check" if plan else None,
                        input_ref={"runId": run_id, "repositoryRevision": row["repository_revision"]},
                        handler=lambda: self._assert_readonly_clean(run, row["repository_revision"]),
                        output_ref=lambda _: {"runId": run_id, "result": "clean"})
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='blocked',error=%s,updated_at=now() WHERE id=%s",
                                 (str(exc), identity))
                    complete("failed")
                    return
            if status == "implementing":
                try:
                    manifest, digest = freeze_delivery(self.project_root, row, run)
                    conn.execute("INSERT INTO workbench.lifeweave_development_delivery "
                                 "(id,workspace,assignment_id,run_id,base_revision,artifact_sha256,manifest) "
                                 "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (assignment_id) DO NOTHING",
                                 ("delivery-" + identity[4:], row["workspace"], identity, run_id,
                                  row["repository_revision"], digest, Jsonb(manifest)))
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='awaiting_acceptance',error=NULL,updated_at=now() WHERE id=%s", (identity,))
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='delivery_failed',error=%s,updated_at=now() WHERE id=%s",
                                 (f"实施已结束，但交付包生成失败：{str(exc)[:1200]}", identity))
                    complete("failed")
                    return
                complete("succeeded")
                return
            result = str(run.get("result") or "").strip()
            if status == "planning" and len(result) < 80:
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='blocked',error='方案正文过短，未进入实施',updated_at=now() WHERE id=%s",
                             (identity,))
                complete("failed")
                return
            if status == "planning":
                digest = hashlib.sha256(result.encode()).hexdigest()
                row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                   "SET plan=%s,plan_sha256=%s,updated_at=now() WHERE id=%s RETURNING *",
                                   (result, digest, identity)).fetchone()
            try:
                self.plugin_host.invoke(
                    "lifeweave.checks.repository", "verify_inputs", workspace=row["workspace"],
                    item_id=row["item_id"], assignment_id=row["id"], plan_id=plan["id"] if plan else None,
                    run_id=run_id, step_id=f"{label}.inputs" if plan else None,
                    input_ref={"repositoryRevision": row["repository_revision"],
                               "contextVersionId": row["context_version_id"]},
                    handler=lambda: self._assert_unchanged(row),
                    output_ref=lambda _: {"result": "unchanged"})
            except (ValueError, OSError) as exc:
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='blocked',error=%s,updated_at=now() WHERE id=%s",
                             (str(exc), identity))
                complete("failed")
                return
            if status == "planning" and row["review_mode"] == "independent":
                review = self._stage_run(row, "review", row["instruction"])
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='reviewing',review_run_id=%s,updated_at=now() WHERE id=%s",
                             (review["id"], identity))
                complete("succeeded")
                self._report_business_stage(row, 'review', review['id'], 'running', '独立方案审阅已启动')
                return
            if status == "reviewing":
                decision = "pass" if re.search(r"^REVIEW_DECISION:\s*PASS\s*$", result, re.I | re.M) else "needs_revision"
                row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                   "SET review=%s,review_decision=%s,updated_at=now() WHERE id=%s RETURNING *",
                                   (result, decision, identity)).fetchone()
                if decision != "pass":
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='blocked',error='独立审阅未通过或没有明确 PASS',updated_at=now() WHERE id=%s",
                                 (identity,))
                    complete("failed")
                    return
            else:
                if "自检" not in result:
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='blocked',error='轻量方案缺少自检',updated_at=now() WHERE id=%s",
                                 (identity,))
                    complete("failed")
                    return
                row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                   "SET review='方案阶段自检（非独立审阅）',review_decision='self_checked',"
                                   "updated_at=now() WHERE id=%s RETURNING *", (identity,)).fetchone()
            if row["execution_scope"] == "plan_only":
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='plan_ready',updated_at=now() WHERE id=%s", (identity,))
                complete("succeeded")
                return
            implementation = self._stage_run(row, "implementation", row["instruction"])
            conn.execute("UPDATE workbench.lifeweave_development_assignment "
                         "SET status='implementing',implementation_run_id=%s,updated_at=now() WHERE id=%s",
                         (implementation["id"], identity))
            complete("succeeded")
            self._report_business_stage(row, 'implementation', implementation['id'], 'running', '受管实施已启动')

    def scan(self) -> None:
        rows = self.db.fetch_all("SELECT id FROM workbench.lifeweave_development_assignment "
                                 "WHERE status IN ('planning','reviewing','implementing') ORDER BY created_at")
        for row in rows:
            try:
                self.advance(row["id"])
            except Exception as exc:
                # Fail visibly; never advance to writable execution after an uncertain transition.
                self.db.execute("UPDATE workbench.lifeweave_development_assignment "
                                "SET status='blocked',error=%s,updated_at=now() WHERE id=%s AND "
                                "status IN ('planning','reviewing','implementing')",
                                (f"阶段推进失败：{type(exc).__name__}: {str(exc)[:1400]}", row["id"]))

    def list(self, workspace: str, item_id: str) -> list[dict[str, Any]]:
        self.work.get_item(workspace, item_id)
        rows = self.db.fetch_all("SELECT * FROM workbench.lifeweave_development_assignment "
                                 "WHERE workspace=%s AND item_id=%s ORDER BY created_at DESC",
                                 (workspace, item_id))
        return [self._wire(row) for row in rows]

    def get(self, workspace: str, identity: str) -> dict[str, Any]:
        row = self.db.fetch_one("SELECT * FROM workbench.lifeweave_development_assignment "
                                "WHERE workspace=%s AND id=%s", (workspace, identity))
        if not row:
            raise KeyError(identity)
        return self._wire(row)

    def delivery(self, workspace: str, identity: str) -> dict[str, Any] | None:
        self.get(workspace, identity)
        row = self.db.fetch_one("SELECT * FROM workbench.lifeweave_development_delivery "
                                "WHERE workspace=%s AND assignment_id=%s", (workspace, identity))
        if not row:
            return None
        return {"id": row["id"], "assignmentId": identity, "implementationRunId": row["run_id"],
                "baseRevision": row["base_revision"], "artifactSha256": row["artifact_sha256"],
                "manifest": row["manifest"], "integrationCommit": row["integration_commit"],
                "integrationCheckedAt": row["integration_checked_at"],
                "integrationCurrentHead": row["integration_current_head"],
                "decision": row["decision"], "decisionScope": row["decision_scope"],
                "decisionReason": row["decision_reason"], "decisionRequestId": row["decision_request_id"],
                "decidedBy": row["decided_by"],
                "decidedAt": row["decided_at"], "createdAt": row["created_at"]}

    def delivery_bytes(self, workspace: str, identity: str) -> bytes:
        row = self.delivery(workspace, identity)
        if not row:
            raise ValueError("此委托尚无固定交付包")
        path = self.project_root / ".runtime" / "development-deliveries" / f"{identity}.zip"
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["artifactSha256"]:
            raise ValueError("固定交付包校验失败")
        return content

    def verify_integration(self, workspace: str, identity: str, commit: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
            raise ValueError("请输入完整的目标 Git 提交 ID")
        assignment = self.get(workspace, identity)
        delivery = self.delivery(workspace, identity)
        if not delivery or assignment["status"] not in {"awaiting_acceptance", "accepted", "rejected"}:
            raise ValueError("此委托没有可核对的固定交付")
        self.delivery_bytes(workspace, identity)
        root = Path(assignment["repositoryPath"]).resolve()
        if root != Path(self._git("rev-parse", "--show-toplevel", cwd=root)).resolve():
            raise ValueError("目标仓目录已经变化")
        resolved = delivery_git(root, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
        if delivery["integrationCommit"] and delivery["integrationCommit"] != resolved:
            raise ValueError("此交付已有固定的目标提交核对记录")
        files = delivery["manifest"]["files"]
        actual = _tree_entries(delivery_git(root, "ls-tree", "-r", "-z", resolved, "--",
                                            *(entry["path"] for entry in files)))
        # Manifest entries also carry captured file bytes and digests. Git tree
        # identity is the mode/type/oid triple; deleted and rename-source paths
        # must still be absent from the target tree.
        git_identity = lambda value: ({key: value.get(key) for key in ('mode', 'type', 'oid')}
                                      if value is not None else None)
        mismatches = [entry["path"] for entry in files
                      if git_identity(actual.get(entry["path"])) != git_identity(entry["after"])]
        if mismatches:
            raise ValueError("目标提交与固定交付文件不一致：" + ", ".join(mismatches[:8]))
        current_head = delivery_git(root, "rev-parse", "HEAD").decode().strip() == resolved
        with self.db.atomic() as conn:
            row = conn.execute("SELECT * FROM workbench.lifeweave_development_delivery "
                               "WHERE workspace=%s AND assignment_id=%s FOR UPDATE", (workspace, identity)).fetchone()
            if row["integration_commit"] and row["integration_commit"] != resolved:
                raise ValueError("此交付已有固定的目标提交核对记录")
            if not row["integration_commit"]:
                conn.execute("UPDATE workbench.lifeweave_development_delivery SET "
                             "integration_commit=%s,integration_checked_at=now(),integration_current_head=%s "
                             "WHERE id=%s", (resolved, current_head, row["id"]))
        return self.delivery(workspace, identity)

    def decide_delivery(self, workspace: str, identity: str, *, artifact_sha256: str,
                        decision: str, scope: str, reason: str, request_id: str,
                        actor_id: str) -> dict[str, Any]:
        if decision not in {"accepted", "rejected"} or scope not in {"patch", "integrated"}:
            raise ValueError("交付决定或接受范围无效")
        if decision == "rejected" and not reason.strip():
            raise ValueError("需要修改时请说明原因")
        with self.db.atomic() as conn:
            assignment = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                                      "WHERE workspace=%s AND id=%s FOR UPDATE", (workspace, identity)).fetchone()
            if not assignment:
                raise KeyError(identity)
            row = conn.execute("SELECT * FROM workbench.lifeweave_development_delivery "
                               "WHERE workspace=%s AND assignment_id=%s FOR UPDATE", (workspace, identity)).fetchone()
            if not row or row["artifact_sha256"] != artifact_sha256:
                raise ValueError("交付版本已经变化，请刷新后再决定")
            if row["run_id"] != assignment["implementation_run_id"]:
                raise ValueError("交付与本次实施运行不匹配")
            self.delivery_bytes(workspace, identity)
            if row["decision"]:
                if (row["decision_request_id"] == request_id and row["decision"] == decision and
                        row["decision_scope"] == scope and (row["decision_reason"] or "") == reason):
                    return self.delivery(workspace, identity)
                raise ValueError("此交付已经作出决定；请从同一事项发起新的委托")
            if assignment["status"] != "awaiting_acceptance":
                raise ValueError("此委托尚未进入可接受状态")
            if decision == "accepted" and scope == "integrated" and not row["integration_commit"]:
                raise ValueError("接受目标仓结果前，需要先核对匹配的目标提交")
            evidence_id = "evidence-" + identity[4:]
            conn.execute("INSERT INTO workbench.t_lifeweave_evidence "
                         "(id,workspace_key,item_id,artifact_ref,artifact_version,environment_ref,summary,status,run_id,payload,created_by,reviewed_by,reviewed_at,review_reason) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s)",
                         (evidence_id, workspace, assignment["item_id"],
                          f"lifeweave-development:{identity}", artifact_sha256,
                          f"git:{row['integration_commit'] or row['base_revision']}",
                          "固定代码交付；接受范围：" + ("目标仓结果" if scope == "integrated" else "补丁"),
                          decision, row["run_id"],
                          Jsonb({"provenance": "development_delivery", "assignmentId": identity,
                                 "deliveryId": row["id"], "decisionScope": scope}), actor_id, actor_id, reason))
            conn.execute("UPDATE workbench.lifeweave_development_delivery SET "
                         "decision=%s,decision_scope=%s,decision_reason=%s,decision_request_id=%s,"
                         "decided_by=%s,decided_at=now() WHERE id=%s",
                         (decision, scope, reason, request_id, actor_id, row["id"]))
            conn.execute("UPDATE workbench.lifeweave_development_assignment "
                         "SET status=%s,updated_at=now() WHERE id=%s", (decision, identity))
        return self.delivery(workspace, identity)

    def diff(self, workspace: str, identity: str) -> dict[str, Any]:
        assignment = self.get(workspace, identity)
        run_id = assignment['implementationRunId']
        if not run_id:
            raise ValueError('实施阶段尚未建立工作目录')
        run = self.runtime.get_run_snapshot(workspace, run_id)
        actual = (run.get('environment_snapshot') or {}).get('actualDirectory')
        if not actual:
            raise ValueError('执行机尚未报告实际工作目录')
        directory = Path(actual).resolve()
        if not directory.is_relative_to(self.project_root / '.runtime' / 'executions') or not directory.is_dir():
            raise ValueError('本机无法读取该运行的隔离工作目录')
        base = assignment['repositoryRevision']
        changed = subprocess.run(['git', '-C', str(directory), 'diff', '--name-only', '-z', base],
                                 capture_output=True, timeout=10, check=False)
        if changed.returncode:
            raise ValueError('无法从原始提交读取运行差异')
        untracked = subprocess.run(['git', '-C', str(directory), 'ls-files', '--others', '--exclude-standard', '-z'],
                                   capture_output=True, timeout=10, check=False)
        if untracked.returncode:
            raise ValueError('运行工作目录不是可读取的 Git 检出')
        environment = run.get('environment_snapshot') or {}
        generated = set(environment.get('materializedInputFiles') or environment.get('materializedCapabilities') or [])
        if generated:
            generated.add('.lifeweave/capability-manifest.json')
        untracked_paths = [part.decode('utf-8', 'replace') for part in untracked.stdout.split(b'\0') if part]
        def generated_artifact(path: str) -> bool:
            parts = Path(path).parts
            return (bool(set(parts) & {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'})
                    or path.endswith(('.pyc', '.pyo')) or path == '.coverage')

        artifacts = [path for path in untracked_paths if generated_artifact(path)]
        paths = list(dict.fromkeys([part.decode('utf-8', 'replace') for part in changed.stdout.split(b'\0') if part] +
                                   untracked_paths))
        paths = [path for path in paths if path not in generated and path not in artifacts]
        patch = ''
        if paths:
            output = subprocess.run(['git', '-C', str(directory), 'diff', '--no-ext-diff', base, '--', *paths],
                                    capture_output=True, timeout=10, check=False,
                                    env={**os.environ, 'GIT_LITERAL_PATHSPECS': '1'})
            if output.returncode:
                raise ValueError('Git 差异读取失败')
            patch = output.stdout.decode('utf-8', 'replace')
        for relative in untracked_paths:
            if relative in generated or relative in artifacts:
                continue
            file = directory / relative
            if not file.is_file() or file.is_symlink() or file.stat().st_size > 100_000:
                continue
            try:
                content = file.read_text()
            except UnicodeError:
                continue
            patch += ''.join(difflib.unified_diff([], content.splitlines(keepends=True),
                         fromfile='/dev/null', tofile='b/' + relative))
        return {'runId': run_id, 'baseRevision': assignment['repositoryRevision'],
                'files': paths[:100], 'fileCount': len(paths), 'generatedInputsExcluded': sorted(generated),
                'generatedArtifactsExcluded': artifacts[:100],
                'patch': patch[:200_000], 'truncated': len(paths) > 100 or len(patch) > 200_000}

    def cancel(self, workspace: str, identity: str) -> dict[str, Any]:
        with self.db.atomic() as conn:
            row = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                               "WHERE workspace=%s AND id=%s FOR UPDATE", (workspace, identity)).fetchone()
            if not row:
                raise KeyError(identity)
            if row["status"] not in ACTIVE:
                raise ValueError("开发委托已结束")
            run_id = {"planning": row["plan_run_id"], "reviewing": row["review_run_id"],
                      "implementing": row["implementation_run_id"]}[row["status"]]
            self.runtime.request_cancel(workspace, run_id)
        return self.get(workspace, identity)

    @staticmethod
    def _wire(row: dict[str, Any]) -> dict[str, Any]:
        names = {"item_id": "itemId", "agent_id": "agentId", "agent_version": "agentVersion",
                 "repository_path": "repositoryPath", "repository_revision": "repositoryRevision",
                 "working_tree_excluded": "workingTreeExcluded", "review_mode": "reviewMode",
                 "review_decision": "reviewDecision", "plan_run_id": "planRunId",
                 "review_run_id": "reviewRunId", "implementation_run_id": "implementationRunId",
                 "plan_sha256": "planSha256", "created_at": "createdAt", "updated_at": "updatedAt",
                 "knowledge_refs": "knowledgeRefs", "input_versions": "inputVersions",
                 "context_version_id": "contextVersionId", "method_id": "methodId"}
        names["execution_scope"] = "executionScope"
        visible = {"id", "item_id", "instruction", "agent_id", "agent_version", "engine", "model",
                   "repository_path", "repository_revision", "working_tree_excluded", "review_mode",
                   "review_decision", "status", "plan_run_id", "review_run_id", "implementation_run_id",
                   "plan", "plan_sha256", "review", "error", "created_at", "updated_at",
                   "knowledge_refs", "input_versions", "context_version_id", "method_id", "execution_scope"}
        return {names.get(key, key): value for key, value in row.items() if key in visible}

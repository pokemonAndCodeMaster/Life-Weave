"""One write rule for reports from managed Runs and external sessions."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Literal

from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from .models import WireModel
from .repository import ConcurrentUpdateError


class ReportDelivery(WireModel):
    expectation_id: str = Field(alias='expectationId', min_length=1, max_length=128)
    output_id: str = Field(alias='outputId', min_length=1, max_length=256)
    version: str | None = Field(default=None, max_length=256)


class ReportCheck(WireModel):
    label: str = Field(min_length=1, max_length=256)
    result: Literal['passed', 'failed', 'unknown']
    evidence: str | None = Field(default=None, max_length=2048)


class StepReportInput(WireModel):
    request_id: str = Field(alias='requestId', min_length=1, max_length=128)
    plan_version: int = Field(alias='planVersion', ge=1)
    step_id: str = Field(alias='stepId', min_length=1, max_length=128)
    outcome: Literal['running', 'succeeded', 'failed', 'blocked', 'cancelled']
    summary: str = Field(min_length=1, max_length=5000)
    deliverables: list[ReportDelivery] = Field(default_factory=list, max_length=80)
    checks: list[ReportCheck] = Field(default_factory=list, max_length=80)
    run_id: str | None = Field(default=None, alias='runId', max_length=128)
    assignment_id: str | None = Field(default=None, alias='assignmentId', max_length=128)
    session_id: str | None = Field(default=None, alias='sessionId', max_length=128)

    @model_validator(mode='after')
    def unique_deliverables(self) -> 'StepReportInput':
        identities = [row.expectation_id for row in self.deliverables]
        if len(identities) != len(set(identities)):
            raise ValueError('同一预期产物只能提交一个成果引用')
        return self


class StepReportService:
    def __init__(self, work: Any, runtime: Any, development: Any, output_files: Any):
        self.work, self.runtime, self.development, self.output_files = work, runtime, development, output_files
        self.db = work.repository._postgres

    @staticmethod
    def _identity(workspace: str, item_id: str, request_id: str) -> str:
        return 'step-report-' + hashlib.sha256(f'{workspace}:{item_id}:{request_id}'.encode()).hexdigest()[:32]

    @staticmethod
    def _wire(row: dict[str, Any]) -> dict[str, Any]:
        payload = row['payload']
        return {'id': row['id'], 'itemId': row['item_id'], 'createdAt': row['created_at'],
                **payload['report']}

    def submit(self, workspace: str, item_id: str, body: StepReportInput, actor_id: str) -> dict[str, Any]:
        identity = self._identity(workspace, item_id, body.request_id)
        submitted = body.model_dump(by_alias=True, exclude_none=True)
        fingerprint = hashlib.sha256(json.dumps(submitted, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.db.atomic() as conn:
            item = conn.execute(
                f'SELECT id,version,payload FROM {self.work.repository.items} '
                'WHERE workspace_key=%s AND id=%s FOR UPDATE', (workspace, item_id)).fetchone()
            if not item:
                raise KeyError(item_id)
            existing = conn.execute(
                f'SELECT * FROM {self.work.repository.activities} WHERE id=%s', (identity,)).fetchone()
            if existing:
                if (existing['workspace_key'] != workspace or existing['item_id'] != item_id or
                        existing['payload'].get('requestFingerprint') != fingerprint):
                    raise ConcurrentUpdateError('同一请求标识已用于不同步骤报告')
                return self._wire(existing)

            plan = deepcopy((item['payload'] or {}).get('workPlan'))
            if not isinstance(plan, dict):
                raise ValueError('此事项尚无声明的业务计划')
            # Ownership is checked before recording any reference, including a failed attempt.
            if body.run_id:
                run = self.runtime.get_run(workspace, body.run_id)
                if str(run.get('item_id') or run.get('itemId')) != item_id:
                    raise ValueError('运行不属于当前事项')
            if body.assignment_id:
                assignment = self.development.get(workspace, body.assignment_id)
                if assignment.get('itemId') != item_id:
                    raise ValueError('开发委托不属于当前事项')
                if body.run_id and body.run_id not in {assignment.get(key) for key in
                                                        ('planRunId', 'reviewRunId', 'implementationRunId')}:
                    raise ValueError('运行不属于所选开发委托')
                assignment_binding = conn.execute(
                    f'SELECT payload FROM {self.work.repository.activities} '
                    "WHERE workspace_key=%s AND item_id=%s AND kind='work_assignment_binding' "
                    "AND payload->>'assignmentId'=%s ORDER BY created_at DESC LIMIT 1",
                    (workspace, item_id, body.assignment_id)).fetchone()
                if assignment_binding and body.step_id not in assignment_binding['payload'].get('stageSteps', {}).values():
                    raise ValueError('步骤不属于所选开发委托的业务计划绑定')
                if assignment_binding and body.plan_version != assignment_binding['payload'].get('planVersion'):
                    raise ValueError('报告计划版本与开发委托启动时的业务计划不一致')
            if body.session_id:
                session = conn.execute(
                    f'SELECT id,payload FROM {self.work.repository.activities} '
                    "WHERE workspace_key=%s AND item_id=%s AND kind='external_development_start' "
                    "AND payload->>'sessionId'=%s", (workspace, item_id, body.session_id)).fetchone()
                if not session:
                    raise ValueError('外部会话不属于当前事项')
                if (session['payload'].get('planVersion') is not None and
                        session['payload']['planVersion'] != body.plan_version):
                    raise ValueError('外部会话的计划版本绑定与报告不一致')
            if not any((body.run_id, body.assignment_id, body.session_id)):
                raise ValueError('步骤报告须关联真实执行或外部会话')

            issues: list[str] = []
            applied = False
            step = next((node for node in plan.get('nodes', []) if node.get('id') == body.step_id), None)
            if int(plan.get('version', 0)) != body.plan_version:
                issues.append('计划版本已变更；报告保留在原执行中，未更新当前步骤')
            elif step is None:
                issues.append('当前计划中没有此步骤；报告已保留，未更新当前步骤')

            output_ids: list[str] = []
            fixed_deliveries: list[dict[str, str]] = []
            expected = {row['id']: row for row in step.get('expectedOutputs', [])} if step else {}
            for delivery in body.deliverables:
                requirement = expected.get(delivery.expectation_id)
                if requirement is None:
                    issues.append(f'未知的预期产物：{delivery.expectation_id}')
                    continue
                output = self.output_files.catalog(workspace, item_id, delivery.output_id, delivery.version)
                if output.get('kind') != requirement['kind']:
                    issues.append(f'产物 {requirement["title"]} 类型不符：需要 {requirement["kind"]}')
                    continue
                if output.get('readable') is not True or not output.get('version'):
                    issues.append(f'产物 {requirement["title"]} 没有可读的固定版本')
                    continue
                if delivery.version and str(output['version']) != delivery.version:
                    issues.append(f'产物 {requirement["title"]} 版本不符')
                    continue
                output_ids.append(delivery.output_id)
                fixed_deliveries.append({'expectationId': delivery.expectation_id,
                                         'outputId': delivery.output_id, 'version': str(output['version'])})

            if body.outcome == 'succeeded':
                if not expected or not (step or {}).get('acceptance', '').strip():
                    issues.append('步骤缺少预期产物或验收办法')
                if not fixed_deliveries:
                    issues.append('完成步骤至少需要一份可读的固定产物')
                supplied = {entry['expectationId'] for entry in fixed_deliveries}
                for requirement in expected.values():
                    if requirement.get('required', True) and requirement['id'] not in supplied:
                        issues.append(f'缺少必需产物：{requirement["title"]}')
                if not body.checks or not any(check.result == 'passed' for check in body.checks):
                    issues.append('完成报告须包含实际通过的检查')
                if any(check.result == 'failed' for check in body.checks):
                    issues.append('检查未通过，不能标记完成')
            if step and step.get('state') == 'succeeded' and body.outcome == 'running':
                issues.append('步骤已完成；后续执行记录保留，但不回退当前步骤')
            if not issues and step is not None:
                # Lock + merge makes reports for different steps commute. A client only
                # names the plan version, never a stale item payload to overwrite.
                step['state'] = 'waiting' if body.outcome == 'blocked' else body.outcome
                step['summary'] = body.summary
                step['outputIds'] = list(dict.fromkeys([*(step.get('outputIds') or []), *output_ids]))
                if body.run_id:
                    step['runId'] = body.run_id
                if body.assignment_id:
                    step['assignmentId'] = body.assignment_id
                new_payload = {**(item['payload'] or {}), 'workPlan': plan}
                self.work.repository.update_item(workspace, item_id, item['version'], {'payload': new_payload}, actor_id)
                applied = True

            report = {**submitted, 'applied': applied, 'issues': issues,
                      'outputIds': output_ids, 'fixedDeliveries': fixed_deliveries}
            row = self.work.repository.append_activity(workspace, item_id, {
                'id': identity, 'kind': 'work_step_report', 'body': body.summary,
                'payload': {'requestFingerprint': fingerprint, 'report': report}, 'actor': actor_id})
            return {'id': row['id'], 'itemId': item_id, 'createdAt': row['createdAt'], **report}

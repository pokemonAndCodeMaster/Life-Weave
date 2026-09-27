"""Project the current work of one item without copying execution bodies."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import nullcontext
from copy import deepcopy
from typing import Any
from urllib.parse import quote, urlsplit

from .repository import ConcurrentUpdateError
from .work_view_models import WorkPlanInput


ITEM_LABELS = {
    'open': '待处理', 'planned': '已计划', 'in_progress': '进行中',
    'blocked': '受阻', 'awaiting_acceptance': '待验收',
    'completed': '已完成', 'cancelled': '已取消',
}
RUN_STATES = {
    'queued': 'planned', 'claimed': 'running', 'running': 'running',
    'pause_requested': 'waiting', 'paused': 'waiting', 'succeeded': 'succeeded',
    'failed': 'failed', 'unavailable': 'failed', 'cancelled': 'cancelled',
}
ASSIGNMENT_STATES = {
    'planning': 'running', 'reviewing': 'running', 'implementing': 'running',
    'plan_ready': 'waiting', 'awaiting_acceptance': 'waiting',
    'accepted': 'succeeded', 'rejected': 'failed', 'blocked': 'failed',
    'failed': 'failed', 'delivery_failed': 'failed', 'cancelled': 'cancelled',
}
ASSIGNMENT_LABELS = {
    'planning': '正在形成方案', 'reviewing': '正在审阅方案',
    'implementing': '正在实施', 'plan_ready': '方案已完成',
    'awaiting_acceptance': '交付待验收', 'accepted': '交付已接受',
    'rejected': '交付被退回', 'blocked': '开发委托受阻',
    'failed': '开发委托失败', 'delivery_failed': '交付包生成失败',
    'cancelled': '开发委托已取消',
}
RUN_LABELS = {
    'queued': '排队中', 'claimed': '已领取', 'running': '正在运行',
    'pause_requested': '请求暂停', 'paused': '已暂停',
    'succeeded': '已完成，待审阅成果', 'failed': '运行失败',
    'unavailable': '运行环境不可用', 'cancelled': '已取消',
}


def _stamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _latest_stamp(*values: Any) -> str | None:
    candidates: list[tuple[float, str]] = []
    for value in values:
        text = _stamp(value)
        if not text:
            continue
        try:
            parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            candidates.append((parsed.timestamp(), text))
        except ValueError:
            continue
    return max(candidates)[1] if candidates else None


def _brief(value: Any, limit: int = 240) -> str:
    return ' '.join(str(value or '').split())[:limit]


def _safe_uri(value: str | None) -> None:
    if value is None:
        return
    parts = urlsplit(value)
    if (not value or value.startswith('//') or '\\' in value or
            any(ord(character) < 32 or ord(character) == 127 for character in value) or
            parts.username is not None or parts.password is not None or
            parts.scheme not in {'', 'http', 'https'} or
            (not parts.scheme and (not value.startswith('/') or '..' in parts.path.split('/')))):
        raise ValueError('步骤背景链接必须是安全的站内路径或 HTTP(S) 链接')


def _node(identity: str, title: str, description: str = '', state: str = 'planned',
          summary: str = '', depends_on: list[str] | None = None, output_ids: list[str] | None = None,
          run_id: str | None = None, assignment_id: str | None = None,
          provenance: str = 'observed') -> dict[str, Any]:
    return {'id': identity, 'title': title, 'description': description, 'state': state,
            'summary': _brief(summary, 2000), 'dependsOn': depends_on or [],
            'outputIds': output_ids or [], 'runId': run_id, 'assignmentId': assignment_id,
            'contextRefs': [], 'provenance': provenance}


class WorkViewService:
    def __init__(self, work: Any, runtime: Any, development: Any):
        self.work, self.runtime, self.development = work, runtime, development

    def _owned_run(self, workspace: str, item_id: str, run_id: str) -> dict[str, Any]:
        run = self.runtime.get_run(workspace, run_id)
        if str(run.get('item_id') or run.get('itemId')) != item_id:
            raise ValueError('关联运行不属于当前事项和工作区')
        return run

    def _owned_assignment(self, workspace: str, item_id: str, assignment_id: str) -> dict[str, Any]:
        assignment = self.development.get(workspace, assignment_id)
        if assignment.get('itemId') != item_id:
            raise ValueError('开发委托不属于当前事项和工作区')
        return assignment

    @staticmethod
    def _run_output(workspace: str, run: dict[str, Any], kind: str = 'research',
                    title: str = '研究成果') -> dict[str, Any] | None:
        result = run.get('result')
        payload = run.get('result_payload') or {}
        content = payload.get('report') or payload.get('content') or result
        if not isinstance(content, str) or not content.strip():
            return None
        run_id = str(run['id'])
        base = f'/api/lifeweave/{workspace}/runs/{quote(run_id, safe="")}'
        return {'id': f'run:{run_id}', 'title': title, 'kind': kind,
                'summary': _brief(content), 'state': run.get('state'),
                'createdAt': _stamp(run.get('finished_at') or run.get('created_at')),
                'version': None, 'runId': run_id, 'assignmentId': None,
                'artifactId': None, 'uri': (base + '/research-output/download' if kind == 'research'
                                           else base + '/artifacts/result')}

    def _assignment_projection(self, workspace: str, item_id: str,
                               assignment: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        identity = assignment['id']
        status = assignment['status']
        runs: dict[str, dict[str, Any]] = {}
        for stage, key in (('plan', 'planRunId'), ('review', 'reviewRunId'),
                           ('implementation', 'implementationRunId')):
            if assignment.get(key):
                runs[stage] = self._owned_run(workspace, item_id, assignment[key])
        outputs: list[dict[str, Any]] = []
        delivery = self.development.delivery(workspace, identity)
        if delivery:
            outputs.append(self._delivery_output(workspace, identity, status, delivery))
        for stage, title in (('implementation', '实施运行结果'), ('plan', '开发方案'), ('review', '方案审阅')):
            if stage in runs:
                output = self._run_output(workspace, runs[stage], 'development', title)
                if output:
                    output['assignmentId'] = identity
                    outputs.append(output)
        def stage_state(stage: str) -> str:
            if stage == 'implementation' and status == 'delivery_failed':
                return 'failed'
            if stage in runs:
                return RUN_STATES.get(runs[stage]['state'], 'unobserved')
            if stage == 'review' and assignment.get('review') and assignment.get('reviewMode') == 'self':
                return 'succeeded' if assignment.get('reviewDecision') == 'self_checked' else 'failed'
            return 'planned'
        plan_id, review_id, implementation_id = (f'{identity}:{stage}' for stage in ('plan', 'review', 'implementation'))
        plan_run = runs.get('plan')
        plan = _node(plan_id, '形成方案', '依据事项背景形成开发方案', stage_state('plan'),
                     '方案已记录' if assignment.get('plan') else '',
                     output_ids=[f'run:{plan_run["id"]}'] if plan_run and any(o['id'] == f'run:{plan_run["id"]}' for o in outputs) else [],
                     run_id=plan_run['id'] if plan_run else None, assignment_id=identity)
        review_run = runs.get('review')
        review = _node(review_id, '审阅方案', '核对方案和实施范围', stage_state('review'),
                       assignment.get('reviewDecision') or '', [plan_id],
                       [f'run:{review_run["id"]}'] if review_run and any(o['id'] == f'run:{review_run["id"]}' for o in outputs) else [],
                       review_run['id'] if review_run else None, identity)
        nodes = [plan, review]
        if assignment.get('executionScope') == 'implement':
            implementation_run = runs.get('implementation')
            implementation_outputs = ([f'delivery:{identity}'] if delivery else [])
            if implementation_run and any(o['id'] == f'run:{implementation_run["id"]}' for o in outputs):
                implementation_outputs.append(f'run:{implementation_run["id"]}')
            nodes.append(_node(implementation_id, '实施与交付', '实施并形成可审阅交付',
                               stage_state('implementation'), assignment.get('error') or '',
                               [review_id], implementation_outputs,
                               implementation_run['id'] if implementation_run else None, identity))
            acceptance_state = ('succeeded' if status == 'accepted' else 'failed' if status == 'rejected'
                                else 'waiting' if status == 'awaiting_acceptance' else 'planned')
            nodes.append(_node(f'{identity}:acceptance', '审阅并接受交付', '核对代码交付与集成结果',
                               acceptance_state, ASSIGNMENT_LABELS.get(status, ''),
                               [implementation_id], [f'delivery:{identity}'] if delivery else [],
                               assignment_id=identity))
        return nodes, outputs

    @staticmethod
    def _delivery_output(workspace: str, identity: str, status: str,
                         delivery: dict[str, Any]) -> dict[str, Any]:
        return {'id': f'delivery:{identity}', 'title': '代码交付包',
                'kind': 'development', 'summary': '固定代码交付包及差异',
                'state': delivery.get('decision') or status,
                'createdAt': _stamp(delivery.get('createdAt')),
                'version': delivery.get('artifactSha256'),
                'runId': delivery.get('implementationRunId'),
                'assignmentId': identity, 'artifactId': None,
                'uri': f'/api/lifeweave/{workspace}/development/{quote(identity, safe="")}/delivery.zip'}

    def _recent_unassigned_runs(self, workspace: str, item_id: str,
                                assignment_run_ids: set[str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        offset = 0
        latest = None
        latest_output = None
        while True:
            rows, total = self.runtime.list_runs(workspace, item_id=item_id, limit=100, offset=offset)
            for row in rows:
                if row['id'] in assignment_run_ids:
                    continue
                if latest is None:
                    latest = row
                if row.get('state') == 'succeeded' and self._run_output(workspace, row):
                    latest_output = row
                    return latest, latest_output
            offset += len(rows)
            if offset >= total:
                return latest, latest_output
            if not rows:
                raise RuntimeError('运行列表在读取时变化，请重新读取工作图')

    def _manual_outputs(self, workspace: str, item_id: str) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for relation in self.work.repository.list_relations(workspace, item_id):
            if (relation.get('fromKind'), relation.get('fromId'), relation.get('toKind'),
                    relation.get('relationType')) != ('item', item_id, 'entity', 'produces'):
                continue
            entity = self.work.repository.get_entity(workspace, relation['toId'])
            if not entity or entity.get('entityType') != 'artifact' or entity['id'] in seen:
                continue
            body = entity.get('payload', {}).get('body')
            if not isinstance(body, str) or not body.strip():
                continue
            seen.add(entity['id'])
            outputs.append({'id': f'artifact:{entity["id"]}', 'title': entity['title'], 'kind': 'artifact',
                            'summary': _brief(body), 'state': 'manual', 'createdAt': _stamp(entity.get('updatedAt')),
                            'version': str(entity.get('version')) if entity.get('version') is not None else None,
                            'runId': None, 'assignmentId': None, 'artifactId': entity['id'],
                            'uri': f'/api/lifeweave/{workspace}/items/{quote(item_id, safe="")}/research-output'})
        outputs.sort(key=lambda output: output['createdAt'] or '', reverse=True)
        return outputs

    def _referenced_output(self, workspace: str, item_id: str, output_id: str,
                           assignments: list[dict[str, Any]]) -> dict[str, Any] | None:
        kind, separator, identity = output_id.partition(':')
        if not separator or not identity:
            return None
        if kind == 'delivery':
            assignment = self._owned_assignment(workspace, item_id, identity)
            delivery = self.development.delivery(workspace, identity)
            return self._delivery_output(workspace, identity, assignment['status'], delivery) if delivery else None
        if kind == 'run':
            run = self._owned_run(workspace, item_id, identity)
            for assignment in assignments:
                for stage, key, title in (('implementation', 'implementationRunId', '实施运行结果'),
                                          ('plan', 'planRunId', '开发方案'),
                                          ('review', 'reviewRunId', '方案审阅')):
                    if assignment.get(key) == identity:
                        output = self._run_output(workspace, run, 'development', title)
                        if output:
                            output['assignmentId'] = assignment['id']
                        return output
            return self._run_output(workspace, run)
        # Manual artifacts are already loaded through same-item produces relations.
        return None

    def read(self, workspace: str, item_id: str) -> dict[str, Any]:
        item = self.work.get_item(workspace, item_id)
        payload = item.get('payload') or {}
        raw_plan = payload.get('workPlan')
        if raw_plan is not None and not isinstance(raw_plan, dict):
            raise ValueError('事项中的工作计划格式无效')
        if raw_plan is not None:
            if not isinstance(raw_plan.get('id'), str) or not raw_plan['id'] or not isinstance(raw_plan.get('version'), int) or raw_plan['version'] < 1:
                raise ValueError('事项中的工作计划格式无效')
            WorkPlanInput.model_validate({'version': item['version'], 'title': raw_plan.get('title'),
                                          'provider': raw_plan.get('provider'), 'nodes': raw_plan.get('nodes')})
        assignments = self.development.list(workspace, item_id)
        assignment = assignments[0] if assignments else None
        assignment_run_ids = {str(row[key]) for row in assignments for key in
                              ('planRunId', 'reviewRunId', 'implementationRunId') if row.get(key)}
        latest_run, latest_output_run = self._recent_unassigned_runs(workspace, item_id, assignment_run_ids)
        outputs: list[dict[str, Any]] = []
        observed_nodes: list[dict[str, Any]] = []
        if assignment:
            observed_nodes, outputs = self._assignment_projection(workspace, item_id, assignment)
            if not any(output['id'].startswith('delivery:') for output in outputs):
                for older in assignments[1:]:
                    delivery = self.development.delivery(workspace, older['id'])
                    if delivery:
                        outputs.insert(0, self._delivery_output(workspace, older['id'], older['status'], delivery))
                        break
        if latest_run:
            research_output = self._run_output(workspace, latest_output_run) if latest_output_run else None
            if research_output:
                outputs.append(research_output)
            if not assignment:
                observed_nodes = [_node(f'run:{latest_run["id"]}', '委托研究与整理',
                                        '本步骤来自实际运行记录；没有细粒度研究过程记录',
                                        RUN_STATES.get(latest_run['state'], 'unobserved'),
                                        latest_run.get('error') or (research_output or {}).get('summary') or '',
                                        output_ids=[research_output['id']] if research_output and
                                        research_output['runId'] == latest_run['id'] else [],
                                        run_id=latest_run['id'])]
        manual_outputs = self._manual_outputs(workspace, item_id)
        outputs.extend(manual_outputs)
        def output_priority(output: dict[str, Any]) -> int:
            if output['id'].startswith('delivery:'):
                rank = 0
            elif output['title'] in {'开发方案', '方案审阅'}:
                rank = 2
            else:
                rank = 1
            return rank
        warnings: list[str] = []
        if raw_plan is not None:
            nodes = deepcopy(raw_plan.get('nodes', []))
            output_index = {output['id']: output for output in outputs}
            stage_cache: dict[str, dict[str, dict[str, Any]]] = {}
            for node in nodes:
                run_id = node.get('runId')
                assignment_id = node.get('assignmentId')
                actual_stage = None
                if assignment_id:
                    bound_assignment = self._owned_assignment(workspace, item_id, assignment_id)
                    if assignment_id not in stage_cache:
                        if assignment and assignment_id == assignment['id']:
                            stage_nodes = observed_nodes
                        else:
                            stage_nodes, _ = self._assignment_projection(workspace, item_id, bound_assignment)
                        stage_cache[assignment_id] = {stage_node['id']: stage_node for stage_node in stage_nodes}
                    actual_stage = stage_cache[assignment_id].get(node['id'])
                    if actual_stage:
                        node['state'] = actual_stage['state']
                        node['runId'] = actual_stage['runId']
                        node['outputIds'] = list(dict.fromkeys([*node.get('outputIds', []),
                                                                 *actual_stage['outputIds']]))
                        run_id = node['runId']
                    if run_id and run_id not in {bound_assignment.get(key) for key in
                                                 ('planRunId', 'reviewRunId', 'implementationRunId')}:
                        raise ValueError('关联运行不属于所选开发委托')
                    if not run_id and not actual_stage:
                        node['state'] = ASSIGNMENT_STATES.get(bound_assignment['status'], 'unobserved')
                if run_id:
                    run = self._owned_run(workspace, item_id, run_id)
                    if actual_stage is None:
                        node['state'] = RUN_STATES.get(run['state'], 'unobserved')
                    output = self._run_output(workspace, run, 'development' if assignment_id else 'research',
                                              '开发运行结果' if assignment_id else '研究成果')
                    if output and output['id'] not in output_index:
                        output_index[output['id']] = output
                        outputs.append(output)
                    if output and output['id'] not in node['outputIds']:
                        node['outputIds'].append(output['id'])
                for output_id in node.get('outputIds') or []:
                    if output_id in output_index:
                        continue
                    output = self._referenced_output(workspace, item_id, output_id, assignments)
                    if output:
                        output_index[output_id] = output
                        outputs.append(output)
                missing = set(node.get('outputIds') or []) - output_index.keys()
                if missing:
                    warnings.append(f'步骤 {node["id"]} 的成果引用已失效：{sorted(missing)[0]}')
                    node['outputIds'] = [value for value in node['outputIds'] if value in output_index]
                node['provenance'] = 'observed' if run_id or assignment_id else 'declared'
            plan = {'id': raw_plan['id'], 'title': raw_plan['title'], 'provider': raw_plan['provider'],
                    'source': 'declared', 'version': raw_plan['version'], 'editable': True, 'nodes': nodes}
        elif observed_nodes:
            plan = {'id': f'observed:{item_id}', 'title': '当前工作步骤',
                    'provider': 'observed', 'source': 'observed', 'version': 0,
                    'editable': False, 'nodes': observed_nodes}
        else:
            plan = {'id': f'empty:{item_id}', 'title': '尚未登记工作步骤',
                    'provider': 'manual', 'source': 'empty', 'version': 0,
                    'editable': True, 'nodes': []}
        outputs.sort(key=lambda output: output.get('createdAt') or '', reverse=True)
        outputs.sort(key=output_priority)
        item_label = ITEM_LABELS.get(item['status'], item['status'])
        if assignment:
            current_label = ASSIGNMENT_LABELS.get(assignment['status'], assignment['status'])
            current_summary = f'最近一次开发委托的实际状态；事项正式状态为{item_label}。'
        elif latest_run:
            current_label = RUN_LABELS.get(latest_run['state'], str(latest_run['state']))
            current_summary = (f'已有较早的完整成果可阅读；最新一轮仍需处理。事项正式状态为{item_label}。'
                               if latest_output_run and latest_output_run['id'] != latest_run['id'] else
                               f'最近一次委托的实际状态；事项正式状态为{item_label}。')
        elif raw_plan is not None:
            pending = next((node for node in plan['nodes'] if node['state'] in {'running', 'waiting', 'failed'}), None)
            if pending is None:
                pending = next((node for node in plan['nodes'] if node['state'] == 'planned'), None)
            current_label = pending['title'] if pending else '已登记工作步骤'
            current_summary = f'已登记 {len(plan["nodes"])} 个步骤；事项正式状态为{item_label}。'
        elif manual_outputs:
            current_label = '已有手工成果'
            current_summary = f'成果目录中有 {len(manual_outputs)} 份人工记录；事项正式状态为{item_label}。'
        else:
            current_label = item_label
            current_summary = '暂无实际工作记录，可登记步骤。'
        latest_update = _latest_stamp(item.get('updatedAt'), assignment.get('updatedAt') if assignment else None,
                                      latest_run.get('updated_at') or latest_run.get('finished_at') or
                                      latest_run.get('created_at') if latest_run else None,
                                      *(output.get('createdAt') for output in manual_outputs))
        return {'itemId': item_id, 'itemVersion': item['version'],
                'current': {'state': item['status'], 'label': current_label,
                            'summary': current_summary, 'updatedAt': latest_update},
                'plan': plan, 'outputs': outputs, 'warnings': warnings}

    def save(self, workspace: str, item_id: str, input: WorkPlanInput, actor_id: str) -> dict[str, Any]:
        item = self.work.get_item(workspace, item_id)
        if item['version'] != input.version:
            raise ConcurrentUpdateError('事项已被其他人更新，请刷新后重试')
        previous = (item.get('payload') or {}).get('workPlan')
        previous_version = int(previous.get('version', 0)) if isinstance(previous, dict) else 0
        owned_output_ids = {output['id'] for output in self.read(workspace, item_id)['outputs']}
        for node in input.nodes:
            for ref in node.context_refs:
                _safe_uri(ref.uri)
            if node.assignment_id:
                assignment = self._owned_assignment(workspace, item_id, node.assignment_id)
                if node.run_id and node.run_id not in {assignment.get(key) for key in
                                                       ('planRunId', 'reviewRunId', 'implementationRunId')}:
                    raise ValueError('关联运行不属于所选开发委托')
            if node.run_id:
                self._owned_run(workspace, item_id, node.run_id)
            # Existing outputs may be linked from a manual step. Direct bindings
            # also permit an older owned Run or delivery outside today's catalog.
            if node.output_ids:
                actual = set(owned_output_ids)
                if node.run_id:
                    run = self._owned_run(workspace, item_id, node.run_id)
                    if self._run_output(workspace, run):
                        actual.add(f'run:{node.run_id}')
                if node.assignment_id and self.development.delivery(workspace, node.assignment_id):
                    actual.add(f'delivery:{node.assignment_id}')
                if set(node.output_ids) - actual:
                    raise ValueError(f'步骤 {node.id} 的成果引用不属于关联运行或交付')
        plan = {'id': previous.get('id', f'plan:{item_id}') if isinstance(previous, dict) else f'plan:{item_id}',
                'title': input.title, 'provider': input.provider,
                'version': previous_version + 1,
                'nodes': [node.model_dump(by_alias=True) for node in input.nodes]}
        postgres = getattr(self.work.repository, '_postgres', None)
        with postgres.atomic() if postgres is not None else nullcontext():
            self.work.update_item(workspace, item_id, version=input.version, actor_id=actor_id,
                                  payload={**(item.get('payload') or {}), 'workPlan': plan})
            self.work.append_activity(workspace, item_id, kind='work_plan_updated',
                                      body=f'更新工作步骤：{input.title}（{len(input.nodes)} 步）',
                                      payload={'planId': plan['id'], 'planVersion': plan['version'],
                                               'plan': plan},
                                      actor_id=actor_id)
        return self.read(workspace, item_id)

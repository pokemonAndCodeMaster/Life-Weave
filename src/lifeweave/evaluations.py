from __future__ import annotations

from typing import Any
from uuid import uuid4

from .evaluation_repository import EvaluationRepository


class Evaluations:
    def __init__(self, repository: EvaluationRepository, work: Any, runtime: Any, knowledge: Any) -> None:
        self.repository = repository
        self.work = work
        self.runtime = runtime
        self.knowledge = knowledge
        self.plugins: Any = None

    def _plugin_call(self, workspace: str, call_id: str) -> dict[str, Any]:
        call = self.repository.postgres.fetch_one(
            'SELECT * FROM workbench.lifeweave_plugin_call WHERE workspace=%s AND id=%s',
            (workspace, call_id))
        if call is None:
            raise KeyError(call_id)
        return call

    def create(self, workspace: str, body: dict[str, Any]) -> dict[str, Any]:
        self.work.get_item(workspace, body['itemId'])
        repeat_of = body.get('repeatOf')
        if repeat_of:
            previous = self.repository.get(workspace, repeat_of)
            if previous['state'] != 'assessed':
                raise ValueError('只能沿已评估的任务复用标准')
            if any(previous[key] != body[key] for key in ('itemId', 'targetKind', 'instruction', 'criteria')):
                raise ValueError('对照评测必须保持同一事项、任务和通过标准')
        candidate_id = body.get('candidateId')
        plugin_call_id = body.get('pluginCallId')
        with self.repository.postgres.atomic() as conn:
            if body['targetKind'] == 'capability':
                if not candidate_id:
                    raise ValueError('能力评测必须选择候选')
                if plugin_call_id:
                    raise ValueError('能力候选评测不绑定插件调用')
                conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                             (f'lifeweave:evaluation:{workspace}:{candidate_id}',))
                candidate = self.knowledge.repository.get(workspace, candidate_id)
                if candidate['status'] not in ('candidate', 'verified'):
                    raise ValueError('只能评测试验中的能力候选')
                version = candidate['version']
                plugin_id = plugin_version = None
                call_run_id = None
            elif body['targetKind'] == 'plugin':
                if candidate_id or not plugin_call_id:
                    raise ValueError('插件评测必须选择一次真实调用，不能绑定能力候选')
                call = self._plugin_call(workspace, plugin_call_id)
                if call['item_id'] != body['itemId']:
                    raise ValueError('插件调用与评测事项不一致')
                if call['state'] not in ('succeeded', 'failed', 'interrupted'):
                    raise ValueError('插件调用尚未结束，暂不能评测')
                plugin_id, plugin_version = call['plugin_id'], call['plugin_version']
                call_run_id = call['run_id']
                version = None
                if repeat_of and previous['pluginId'] != plugin_id:
                    raise ValueError('对照评测必须使用同一插件身份')
            else:
                if candidate_id:
                    raise ValueError('平台整体评测不绑定能力候选')
                if plugin_call_id:
                    raise ValueError('平台整体评测不绑定插件调用')
                version = None
                plugin_id = plugin_version = None
                call_run_id = None
            row = {'id': 'eval-' + uuid4().hex[:16], 'repeatOf': None, **body,
                   'candidateId': candidate_id, 'candidateVersion': version,
                   'pluginId': plugin_id, 'pluginVersion': plugin_version,
                   'pluginCallId': plugin_call_id if body['targetKind'] == 'plugin' else None,
                   'runId': call_run_id, 'state': 'running' if body['targetKind'] == 'plugin' else 'planned'}
            self.repository.create(workspace, row)
        return self.get(workspace, row['id'])

    def get(self, workspace: str, evaluation_id: str) -> dict[str, Any]:
        row = self.repository.get(workspace, evaluation_id)
        if row['repeatOf']:
            previous = self.repository.get(workspace, row['repeatOf'])
            row['previous'] = {'id': previous['id'], 'outcome': previous['outcome'],
                               'runId': previous['runId'], 'candidateVersion': previous['candidateVersion'],
                               'assessment': previous['assessment']}
        if row['runId']:
            run = self.runtime.get_run(workspace, row['runId'])
            row['run'] = {'id': run['id'], 'state': run['state'], 'engine': run['engine'],
                          'itemId': run['item_id'], 'finishedAt': run.get('finished_at'),
                          'repositoryPath': run.get('repository_path'),
                          'repositoryRevision': run.get('repository_revision'),
                          'selectedInputs': (run.get('environment_snapshot') or {}).get('selectedInputs', {})}
            row['evidence'] = [
                {'id': entry['id'], 'status': entry['status'], 'summary': entry.get('summary')}
                for entry in self.work.repository.list_evidence(workspace, row['itemId'])
                if entry.get('runId') == row['runId']
            ]
        if row.get('pluginCallId'):
            call = self._plugin_call(workspace, row['pluginCallId'])
            row['pluginCall'] = {key: call[key] for key in
                                 ('id', 'plugin_id', 'plugin_version', 'implementation_digest', 'operation', 'state',
                                  'run_id', 'item_id',
                                  'started_at', 'finished_at')}
        return row

    def list(self, workspace: str, limit: int = 30, offset: int = 0) -> dict[str, Any]:
        rows, total = self.repository.list(workspace, limit, offset)
        return {'items': [self.get(workspace, row['id']) for row in rows],
                'total': total, 'limit': limit, 'offset': offset}

    def candidate_history(self, workspace: str, candidate_id: str,
                          limit: int = 20, offset: int = 0) -> dict[str, Any]:
        lineage = []
        visited: set[str] = set()
        next_id: str | None = candidate_id
        while next_id:
            if next_id in visited:
                raise ValueError('候选前任关系存在循环')
            visited.add(next_id)
            candidate = self.knowledge.repository.get(workspace, next_id)
            lineage.append({'id': candidate['id'], 'title': candidate['title'],
                            'version': candidate['version']})
            next_id = candidate.get('predecessorCandidateId')
        rows, total = self.repository.list_for_candidates(workspace, list(visited), limit, offset)
        return {'items': [self.get(workspace, row['id']) for row in rows],
                'lineage': lineage, 'total': total, 'limit': limit, 'offset': offset}

    def plugin_history(self, workspace: str, plugin_id: str,
                       limit: int = 20, offset: int = 0) -> dict[str, Any]:
        if self.plugins is None:
            raise KeyError(plugin_id)
        try:
            self.plugins.detail(workspace, plugin_id)
        except KeyError:
            # Removed methods retain read-only evidence, scoped to this workspace.
            existing = self.repository.postgres.fetch_one(
                'SELECT 1 FROM workbench.t_lifeweave_evaluation '
                'WHERE workspace_key=%s AND plugin_id=%s LIMIT 1', (workspace, plugin_id))
            if not existing:
                raise
        rows, total = self.repository.list_for_plugin(workspace, plugin_id, limit, offset)
        return {'items': [self.get(workspace, row['id']) for row in rows],
                'total': total, 'limit': limit, 'offset': offset}

    def start(self, workspace: str, evaluation_id: str, *, engine: str, permission: str, model: str | None,
              directory: str | None, method_id: str | None, knowledge_refs: list[str]) -> dict[str, Any]:
        with self.repository.postgres.atomic():
            row = self.repository.get(workspace, evaluation_id, lock=True)
            if row['state'] != 'planned':
                raise ValueError('评测已开始，不能重复创建运行')
            if row['targetKind'] == 'plugin':
                raise ValueError('插件评测已绑定真实调用，不能重复启动')
            candidate_id = row['candidateId']
            if candidate_id:
                candidate = self.knowledge.repository.get(workspace, candidate_id)
                if candidate['version'] != row['candidateVersion'] or candidate['status'] not in ('candidate', 'verified'):
                    raise ValueError('候选版本或状态已变化，请创建新的评测任务')
            instruction = f"{row['instruction'].strip()}\n\n本次评测通过标准：\n{row['criteria'].strip()}\n\n请保留过程、来源与不足，供人审阅。"
            run = self.runtime.create_run(workspace, item_id=row['itemId'], instruction=instruction,
                                          engine=engine, permission=permission, model=model,
                                          directory=directory or None, method_id=method_id or None,
                                          knowledge_refs=knowledge_refs,
                                          capability_candidate_id=candidate_id, actor_id='local-user')
            self.repository.bind_run(workspace, evaluation_id, run['id'])
        return self.get(workspace, evaluation_id)

    def assess(self, workspace: str, evaluation_id: str, *, outcome: str, assessment: str,
               evidence_id: str | None) -> dict[str, Any]:
        with self.repository.postgres.atomic():
            row = self.repository.get(workspace, evaluation_id, lock=True)
            if row['state'] != 'running' or (not row['runId'] and not row.get('pluginCallId')):
                raise ValueError('评测尚未运行或已经评估')
            run = self.runtime.get_run(workspace, row['runId']) if row['runId'] else None
            if run:
                if run['item_id'] != row['itemId']:
                    raise ValueError('运行与评测事项不一致')
                if run['state'] not in ('succeeded', 'failed', 'unavailable', 'cancelled'):
                    raise ValueError('运行尚未结束，暂不能判断')
            call = self._plugin_call(workspace, row['pluginCallId']) if row.get('pluginCallId') else None
            if call and (call['plugin_id'] != row['pluginId'] or call['plugin_version'] != row['pluginVersion']
                         or call['item_id'] != row['itemId'] or call['run_id'] != row['runId']):
                raise ValueError('插件评测的固定调用身份已变化')
            if outcome == 'passed':
                if call and call['state'] != 'succeeded':
                    raise ValueError('通过评测需要真实成功结束的插件调用')
                if run and run['state'] != 'succeeded':
                    raise ValueError('通过评测需要真实成功结束的运行')
                if run:
                    evidence = next((entry for entry in self.work.repository.list_evidence(workspace, row['itemId'])
                                     if entry['id'] == evidence_id), None)
                    if not evidence or evidence.get('runId') != row['runId'] or evidence['status'] != 'accepted':
                        raise ValueError('通过评测需要本次运行中已人工接受的证据')
                if row['candidateId']:
                    candidate = self.knowledge.repository.get(workspace, row['candidateId'])
                    if candidate['version'] != row['candidateVersion']:
                        raise ValueError('候选版本已变化，请创建新的评测任务')
                    self.knowledge.verify(workspace, row['candidateId'],
                                          {'runId': row['runId'], 'evidenceId': evidence_id,
                                           'result': 'accepted', 'assessment': assessment}, 'local-user')
            self.repository.assess(workspace, evaluation_id, outcome, assessment,
                                   evidence_id if outcome == 'passed' else None)
        return self.get(workspace, evaluation_id)

    def ensure_publishable(self, workspace: str, candidate_id: str, version: str) -> None:
        with self.repository.postgres.atomic() as conn:
            candidate = self.knowledge.repository.get(workspace, candidate_id)
            if candidate['version'] != version:
                raise ValueError('候选版本已改变，请刷新后再发布')
            current = self.repository.candidate_assessments(workspace, candidate_id, version)
            if not current:
                raise ValueError('此版本尚无显式评测任务；请先按任务和通过标准完成一次评测')
            if any(row['state'] != 'assessed' for row in current):
                raise ValueError('此版本还有未完成的评测任务，请先处理再发布')
            passed = [row for row in current if row['outcome'] == 'passed']
            if not passed:
                raise ValueError('此版本尚无通过的评测任务，不能发布')
            history = list(current)
            visited_candidates = {candidate_id}
            predecessor_id = candidate.get('predecessorCandidateId')
            while predecessor_id:
                if predecessor_id in visited_candidates:
                    raise ValueError('候选前任关系存在循环，不能发布')
                visited_candidates.add(predecessor_id)
                conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                             (f'lifeweave:evaluation:{workspace}:{predecessor_id}',))
                predecessor = self.knowledge.repository.get(workspace, predecessor_id)
                history.extend(self.repository.candidate_assessments(
                    workspace, predecessor_id, predecessor['version']))
                predecessor_id = predecessor.get('predecessorCandidateId')
            by_id = {row['id']: row for row in history}
            resolved: set[str] = set()
            for row in passed:
                previous = row.get('repeatOf')
                visited: set[str] = set()
                while previous and previous in by_id and previous not in visited:
                    visited.add(previous)
                    resolved.add(previous)
                    previous = by_id[previous].get('repeatOf')
            if any(row['state'] == 'assessed' and row['outcome'] != 'passed' and row['id'] not in resolved
                   for row in history):
                raise ValueError('当前候选或其前任仍有未解决的评测问题；需沿原任务的同一标准再评并通过')

    def create_improvement(self, workspace: str, evaluation_id: str, *, target_kind: str,
                           problem: str, desired_behavior: str, validation_plan: str) -> dict[str, Any]:
        with self.repository.postgres.atomic():
            row = self.repository.get(workspace, evaluation_id, lock=True)
            if row['state'] != 'assessed':
                raise ValueError('评测完成并记录判断后才能形成改进建议')
            if row.get('improvementId'):
                return self.get(workspace, evaluation_id)
            self.work.get_item(workspace, row['itemId'])
            improvement = self.work.create_entity(
                workspace, entity_type='improvement', title='改进：' + row['title'],
                payload={'sourceItemId': row['itemId'], 'sourceEvaluationId': row['id'],
                         'sourceRunId': row['runId'], 'sourceOutcome': row['outcome'],
                         'targetKind': target_kind,
                         'targetRef': row.get('pluginId') or row['candidateId'] or '',
                         'problem': problem.strip(), 'body': problem.strip(),
                         'desiredBehavior': desired_behavior.strip(),
                         'validationPlan': validation_plan.strip(), 'state': '草案'},
                actor_id='local-user',
            )
            self.work.create_relation(workspace, actor_id='local-user', from_kind='item',
                                      from_id=row['itemId'], to_kind='entity',
                                      to_id=improvement['id'], relation_type='produces')
            self.repository.attach_improvement(workspace, evaluation_id, improvement['id'])
        return self.get(workspace, evaluation_id)

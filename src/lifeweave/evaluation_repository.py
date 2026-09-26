from __future__ import annotations

from typing import Any

from src.database import PGConnector


class EvaluationRepository:
    def __init__(self, postgres: PGConnector) -> None:
        self.postgres = postgres
        self.table = f'{postgres.schema}.t_lifeweave_evaluation'

    @staticmethod
    def wire(row: dict[str, Any]) -> dict[str, Any]:
        names = {'workspace_key': 'workspace', 'item_id': 'itemId', 'target_kind': 'targetKind',
                 'candidate_id': 'candidateId', 'candidate_version': 'candidateVersion',
                 'repeat_of': 'repeatOf',
                 'plugin_id': 'pluginId', 'plugin_version': 'pluginVersion',
                 'plugin_call_id': 'pluginCallId',
                 'run_id': 'runId', 'evidence_id': 'evidenceId', 'improvement_id': 'improvementId',
                 'created_at': 'createdAt',
                 'assessed_at': 'assessedAt'}
        return {names.get(key, key): value for key, value in row.items()}

    def get(self, workspace: str, evaluation_id: str, *, lock: bool = False) -> dict[str, Any]:
        suffix = ' FOR UPDATE' if lock else ''
        row = self.postgres.fetch_one(
            f'SELECT * FROM {self.table} WHERE workspace_key=%s AND id=%s{suffix}',
            (workspace, evaluation_id),
        )
        if row is None:
            raise KeyError(evaluation_id)
        return self.wire(row)

    def list(self, workspace: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        rows = self.postgres.fetch_all(
            f'SELECT * FROM {self.table} WHERE workspace_key=%s ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s',
            (workspace, limit, offset),
        )
        count = self.postgres.fetch_one(f'SELECT count(*) AS total FROM {self.table} WHERE workspace_key=%s', (workspace,))
        return [self.wire(row) for row in rows], int(count['total']) if count else 0

    def list_for_candidates(self, workspace: str, candidate_ids: list[str], limit: int,
                            offset: int) -> tuple[list[dict[str, Any]], int]:
        rows = self.postgres.fetch_all(
            f'''SELECT * FROM {self.table} WHERE workspace_key=%s AND candidate_id=ANY(%s)
            ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s''',
            (workspace, candidate_ids, limit, offset),
        )
        count = self.postgres.fetch_one(
            f'SELECT count(*) AS total FROM {self.table} WHERE workspace_key=%s AND candidate_id=ANY(%s)',
            (workspace, candidate_ids),
        )
        return [self.wire(row) for row in rows], int(count['total']) if count else 0

    def list_for_plugin(self, workspace: str, plugin_id: str, limit: int,
                        offset: int) -> tuple[list[dict[str, Any]], int]:
        rows = self.postgres.fetch_all(
            f'''SELECT * FROM {self.table} WHERE workspace_key=%s AND plugin_id=%s
            ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s''',
            (workspace, plugin_id, limit, offset),
        )
        count = self.postgres.fetch_one(
            f'SELECT count(*) AS total FROM {self.table} WHERE workspace_key=%s AND plugin_id=%s',
            (workspace, plugin_id),
        )
        return [self.wire(row) for row in rows], int(count['total']) if count else 0

    def create(self, workspace: str, row: dict[str, Any]) -> dict[str, Any]:
        self.postgres.execute(
            f'''INSERT INTO {self.table}
            (id,workspace_key,item_id,target_kind,candidate_id,candidate_version,plugin_id,plugin_version,
             plugin_call_id,repeat_of,title,instruction,criteria,state,run_id)
            VALUES (%(id)s,%(workspace)s,%(itemId)s,%(targetKind)s,%(candidateId)s,%(candidateVersion)s,
                    %(pluginId)s,%(pluginVersion)s,%(pluginCallId)s,%(repeatOf)s,%(title)s,
                    %(instruction)s,%(criteria)s,%(state)s,%(runId)s)''',
            {**row, 'workspace': workspace},
        )
        return self.get(workspace, row['id'])

    def bind_run(self, workspace: str, evaluation_id: str, run_id: str) -> None:
        changed = self.postgres.execute(
            f"UPDATE {self.table} SET state='running',run_id=%s WHERE workspace_key=%s AND id=%s AND state='planned'",
            (run_id, workspace, evaluation_id),
        )
        if changed != 1:
            raise ValueError('评测已开始，请刷新后查看原运行')

    def assess(self, workspace: str, evaluation_id: str, outcome: str, assessment: str, evidence_id: str | None) -> None:
        changed = self.postgres.execute(
            f"""UPDATE {self.table} SET state='assessed',outcome=%s,assessment=%s,evidence_id=%s,
            assessed_at=now() WHERE workspace_key=%s AND id=%s AND state='running'""",
            (outcome, assessment, evidence_id, workspace, evaluation_id),
        )
        if changed != 1:
            raise ValueError('评测状态已变化，请刷新后重试')

    def attach_improvement(self, workspace: str, evaluation_id: str, improvement_id: str) -> None:
        changed = self.postgres.execute(
            f"UPDATE {self.table} SET improvement_id=%s WHERE workspace_key=%s AND id=%s AND state='assessed' AND improvement_id IS NULL",
            (improvement_id, workspace, evaluation_id),
        )
        if changed != 1:
            raise ValueError('改进建议已建立，请刷新查看')

    def candidate_assessments(self, workspace: str, candidate_id: str, version: str) -> list[dict[str, Any]]:
        return [self.wire(row) for row in self.postgres.fetch_all(
            f'''SELECT * FROM {self.table} WHERE workspace_key=%s AND candidate_id=%s AND candidate_version=%s
            ORDER BY assessed_at DESC NULLS FIRST, created_at DESC''',
            (workspace, candidate_id, version),
        )]

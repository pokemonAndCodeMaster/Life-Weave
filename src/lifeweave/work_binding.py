"""Resolve a conversation or execution to one item before starting work."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from typing import Literal

from pydantic import Field, model_validator

from .models import ItemType, WireModel
from .repository import ConcurrentUpdateError


class WorkBindingInput(WireModel):
    request_id: str = Field(alias='requestId', min_length=1, max_length=128)
    decision: Literal['auto', 'continue', 'child', 'new'] = 'auto'
    item_id: str | None = Field(default=None, alias='itemId', max_length=64)
    parent_id: str | None = Field(default=None, alias='parentId', max_length=64)
    conversation_id: str | None = Field(default=None, alias='conversationId', max_length=128)
    session_id: str | None = Field(default=None, alias='sessionId', max_length=128)
    title: str | None = Field(default=None, max_length=256)
    goal: str | None = Field(default=None, max_length=5000)
    item_type: ItemType = Field(default='requirement', alias='itemType')
    distinct_goal: bool = Field(default=False, alias='distinctGoal')
    payload: dict[str, Any] = Field(default_factory=dict)
    initial_context: dict[str, Any] | None = Field(default=None, alias='initialContext')
    provenance: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_decision(self) -> 'WorkBindingInput':
        if self.decision in {'child', 'new'} and not (self.title and self.title.strip() and self.goal and self.goal.strip()):
            raise ValueError('新建事项或子事项须明确标题与目标')
        if self.decision == 'child' and not self.parent_id:
            raise ValueError('创建子事项须指定父事项')
        if self.decision == 'continue' and not (self.item_id or self.conversation_id or self.session_id):
            raise ValueError('接续须指定事项、已绑定对话或执行')
        if self.item_id and self.decision in {'child', 'new'}:
            raise ValueError('创建新事项时不能同时指定要接续的事项')
        if self.decision == 'new' and self.payload.get('parentId'):
            raise ValueError('新事项包含父事项时须选择 child 决定')
        if self.decision == 'child' and self.payload.get('parentId') not in {None, self.parent_id}:
            raise ValueError('子事项 payload.parentId 与所选父事项不一致')
        return self


class WorkBindingService:
    def __init__(self, work):
        self.work = work
        self.db = work.repository._postgres

    @staticmethod
    def _receipt(workspace: str, request_id: str) -> str:
        return 'work-binding-' + hashlib.sha256(f'{workspace}:{request_id}'.encode()).hexdigest()[:32]

    def resolve(self, workspace: str, body: WorkBindingInput, actor_id: str) -> dict:
        workspace = self.work._workspace(workspace)
        submitted = body.model_dump(by_alias=True, exclude_none=True)
        fingerprint = hashlib.sha256(json.dumps(submitted, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        identity = self._receipt(workspace, body.request_id)
        with self.db.atomic() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                         (f'work-binding:{workspace}:{body.request_id}',))
            existing = conn.execute(f'SELECT * FROM {self.work.repository.activities} WHERE id=%s',
                                    (identity,)).fetchone()
            if existing:
                if existing['workspace_key'] != workspace or existing['payload'].get('requestFingerprint') != fingerprint:
                    raise ConcurrentUpdateError('同一请求标识已用于不同事项绑定')
                return existing['payload']['binding']

            explicit = self.work.get_item(workspace, body.item_id) if body.item_id else None
            conversation_item = None
            if body.conversation_id:
                conversation = conn.execute(
                    'SELECT item_id FROM workbench.lifeweave_conversation '
                    'WHERE workspace=%s AND id=%s FOR UPDATE',
                    (workspace, body.conversation_id)).fetchone()
                if not conversation:
                    raise KeyError(body.conversation_id)
                conversation_item = conversation['item_id']
            bound_session = None
            if body.session_id:
                activity = conn.execute(
                    f'SELECT item_id FROM {self.work.repository.activities} '
                    "WHERE workspace_key=%s AND (kind='work_binding' OR kind='external_development_start') "
                    "AND (payload->>'sessionId'=%s OR payload->'binding'->>'sessionId'=%s) "
                    'ORDER BY created_at DESC LIMIT 1',
                    (workspace, body.session_id, body.session_id)).fetchone()
                bound_session = activity['item_id'] if activity else None
            bound_ids = {value for value in (conversation_item, bound_session) if value}
            if len(bound_ids) > 1 or (explicit and bound_ids and explicit['id'] not in bound_ids):
                raise ConcurrentUpdateError('显式事项与已绑定对话或执行不一致')

            resolved_id = explicit['id'] if explicit else next(iter(bound_ids), None)
            if body.decision in {'child', 'new'} and resolved_id:
                raise ConcurrentUpdateError('对话或执行已绑定旧事项；请接续，或使用新会话创建新目标')
            if body.decision == 'child':
                self.work.get_item(workspace, body.parent_id)
            if body.title:
                conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                             (f'work-title:{workspace}:{body.title.strip().casefold()}',))
            candidates = []
            if body.title:
                rows, _ = self.work.list_items(workspace, query=body.title.strip(), limit=None, offset=0)
                candidates = [{'id': row['id'], 'title': row['title'], 'itemType': row['itemType'],
                               'status': row['status']} for row in rows]
            exact = [row for row in candidates if row['title'].strip().casefold() == (body.title or '').strip().casefold()]
            if body.decision == 'auto' and not resolved_id:
                if len(exact) == 1:
                    resolved_id = exact[0]['id']
                else:
                    return {'action': 'needs_choice', 'itemId': None, 'candidates': candidates}
            if body.decision == 'continue' and not resolved_id:
                return {'action': 'needs_choice', 'itemId': None, 'candidates': candidates}
            if body.decision in {'child', 'new'} and exact and not body.distinct_goal:
                return {'action': 'needs_choice', 'itemId': None, 'candidates': candidates,
                        'reason': '已有同名事项；确认独立目标后才新建'}

            action = 'bound'
            if body.decision in {'child', 'new'}:
                parent = body.parent_id if body.decision == 'child' else None
                payload = {**body.payload, 'goal': body.goal.strip()}
                if parent:
                    payload['parentId'] = parent
                item = self.work.create_item(workspace, item_type=body.item_type,
                                             title=body.title.strip(), status='open', payload=payload,
                                             actor_id=actor_id, initial_context=body.initial_context,
                                             provenance=body.provenance)
                resolved_id = item['id']
                action = 'created_child' if parent else 'created'
            if not resolved_id:
                raise ValueError('尚未确定事项归属')
            self.work.get_item(workspace, resolved_id)
            if body.conversation_id and not conversation_item:
                conn.execute('UPDATE workbench.lifeweave_conversation SET item_id=%s,updated_at=now() '
                             'WHERE workspace=%s AND id=%s AND item_id IS NULL',
                             (resolved_id, workspace, body.conversation_id))
            result = {'action': action, 'itemId': resolved_id, 'parentId': body.parent_id if action == 'created_child' else None,
                      'conversationId': body.conversation_id, 'sessionId': body.session_id, 'candidates': []}
            self.work.repository.append_activity(workspace, resolved_id, {
                'id': identity, 'kind': 'work_binding', 'body': f'工作归属：{action}',
                'payload': {'requestFingerprint': fingerprint, 'binding': result,
                            'sessionId': body.session_id}, 'actor': actor_id})
            return result

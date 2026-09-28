"""Govern topic, domain, and parent relations without changing work history."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from .item_organization_models import OrganizationProposalInput, OrganizationRulesInput
from .repository import ConcurrentUpdateError


PARENT_TYPES = {'part_of', 'contributes_to'}
RULE_KEY = 'item-organization-rules'


class ItemOrganizationService:
    def __init__(self, work: Any):
        self.work = work
        self.repo = work.repository
        self.db = self.repo._postgres
        self.table = f'{self.db.schema}.t_lifeweave_organization_proposal'

    def _workspace(self, workspace: str) -> str:
        return self.work._workspace(workspace)

    @staticmethod
    def _fingerprint(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        result = {'id': row['id'], 'status': row['status'], 'reason': row['reason'],
                  'changes': row['changes'], 'groups': row['groups'], 'warnings': row['warnings'],
                  'createdAt': row['created_at'].isoformat(),
                  'appliedAt': row['applied_at'].isoformat() if row['applied_at'] else None,
                  'undoneAt': row['undone_at'].isoformat() if row['undone_at'] else None,
                  'createdBy': row['created_by']}
        return result

    def _rules_record(self, workspace: str) -> dict[str, Any] | None:
        return self.repo._one(f'SELECT workspace_key,preference_key,payload,version,updated_by,updated_at '
                              f'FROM {self.repo.preferences} WHERE workspace_key=%(workspace)s AND preference_key=%(key)s',
                              {'workspace': workspace, 'key': RULE_KEY})

    def rules(self, workspace: str) -> dict[str, Any]:
        record = self._rules_record(self._workspace(workspace))
        return {'version': record['version'] if record else None,
                'rules': (record['payload'].get('rules') or []) if record else []}

    def save_rules(self, workspace: str, body: OrganizationRulesInput, actor_id: str) -> dict[str, Any]:
        workspace = self._workspace(workspace)
        for rule in body.rules:
            if not rule.terms or any(not term.strip() for term in rule.terms):
                raise ValueError(f'规则 {rule.id} 必须提供明确且非空的匹配词')
            self._validate_entities(workspace, rule.topic_ids, rule.domain_ids)
        result = self.repo.save_preference(workspace, RULE_KEY,
                                           {'rules': [rule.model_dump(by_alias=True) for rule in body.rules]},
                                           body.version, actor_id)
        return {'version': result['version'], 'rules': result['payload']['rules']}

    def _validate_entities(self, workspace: str, topics: list[str], domains: list[str]) -> None:
        for ids, entity_type in ((topics, 'topic'), (domains, 'domain')):
            if len(ids) != len(set(ids)):
                raise ValueError(f'{entity_type} ID 不可重复')
            for identity in ids:
                entity = self.repo.get_entity(workspace, identity)
                if not entity or entity['entityType'] != entity_type:
                    raise ValueError(f'{entity_type} 不存在于当前空间：{identity}')

    def _organization(self, workspace: str, item_id: str) -> dict[str, Any]:
        item = self.work.get_item(workspace, item_id)
        relations = self.repo.list_relations(workspace, item_id)
        outbound = [row for row in relations if row['fromKind'] == 'item' and row['fromId'] == item_id]
        parent = [row['toId'] for row in outbound if row['toKind'] == 'item' and row['relationType'] in PARENT_TYPES]
        if len(set(parent)) > 1:
            raise ValueError(f'事项 {item_id} 存在多个父级，请先明确唯一父级')
        topic_ids, domain_ids = [], []
        for row in outbound:
            if row['toKind'] != 'entity' or row['relationType'] != 'serves':
                continue
            entity = self.repo.get_entity(workspace, row['toId'])
            if entity and entity['entityType'] == 'topic': topic_ids.append(entity['id'])
            if entity and entity['entityType'] == 'domain': domain_ids.append(entity['id'])
        return {'topicIds': sorted(set(topic_ids)), 'domainIds': sorted(set(domain_ids)),
                'parentId': parent[0] if parent else None}

    def _relations_snapshot(self, workspace: str, item_id: str) -> list[dict[str, Any]]:
        rows = []
        for relation in self.repo.list_relations(workspace, item_id):
            if relation['fromKind'] != 'item' or relation['fromId'] != item_id:
                continue
            if relation['toKind'] == 'item' and relation['relationType'] in PARENT_TYPES:
                pass
            elif relation['toKind'] == 'entity' and relation['relationType'] == 'serves':
                entity = self.repo.get_entity(workspace, relation['toId'])
                if not entity or entity['entityType'] not in {'topic', 'domain'}:
                    continue
            else:
                continue
            rows.append({'id': relation['id'], 'fromKind': relation['fromKind'], 'fromId': relation['fromId'],
                         'toKind': relation['toKind'], 'toId': relation['toId'],
                         'relationType': relation['relationType'], 'createdBy': relation['createdBy'],
                         'createdAt': relation['createdAt'].isoformat() if hasattr(relation['createdAt'], 'isoformat') else relation['createdAt']})
        return sorted(rows, key=lambda row: row['id'])

    def _rule_match(self, workspace: str, item: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        source = ' '.join([item['title'], str((item.get('payload') or {}).get('goal') or '')]).casefold()
        matched = [rule for rule in self.rules(workspace)['rules'] if rule['enabled'] and
                   any(term.strip().casefold() in source for term in rule['terms'])]
        if not matched:
            return None, '没有命中已维护的明确分类规则'
        targets = {(tuple(sorted(rule['topicIds'])), tuple(sorted(rule['domainIds']))) for rule in matched}
        if len(targets) != 1:
            return None, '多条规则指向不同分类，保留待人工判断'
        target = matched[0]
        return {'topicIds': target['topicIds'], 'domainIds': target['domainIds']}, f'明确规则：{", ".join(rule["title"] for rule in matched)}'

    def classify_new(self, workspace: str, item: dict[str, Any], parent_id: str | None,
                     explicit_topics: list[str] | None, explicit_domains: list[str] | None,
                     actor_id: str) -> None:
        """Called inside the create transaction, after the item row exists."""
        workspace = self._workspace(workspace)
        parent = self._organization(workspace, parent_id) if parent_id else None
        matched, reason = ((None, '') if parent or explicit_topics is not None or explicit_domains is not None
                           else self._rule_match(workspace, item))
        topics = explicit_topics if explicit_topics is not None else (parent['topicIds'] if parent else (matched or {}).get('topicIds', []))
        domains = explicit_domains if explicit_domains is not None else (parent['domainIds'] if parent else (matched or {}).get('domainIds', []))
        self._validate_entities(workspace, topics, domains)
        for entity_id in [*topics, *domains]:
            self.work.create_relation(workspace, actor_id=actor_id, from_kind='item', from_id=item['id'],
                                      to_kind='entity', to_id=entity_id, relation_type='serves')
        if parent_id:
            self.work.create_relation(workspace, actor_id=actor_id, from_kind='item', from_id=item['id'],
                                      to_kind='item', to_id=parent_id, relation_type='part_of')
        if topics or domains or parent_id:
            source = '显式分类' if explicit_topics is not None or explicit_domains is not None else ('继承父事项' if parent else reason)
            self.work.append_activity(workspace, item['id'], kind='item_organization_auto',
                                      body=f'创建时分类：{source}', actor_id=actor_id,
                                      payload={'source': source, 'topicIds': topics, 'domainIds': domains, 'parentId': parent_id})

    def catalog(self, workspace: str) -> dict[str, Any]:
        workspace = self._workspace(workspace)
        items, _ = self.work.list_items(workspace, limit=None)
        projected = []
        for item in items:
            projected.append({key: item[key] for key in ('id', 'title', 'status', 'version', 'itemType')} |
                             self._organization(workspace, item['id']) |
                             {'organizationStatus': (item.get('payload') or {}).get('organizationBatchStatus')})
        proposals = self.db.fetch_all(f'SELECT * FROM {self.table} WHERE workspace_key=%s ORDER BY created_at DESC LIMIT 100', (workspace,))
        rules = self.rules(workspace)
        return {'workspace': workspace, 'topics': self.repo.list_entities(workspace, 'topic'),
                'domains': self.repo.list_entities(workspace, 'domain'), 'items': projected,
                'unorganizedItems': [row for row in projected if not row['topicIds'] and not row['domainIds']],
                'rules': rules['rules'], 'rulesVersion': rules['version'],
                'proposals': [self._public(row) for row in proposals]}

    def get_proposal(self, workspace: str, proposal_id: str) -> dict[str, Any]:
        workspace = self._workspace(workspace)
        row = self.db.fetch_one(f'SELECT * FROM {self.table} WHERE workspace_key=%s AND id=%s', (workspace, proposal_id))
        if not row: raise KeyError(proposal_id)
        return self._public(row)

    def propose(self, workspace: str, body: OrganizationProposalInput, actor_id: str) -> dict[str, Any]:
        workspace = self._workspace(workspace)
        submitted = body.model_dump(by_alias=True, exclude_unset=True)
        fingerprint = self._fingerprint(submitted)
        with self.db.atomic() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (f'organization:{workspace}',))
            old = conn.execute(f'SELECT * FROM {self.table} WHERE workspace_key=%s AND request_id=%s',
                               (workspace, body.request_id)).fetchone()
            if old:
                if old['request_fingerprint'] != fingerprint:
                    raise ConcurrentUpdateError('同一请求标识已用于不同整理建议')
                return self._public(old)
            explicit = {change.item_id: change for change in body.changes or []}
            groups = [group.model_dump(by_alias=True) for group in body.groups or []]
            group_keys = {group['key'] for group in groups}
            memberships: dict[str, str] = {}
            for group in groups:
                existing, _ = self.work.list_items(workspace, query=group['title'], limit=None)
                if any(item['title'].strip().casefold() == group['title'].strip().casefold() for item in existing):
                    raise ValueError(f'同名事项已存在：{group["title"]}；请显式选择其 ID 作为父项')
                for item_id in group['itemIds']:
                    if item_id in memberships:
                        raise ValueError(f'事项 {item_id} 不可属于多个聚合组')
                    memberships[item_id] = group['key']
            target_ids = list(dict.fromkeys([*(body.item_ids or []), *explicit, *memberships]))
            if not target_ids:
                raise ValueError('请选择需要整理的事项')
            changes, warnings = [], []
            for item_id in target_ids:
                item = self.work.get_item(workspace, item_id)
                before = self._organization(workspace, item_id)
                requested = explicit.get(item_id)
                if requested and requested.item_version != item['version']:
                    raise ConcurrentUpdateError(f'事项 {item_id} 版本已变化')
                after = dict(before)
                reason = requested.reason if requested else ''
                if requested:
                    if requested.topic_ids is not None: after['topicIds'] = requested.topic_ids
                    if requested.domain_ids is not None: after['domainIds'] = requested.domain_ids
                    if requested.changes_parent: after['parentId'] = requested.parent_id
                if item_id in memberships:
                    if requested and requested.changes_parent:
                        raise ValueError(f'事项 {item_id} 同时指定了父项和聚合组')
                    after['parentId'] = f'group:{memberships[item_id]}'
                    reason = (reason + '；' if reason else '') + '显式聚合到一级事项'
                if not requested:
                    if before['parentId']:
                        inherited = self._organization(workspace, before['parentId'])
                        if not before['topicIds']: after['topicIds'] = inherited['topicIds']
                        if not before['domainIds']: after['domainIds'] = inherited['domainIds']
                        reason = reason or '继承现有父事项分类'
                    else:
                        if not before['topicIds'] and not before['domainIds']:
                            matched, reason = self._rule_match(workspace, item)
                            if matched:
                                after['topicIds'] = matched['topicIds']
                                after['domainIds'] = matched['domainIds']
                        else:
                            reason = '事项已有分类，不自动覆盖'
                self._validate_entities(workspace, after['topicIds'], after['domainIds'])
                if after['parentId'] and not after['parentId'].startswith('group:'):
                    self.work.get_item(workspace, after['parentId'])
                if after['parentId'] and after['parentId'].startswith('group:') and after['parentId'][6:] not in group_keys:
                    raise ValueError(f'聚合组不存在：{after["parentId"]}')
                if after == before:
                    warnings.append(f'{item["title"]}：{reason or "没有可确定的分类变化"}')
                    continue
                changes.append({'itemId': item_id, 'itemVersion': item['version'], 'title': item['title'],
                                'before': before, 'after': after, 'reason': reason,
                                'beforeRelations': self._relations_snapshot(workspace, item_id)})
            by_item = {change['itemId']: change['after'] for change in changes}
            for group in groups:
                classifications = [by_item.get(item_id) or self._organization(workspace, item_id)
                                   for item_id in group['itemIds']]
                owners = [(self.work.get_item(workspace, item_id).get('payload') or {}).get('owner')
                          for item_id in group['itemIds']]
                group['owner'] = owners[0] if owners and isinstance(owners[0], str) and owners[0].strip() and all(owner == owners[0] for owner in owners) else None
                common_topics = set(classifications[0]['topicIds'])
                common_domains = set(classifications[0]['domainIds'])
                for classification in classifications[1:]:
                    common_topics.intersection_update(classification['topicIds'])
                    common_domains.intersection_update(classification['domainIds'])
                if not common_topics and not common_domains:
                    match, _ = self._rule_match(workspace, {'title': group['title'], 'payload': {'goal': group['goal']}})
                    if match:
                        common_topics, common_domains = set(match['topicIds']), set(match['domainIds'])
                if not common_topics and not common_domains:
                    raise ValueError(f'聚合事项 {group["title"]} 缺少共同分类或明确规则')
                group['topicIds'] = sorted(common_topics)
                group['domainIds'] = sorted(common_domains)
            self._validate_parent_graph(workspace, changes, memberships)
            identity = 'orgp-' + uuid4().hex[:24]
            row = conn.execute(f'INSERT INTO {self.table}(id,workspace_key,request_id,request_fingerprint,reason,changes,groups,warnings,created_by) '
                               'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                               (identity, workspace, body.request_id, fingerprint, body.reason,
                                Jsonb(changes), Jsonb(groups), Jsonb(warnings), actor_id)).fetchone()
            return self._public(row)

    def _validate_parent_graph(self, workspace: str, changes: list[dict[str, Any]], groups: dict[str, str] | None = None) -> None:
        items, _ = self.work.list_items(workspace, limit=None)
        parents = {item['id']: self._organization(workspace, item['id'])['parentId'] for item in items}
        parents.update({row['itemId']: row['after']['parentId'] for row in changes})
        for item_id in parents:
            seen = set()
            current = item_id
            while current and current in parents:
                if current in seen: raise ValueError('聚合关系形成循环')
                seen.add(current)
                current = parents[current]

    def _replace_relations(self, workspace: str, item_id: str, desired: dict[str, Any], actor_id: str,
                           restore: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        for row in self._relations_snapshot(workspace, item_id):
            self.repo.delete_relation(workspace, row['id'])
        if restore is not None:
            for row in restore:
                self.db.execute(f'INSERT INTO {self.repo.relations}(id,workspace_key,from_kind,from_id,to_kind,to_id,relation_type,created_by,created_at) '
                                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                (row['id'], workspace, row['fromKind'], row['fromId'], row['toKind'], row['toId'],
                                 row['relationType'], row['createdBy'], row['createdAt']))
        else:
            for entity_id in [*desired['topicIds'], *desired['domainIds']]:
                self.work.create_relation(workspace, actor_id=actor_id, from_kind='item', from_id=item_id,
                                          to_kind='entity', to_id=entity_id, relation_type='serves')
            if desired['parentId']:
                self.work.create_relation(workspace, actor_id=actor_id, from_kind='item', from_id=item_id,
                                          to_kind='item', to_id=desired['parentId'], relation_type='part_of')
        return self._relations_snapshot(workspace, item_id)

    def _action(self, workspace: str, proposal_id: str, request_id: str, actor_id: str, undo: bool) -> dict[str, Any]:
        workspace = self._workspace(workspace)
        with self.db.atomic() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (f'organization:{workspace}',))
            row = conn.execute(f'SELECT * FROM {self.table} WHERE workspace_key=%s AND id=%s FOR UPDATE',
                               (workspace, proposal_id)).fetchone()
            if not row: raise KeyError(proposal_id)
            action_key = 'undoRequestId' if undo else 'applyRequestId'
            desired_status = 'undone' if undo else 'applied'
            receipt = dict(row['receipt'])
            if row['status'] == desired_status and receipt.get(action_key) == request_id:
                return self._public(row)
            if row['status'] != ('applied' if undo else 'proposed'):
                raise ConcurrentUpdateError('整理批次状态已经变化')
            if undo and receipt.get('undoRequestId'):
                raise ConcurrentUpdateError('撤销请求已使用')
            if not undo and receipt.get('applyRequestId'):
                raise ConcurrentUpdateError('应用请求已使用')
            # Direct relation writes do not acquire the organization advisory lock.
            conn.execute(f'LOCK TABLE {self.repo.relations} IN SHARE ROW EXCLUSIVE MODE')
            changes = row['changes']
            affected = sorted({change['itemId'] for change in changes})
            if affected:
                conn.execute(f'SELECT id FROM {self.repo.items} WHERE workspace_key=%s AND id=ANY(%s) ORDER BY id FOR UPDATE',
                             (workspace, affected))
            for change in changes:
                item = self.work.get_item(workspace, change['itemId'])
                current = self._organization(workspace, change['itemId'])
                expected = change['after'] if undo else change['before']
                if undo and expected['parentId'] and str(expected['parentId']).startswith('group:'):
                    expected = {**expected, 'parentId': receipt.get('groupItems', {}).get(expected['parentId'][6:])}
                if current != expected:
                    raise ConcurrentUpdateError(f'事项 {change["itemId"]} 的组织关系已变化')
                if not undo and item['version'] != change['itemVersion']:
                    raise ConcurrentUpdateError(f'事项 {change["itemId"]} 的版本已变化')
                if undo and self._relations_snapshot(workspace, change['itemId']) != receipt.get('afterRelations', {}).get(change['itemId']):
                    raise ConcurrentUpdateError(f'事项 {change["itemId"]} 的组织关系已变化')
            if undo:
                restore_changes = [{**change, 'after': change['before']} for change in changes]
                try:
                    self._validate_parent_graph(workspace, restore_changes)
                except ValueError as exc:
                    raise ConcurrentUpdateError('撤销将与后续父子关系形成循环，请先整理新的关系') from exc
            if not undo:
                self._validate_parent_graph(workspace, changes)
                group_items = {}
                for group in row['groups']:
                    existing, _ = self.work.list_items(workspace, query=group['title'], limit=None)
                    if any(item['title'].strip().casefold() == group['title'].strip().casefold() for item in existing):
                        raise ConcurrentUpdateError(f'同名聚合事项已出现：{group["title"]}')
                    created = self.work.create_item(workspace, item_type='requirement', title=group['title'],
                                                    status='open', payload={'goal': group['goal'],
                                                                            'topicIds': group['topicIds'],
                                                                            'domainIds': group['domainIds'],
                                                                            'owner': group.get('owner'),
                                                                            'organizationBatchId': proposal_id,
                                                                            'organizationBatchStatus': 'active'}, actor_id=actor_id)
                    group_items[group['key']] = created['id']
                receipt['groupItems'] = group_items
            else:
                group_items = receipt.get('groupItems', {})
            # Remove every old organization edge before rebuilding the batch.
            # Otherwise a valid parent swap can fail on a transient cycle that
            # exists only because one row was rebuilt before another was cut.
            for change in changes:
                for relation in self._relations_snapshot(workspace, change['itemId']):
                    self.repo.delete_relation(workspace, relation['id'])
            after_relations = {}
            for change in changes:
                target = change['before'] if undo else change['after']
                if target['parentId'] and str(target['parentId']).startswith('group:'):
                    target = {**target, 'parentId': group_items[target['parentId'][6:]]}
                self._validate_entities(workspace, target['topicIds'], target['domainIds'])
                if target['parentId']:
                    self.work.get_item(workspace, target['parentId'])
                new_relations = self._replace_relations(workspace, change['itemId'], target, actor_id,
                                                         restore=change['beforeRelations'] if undo else None)
                if not undo: after_relations[change['itemId']] = new_relations
                item = self.work.get_item(workspace, change['itemId'])
                payload = dict(item['payload'])
                if target['parentId']: payload['parentId'] = target['parentId']
                else: payload.pop('parentId', None)
                self.work.update_item(workspace, change['itemId'], version=item['version'], actor_id=actor_id, payload=payload)
                self.work.append_activity(workspace, change['itemId'], kind='item_organization_undone' if undo else 'item_organization_applied',
                                          body=change['reason'] or ('撤销事项整理' if undo else '应用事项整理'), actor_id=actor_id,
                                          payload={'proposalId': proposal_id, 'before': change['before'], 'after': change['after']})
            if not undo:
                receipt['afterRelations'] = after_relations
            else:
                for group_id in group_items.values():
                    group_item = self.work.get_item(workspace, group_id)
                    group_payload = {**group_item['payload'], 'organizationBatchStatus': 'undone'}
                    self.work.update_item(workspace, group_id, version=group_item['version'], actor_id=actor_id,
                                          payload=group_payload)
                if group_items:
                    row['warnings'].append('聚合已撤销；新建的一级事项保留并标记为已撤销，已有工作和成果不删除')
            receipt[action_key] = request_id
            updated = conn.execute(f'UPDATE {self.table} SET status=%s,receipt=%s,warnings=%s, '
                                   + ('undone_by=%s,undone_at=now()' if undo else 'applied_by=%s,applied_at=now()')
                                   + ' WHERE id=%s RETURNING *',
                                   (desired_status, Jsonb(receipt), Jsonb(row['warnings']), actor_id, proposal_id)).fetchone()
            return self._public(updated)

    def apply(self, workspace: str, proposal_id: str, request_id: str, actor_id: str) -> dict[str, Any]:
        return self._action(workspace, proposal_id, request_id, actor_id, undo=False)

    def undo(self, workspace: str, proposal_id: str, request_id: str, actor_id: str) -> dict[str, Any]:
        return self._action(workspace, proposal_id, request_id, actor_id, undo=True)

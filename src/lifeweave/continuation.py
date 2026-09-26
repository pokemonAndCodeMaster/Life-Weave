"""Read the current work through product-owned records, without session memory."""
import json
from datetime import datetime, timezone

from .discovery import match


class WorkContinuation:
    def __init__(self, work, runtime):
        self.work = work
        self.runtime = runtime

    def discover(self, workspace, query):
        workspace = self.work._workspace(workspace)
        items, _ = self.work.list_items(workspace, limit=None)
        ideas = self.work.repository.list_entities(workspace, 'idea')
        matches = []
        for kind, rows in (('item', items), ('idea', ideas)):
            for row in rows:
                context = (row.get('context') or {}).get('content') or {}
                ranking = match(query, row['title'] + ' ' + row['id'], json.dumps([row['payload'], context], ensure_ascii=False))
                if query.strip() and not ranking['score']:
                    continue
                matches.append({'kind': kind, 'id': row['id'], 'title': row['title'],
                                'status': row.get('status', row['payload'].get('state')),
                                'updatedAt': row['updatedAt'], **ranking})
        matches.sort(key=lambda row: (row['score'], str(row['updatedAt'])), reverse=True)
        return {'items': matches, 'total': len(matches), 'strategy': 'lexical-v1',
                'boundary': '文本匹配候选，不自动合并、创建或执行；没有命中不代表没有相关工作。'}

    def read(self, workspace, item_id):
        item = self.work.get_item(workspace, item_id)
        repo = self.work.repository
        context = self.work.current_context_snapshot(workspace, item_id)
        # Fetch every page. A continuation must not silently lose older attempts.
        runs = []
        while True:
            page, total = self.runtime.list_runs(workspace, item_id=item_id, limit=100, offset=len(runs))
            runs.extend(page)
            if len(runs) >= total:
                break
            if not page:
                raise ValueError('运行列表在读取时变化，请重新取得接续记录')
        discussion = repo.list_discussions(workspace, item_id=item_id)
        proposals = repo.list_proposals(workspace, item_id)
        external_development = [row for row in repo.list_activities(workspace, item_id)
                                if row['kind'] in {'external_development_start', 'external_development_event'}]
        parent_id = context.get('inheritedFromItemId')
        inherited = None
        if parent_id:
            inherited = {'itemId': parent_id, 'discussions': repo.list_discussions(workspace, item_id=parent_id),
                         'contextProposals': repo.list_proposals(workspace, parent_id)}
        return {'readAt': datetime.now(timezone.utc).isoformat(), 'item': item, 'context': context,
                'contextProposals': proposals, 'discussions': discussion, 'inherited': inherited,
                'externalDevelopment': external_development,
                'feedback': self.work.execution_feedback(workspace, item_id),
                'evidence': repo.list_evidence(workspace, item_id),
                'relations': repo.list_relations(workspace, item_id),
                'runs': [{k: row.get(k) for k in ('id', 'state', 'instruction', 'engine', 'result', 'error',
                         'retry_of', 'created_at', 'finished_at', 'context_version_id', 'capabilities')} for row in runs],
                'nextStep': {'declared': item['payload'].get('nextStep'),
                             'openProposalCount': sum(p['status'] == 'open' for p in proposals),
                             'note': '依据当前目标、待审候选、反馈、运行结果与已上报的外部开发记录决定下一步；读取不授权执行。'},
                'boundaries': ['这是读取时的当前记录，提交修改仍须携带版本。',
                               '方法推荐、输入加载、实际步骤执行是不同证据。',
                               '外部开发阶段与检查由会话主动上报，Git 状态由服务在上报时观测；它们不是平台 Run。',
                               '本机入口可用不表示 ChatGPT 或 Linear 已同步。']}

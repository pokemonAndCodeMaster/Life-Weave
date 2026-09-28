"""Short, sourced item introduction and current work projection."""
from __future__ import annotations

from typing import Any

from .repository import ConcurrentUpdateError


def _short(value: Any, limit: int = 500) -> str:
    if isinstance(value, list):
        value = '；'.join(str(part) for part in value if isinstance(part, (str, int, float)))
    if not isinstance(value, str):
        return ''
    return ' '.join(value.split())[:limit]


class ItemOverviewService:
    def __init__(self, work: Any):
        self.work = work

    def project(self, item: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
        payload = item.get('payload') or {}
        authored = payload.get('overview') if isinstance(payload.get('overview'), dict) else {}
        context = (item.get('context') or {}).get('content') or {}
        if not context and hasattr(getattr(self.work, 'repository', None), 'context'):
            context_record = self.work.repository.context(item.get('workspace', ''), item['id'])
            context = (context_record or {}).get('content') or {}
        values = {}
        sources = {}
        fallback = {
            'background': [('context', context.get('scope')), ('payload', payload.get('background'))],
            'intent': [('payload', payload.get('goal')), ('context', context.get('goal'))],
            'expectedResult': [('context', context.get('acceptance')), ('payload', payload.get('expectedResult'))],
        }
        for field, options in fallback.items():
            if field in authored:
                values[field] = _short(authored[field])
                sources[field] = 'item.overview'
            else:
                source, value = next(((source, value) for source, value in options if _short(value)), ('missing', ''))
                values[field] = _short(value)
                sources[field] = source
        nodes = view['plan']['nodes']
        completed = sum(node['state'] == 'succeeded' for node in nodes)
        active = next((node for node in nodes if node['state'] in {'running', 'waiting', 'failed', 'blocked'}), None)
        if active is None:
            active = next((node for node in nodes if node['state'] == 'planned'), None)
        if active is None and nodes:
            active = nodes[-1]
        effective_reports = [(node, attempt) for node in nodes for attempt in node.get('attempts', [])
                             if attempt.get('planVersion') == view['plan']['version'] and attempt.get('applied')]
        effective_reports.sort(key=lambda pair: pair[1].get('createdAt') or '', reverse=True)
        latest = effective_reports[0] if effective_reports else None
        active_report = next((attempt for node, attempt in effective_reports if active and node['id'] == active['id']), None)
        if active_report:
            progress_summary = _short(active_report.get('summary'), 600) or _short(active.get('summary'), 600)
            progress_source = 'step_report'
        elif latest:
            reported_node, reported = latest
            fact = _short(reported.get('summary'), 500) or _short(reported_node.get('summary'), 500)
            progress_summary = f'{reported_node["title"]}：{fact}' if fact else f'{reported_node["title"]}已记录报告'
            if active and active['id'] != reported_node['id'] and active['state'] != 'succeeded':
                progress_summary += f'；下一步：{active["title"]}'
            progress_source = 'step_report'
        elif active and active.get('summary'):
            progress_summary = _short(active['summary'], 600)
            progress_source = 'work_step'
        elif active and active['state'] == 'planned':
            progress_summary = f'尚未开始；下一步：{active["title"]}'
            progress_source = 'work_plan'
        elif active:
            progress_summary = f'{active["title"]}：{active["state"]}'
            progress_source = 'work_step'
        elif view['outputs']:
            latest_output = max(view['outputs'], key=lambda row: row.get('createdAt') or '')
            progress_summary = f'最近记录成果：{latest_output["title"]}；事项状态：{item["status"]}'
            progress_source = 'output'
        else:
            progress_summary = '暂无实际工作记录'
            progress_source = 'work_view'
        output_index = {output['id']: output for output in view['outputs']}
        output_ids = []
        for node in nodes:
            current_report = next((attempt for attempt in node.get('attempts', [])
                                   if attempt.get('applied') and attempt.get('outcome') == 'succeeded'
                                   and attempt.get('planVersion') == view['plan']['version']), None)
            candidates = current_report.get('outputIds', []) if current_report else node.get('outputIds', [])
            for output_id in candidates:
                if output_id in output_index and output_id not in output_ids:
                    output_ids.append(output_id)
        # The output catalog is historical. With no step reference, show only the
        # newest currently readable fixed delivery, research result, or manual result.
        for prefix in ('delivery:', 'run:', 'artifact:'):
            if any(identity.startswith(prefix) for identity in output_ids):
                continue
            candidates = [row for row in view['outputs'] if row['id'].startswith(prefix)]
            if prefix == 'run:':
                candidates = [row for row in candidates if row.get('kind') == 'research']
            if candidates:
                newest = max(candidates, key=lambda row: row.get('createdAt') or '')
                output_ids.append(newest['id'])
        return {**values,
                'progress': {'summary': progress_summary, 'state': active['state'] if active else view['current']['state'],
                             'completedSteps': completed, 'totalSteps': len(nodes)},
                'outputIds': output_ids,
                'sources': {**sources, 'progress': progress_source}}

    def save(self, workspace: str, item_id: str, *, version: int, background: str,
             intent: str, expected_result: str, actor_id: str, view_service: Any) -> dict[str, Any]:
        item = self.work.get_item(workspace, item_id)
        if item['version'] != version:
            raise ConcurrentUpdateError('事项已被其他人更新，请刷新后重试')
        payload = dict(item.get('payload') or {})
        payload['overview'] = {'background': background.strip(), 'intent': intent.strip(),
                               'expectedResult': expected_result.strip()}
        payload['goal'] = intent.strip()
        self.work.update_item(workspace, item_id, version=version, actor_id=actor_id, payload=payload)
        return view_service.read(workspace, item_id)

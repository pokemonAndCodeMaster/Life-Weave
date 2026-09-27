#!/usr/bin/env python3
"""LifeWeave's supported local Agent client. No session memory or direct DB access.

Start with discover, then continue/recommend. capture only records an idea;
create/discuss/feedback save work without starting AI. run explicitly delegates
work with recommended inputs. An unavailable connection is an error, not a sync.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lifeweave_hook import bind_session


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8010', help='local LifeWeave URL')
    parser.add_argument('--workspace', choices=['personal', 'team'], default='personal')
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('discover', help='find work by topic; empty query lists existing work')
    p.add_argument('query', nargs='?', default='')
    for name, help_text in [('continue', 'read accepted background, proposals, feedback and outcomes'),
                            ('work-view', 'read this item\'s actual steps and current outcomes; no execution'),
                            ('development-choices', 'read development options without starting execution'),
                            ('recommend', 'find versioned materials and methods for this work')]:
        p = commands.add_parser(name, help=help_text); p.add_argument('item_id')
        if name == 'recommend': p.add_argument('--query', default='')
    p = commands.add_parser('work-plan', help='save capability-defined steps from JSON; never starts execution')
    p.add_argument('item_id')
    p.add_argument('--file', required=True, help='JSON plan with version, title, provider and nodes; use work-view to read itemVersion first')
    p = commands.add_parser('capture', help='record original idea only; never starts AI')
    p.add_argument('body')
    p = commands.add_parser('read-idea', help='read an idea and its discussions')
    p.add_argument('idea_id')
    p = commands.add_parser('read-knowledge', help='read the full current Markdown with source and version')
    p.add_argument('ref', help='sourceId:path as returned by recommend')
    p = commands.add_parser('knowledge', help='search current Markdown knowledge without creating work')
    p.add_argument('query', nargs='?', default='')
    p.add_argument('--source', default=None, help='limit to a source ID, e.g. lifeweave-project')
    p = commands.add_parser('read-method', help='read the full method, support files and version; does not execute it')
    p.add_argument('method_id')
    p = commands.add_parser('runs', help='read all current runs in this workspace, optionally for one item')
    p.add_argument('--item-id')
    p = commands.add_parser('create', help='create work and its initial intent; no execution')
    p.add_argument('title'); p.add_argument('--goal', required=True)
    p.add_argument('--type', choices=['requirement', 'research', 'fix', 'learning', 'review', 'personal', 'hobby', 'game', 'other'], default='other')
    p.add_argument('--request-id', help='reuse this ID when retrying the exact same creation')
    p.add_argument('--distinct-goal', action='store_true', help='confirm a same-title goal is independent')
    p = commands.add_parser('work-bind', help='resolve or create one item for a conversation or execution without starting work')
    p.add_argument('--decision', choices=['auto', 'continue', 'child', 'new'], default='auto')
    p.add_argument('--item-id'); p.add_argument('--parent-id'); p.add_argument('--conversation-id'); p.add_argument('--session-id')
    p.add_argument('--title'); p.add_argument('--goal')
    p.add_argument('--type', choices=['requirement', 'research', 'fix', 'learning', 'review', 'personal', 'hobby', 'game', 'other'], default='requirement')
    p.add_argument('--distinct-goal', action='store_true', help='explicitly confirm a same-title target has independent acceptance')
    p.add_argument('--request-id', help='reuse this ID when retrying the same binding')
    for name in ('discuss', 'feedback'):
        p = commands.add_parser(name, help='save discussion' if name == 'discuss' else 'save correction for automatic inclusion in subsequent runs')
        p.add_argument('item_id'); p.add_argument('body')
        if name == 'feedback':
            p.add_argument('--run-id'); p.add_argument('--request-id', default=None, help='reuse this ID only when retrying the same feedback')
    p = commands.add_parser('run', help='explicitly start AI with suggested inputs; inspect recommend before use')
    p.add_argument('item_id'); p.add_argument('instruction')
    p.add_argument('--engine', choices=['codex', 'opencode'], default='codex')
    p.add_argument('--without-materials', action='store_true')
    p = commands.add_parser('external-start', help='bind this already-running Codex session to an existing item and Git worktree')
    p.add_argument('item_id'); p.add_argument('--repo', required=True); p.add_argument('--summary', required=True)
    p.add_argument('--method'); p.add_argument('--knowledge', action='append', default=[])
    p.add_argument('--request-id', default=None)
    p.add_argument('--step-id', help='target step from current work-view')
    p.add_argument('--plan-version', type=int, help='current plan.version')
    p = commands.add_parser('external-report', help='report an actual phase; this does not claim automatic tool capture')
    p.add_argument('item_id'); p.add_argument('session_id')
    p.add_argument('phase', choices=['context','design','implementation','verification','knowledge','finished','blocked'])
    p.add_argument('summary'); p.add_argument('--check', action='append', default=[])
    p.add_argument('--knowledge', action='append', default=[]); p.add_argument('--request-id', default=None)
    p.add_argument('--step-id', help='planned step ID from work-view')
    p.add_argument('--plan-version', type=int, help='plan.version from work-view')
    p.add_argument('--outcome', choices=['running', 'succeeded', 'failed', 'blocked', 'cancelled'])
    p.add_argument('--deliverable', action='append', default=[], metavar='EXPECTATION_ID=OUTPUT_ID',
                   help='bind a fixed result to one expected output; repeat for multiple outputs')
    p = commands.add_parser('external-bind', help='bind an existing external record to this Codex native session for supported hooks')
    p.add_argument('item_id'); p.add_argument('session_id'); p.add_argument('--repo', required=True)
    p.add_argument('--request-id', default=None)
    p = commands.add_parser('external-list', help='read explicitly reported development activity for an item')
    p.add_argument('item_id')
    p = commands.add_parser('external-delivery', help='capture selected changed files as a fixed external code delivery')
    p.add_argument('item_id'); p.add_argument('session_id')
    p.add_argument('--title', required=True); p.add_argument('--summary', required=True)
    p.add_argument('--path', action='append', required=True, help='changed path owned by this session; repeat for each')
    p.add_argument('--acknowledge-preexisting-changes', action='store_true',
                   help='explicitly include selected paths already dirty when the session started')
    p.add_argument('--request-id', help='reuse this ID when retrying the exact same delivery')
    p = commands.add_parser('manual-result', help='register a fixed, readable non-code result for one item')
    p.add_argument('item_id'); p.add_argument('--title', required=True)
    p.add_argument('--content-file', required=True, help='UTF-8 file containing the actual result')
    p.add_argument('--verification', required=True, help='actual check or review evidence')
    p.add_argument('--environment', required=True, help='where the result was checked')
    p.add_argument('--kind', choices=['plan', 'document', 'validation', 'finding', 'decision', 'operation', 'attachment'],
                   default='document')
    args = parser.parse_args(argv)
    url = urlsplit(args.url)
    if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment:
        parser.error('只支持本机 HTTP 服务；远程共享需要正式身份与连接配置。')
    base = args.url.rstrip('/') + '/api/lifeweave/' + args.workspace

    def call(path, data=None, method=None):
        request = Request(base + path, data=json.dumps(data, ensure_ascii=False).encode() if data is not None else None,
                          headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, method=method)
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        item = quote(getattr(args, 'item_id', '') or '', safe='')
        if args.command == 'discover':
            result = call('/work-discovery?' + urlencode({'query': args.query}))
        elif args.command == 'continue':
            result = call(f'/items/{item}/continuation')
        elif args.command == 'work-view':
            result = call(f'/items/{item}/work-view')
        elif args.command == 'work-plan':
            try:
                plan = json.loads(Path(args.file).read_text(encoding='utf-8'))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                parser.error(f'无法读取计划 JSON：{exc}')
            if not isinstance(plan, dict) or not isinstance(plan.get('version'), int) or isinstance(plan.get('version'), bool):
                parser.error('计划须包含整数 version（work-view 返回的 itemVersion），过期版本不会自动覆盖。')
            result = call(f'/items/{item}/work-plan', plan, method='PUT')
        elif args.command == 'development-choices':
            result = call(f'/items/{item}/development/choices')
        elif args.command == 'recommend':
            result = call(f'/items/{item}/input-recommendations?' + urlencode({'query': args.query}))
        elif args.command == 'capture':
            if not args.body.strip(): parser.error('原话不能为空')
            result = call('/entities', {'entityType': 'idea', 'title': args.body.splitlines()[0][:120],
                          'payload': {'body': args.body, 'state': '待整理', 'scope': '个人' if args.workspace == 'personal' else '团队', 'origin': 'LifeWeave Agent 入口'}})
        elif args.command == 'read-idea':
            result = call('/entities/' + quote(args.idea_id, safe=''))
        elif args.command == 'read-knowledge':
            source, separator, path = args.ref.partition(':')
            if not separator or not source or not path: parser.error('知识引用须为 sourceId:path')
            result = call('/library/document?' + urlencode({'sourceId': source, 'path': path}))
        elif args.command == 'knowledge':
            params = {'q': args.query}
            if args.source: params['sourceId'] = args.source
            result = call('/library/documents?' + urlencode(params))
        elif args.command == 'read-method':
            result = call('/methods/' + quote(args.method_id, safe=''))
        elif args.command == 'runs':
            rows = []
            while True:
                params = {'limit': 100, 'offset': len(rows)}
                if args.item_id: params['itemId'] = args.item_id
                page = call('/runs?' + urlencode(params))
                rows.extend(page['items'])
                if len(rows) >= page['total']: break
                if not page['items']: raise OSError('读取期间运行列表变化，请重试')
            result = {'items': rows, 'total': len(rows)}
        elif args.command == 'create':
            request_id = args.request_id or str(uuid4())
            print('create requestId: ' + request_id, file=sys.stderr)
            binding = call('/work-bindings/resolve', {
                'requestId': request_id, 'decision': 'new', 'itemType': args.type,
                'title': args.title, 'goal': args.goal, 'distinctGoal': args.distinct_goal})
            result = (call('/items/' + quote(binding['itemId'], safe=''))
                      if binding.get('itemId') else binding)
        elif args.command == 'work-bind':
            request_id = args.request_id or str(uuid4())
            print('work-bind requestId: ' + request_id, file=sys.stderr)
            result = call('/work-bindings/resolve', {
                'requestId': request_id, 'decision': args.decision, 'itemId': args.item_id,
                'parentId': args.parent_id, 'conversationId': args.conversation_id,
                'sessionId': args.session_id, 'title': args.title, 'goal': args.goal,
                'itemType': args.type, 'distinctGoal': args.distinct_goal})
        elif args.command == 'discuss':
            result = call(f'/items/{item}/discussions', {'body': args.body})
        elif args.command == 'feedback':
            request_id = args.request_id or str(uuid4())
            # Print retry identity before sending, including on a network timeout.
            print('feedback requestId: ' + request_id, file=sys.stderr)
            result = call(f'/items/{item}/feedback', {'body': args.body, 'runId': args.run_id, 'requestId': request_id})
        elif args.command == 'external-start':
            request_id = args.request_id or str(uuid4())
            print('external-start requestId: ' + request_id, file=sys.stderr)
            if (args.step_id is None) != (args.plan_version is None):
                parser.error('外部开发启动须同时指定 --step-id 和 --plan-version')
            native_id = os.environ.get('CODEX_SESSION_ID') or os.environ.get('CODEX_THREAD_ID')
            result = call(f'/items/{item}/external-development/sessions', {
                'requestId': request_id, 'repositoryPath': args.repo, 'summary': args.summary,
                'methodId': args.method, 'knowledgeRefs': args.knowledge,
                'nativeSessionId': native_id, 'stepId': args.step_id,
                'planVersion': args.plan_version})
            if native_id:
                if result['event'].get('payload', {}).get('nativeSessionId') != native_id:
                    session = quote(result['sessionId'], safe='')
                    call(f'/items/{item}/external-development/sessions/{session}/binding', {
                        'requestId': 'native-bind-' + native_id,
                        'nativeSessionId': native_id, 'repositoryPath': args.repo})
                bind_session(native_id, base_url=args.url, workspace=args.workspace,
                             item_id=args.item_id, external_id=result['sessionId'], repository=args.repo)
        elif args.command == 'external-report':
            request_id = args.request_id or str(uuid4())
            print('external-report requestId: ' + request_id, file=sys.stderr)
            session = quote(args.session_id, safe='')
            deliverables = []
            for raw in args.deliverable:
                expectation_id, separator, output_id = raw.partition('=')
                if not separator or not expectation_id or not output_id:
                    parser.error('--deliverable 须为 EXPECTATION_ID=OUTPUT_ID')
                deliverables.append({'expectationId': expectation_id, 'outputId': output_id})
            if any(value is not None for value in (args.step_id, args.plan_version, args.outcome)) or deliverables:
                if not all(value is not None for value in (args.step_id, args.plan_version, args.outcome)):
                    parser.error('步骤报告须同时指定 --step-id、--plan-version 和 --outcome')
            result = call(f'/items/{item}/external-development/sessions/{session}/events', {
                'requestId': request_id, 'phase': args.phase, 'summary': args.summary,
                'checks': args.check, 'knowledgeRefs': args.knowledge,
                'stepId': args.step_id, 'planVersion': args.plan_version,
                'outcome': args.outcome, 'deliverables': deliverables})
        elif args.command == 'external-list':
            result = call(f'/items/{item}/external-development/sessions')
        elif args.command == 'external-delivery':
            request_id = args.request_id or str(uuid4())
            print('external-delivery requestId: ' + request_id, file=sys.stderr)
            session = quote(args.session_id, safe='')
            result = call(f'/items/{item}/external-development/sessions/{session}/delivery', {
                'requestId': request_id, 'title': args.title, 'summary': args.summary,
                'paths': args.path, 'acknowledgePreexistingChanges': args.acknowledge_preexisting_changes})
        elif args.command == 'manual-result':
            try:
                content = Path(args.content_file).read_text(encoding='utf-8')
            except (OSError, UnicodeError) as exc:
                parser.error(f'无法读取成果文件：{exc}')
            if not content.strip():
                parser.error('成果正文不能为空')
            result = call(f'/items/{item}/manual-results', {
                'title': args.title, 'content': content, 'verification': args.verification,
                'environment': args.environment, 'resultKind': args.kind})
        elif args.command == 'external-bind':
            native_id = os.environ.get('CODEX_SESSION_ID') or os.environ.get('CODEX_THREAD_ID')
            if not native_id: parser.error('只在运行中的 Codex 会话内绑定原生 Hook')
            request_id = args.request_id or str(uuid4())
            print('external-bind requestId: ' + request_id, file=sys.stderr)
            session = quote(args.session_id, safe='')
            result = call(f'/items/{item}/external-development/sessions/{session}/binding', {
                'requestId': request_id, 'nativeSessionId': native_id,
                'repositoryPath': args.repo})
            bind_session(native_id, base_url=args.url, workspace=args.workspace,
                         item_id=args.item_id, external_id=args.session_id, repository=args.repo)
        else:
            inputs = {} if args.without_materials else call(f'/items/{item}/input-recommendations?' + urlencode({'query': args.instruction}))['suggested']
            result = call('/runs', {'itemId': args.item_id, 'instruction': args.instruction, 'engine': args.engine, **inputs})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        print(f'LifeWeave HTTP {exc.code}: {exc.read().decode()}', file=sys.stderr)
    except (URLError, TimeoutError, OSError) as exc:
        print(f'LifeWeave 连接失败，未确认保存：{exc}。重新连接后先读记录，不自动重复创建。', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

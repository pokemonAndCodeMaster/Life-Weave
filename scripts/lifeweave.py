#!/usr/bin/env python3
"""LifeWeave's supported local Agent client. No session memory or direct DB access.

Start with discover, then continue/recommend. capture only records an idea;
create/discuss/feedback save work without starting AI. run explicitly delegates
work with recommended inputs. An unavailable connection is an error, not a sync.
"""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8010', help='local LifeWeave URL')
    parser.add_argument('--workspace', choices=['personal', 'team'], default='personal')
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('discover', help='find work by topic; empty query lists existing work')
    p.add_argument('query', nargs='?', default='')
    for name, help_text in [('continue', 'read accepted background, proposals, feedback and outcomes'),
                            ('recommend', 'find versioned materials and methods for this work')]:
        p = commands.add_parser(name, help=help_text); p.add_argument('item_id')
        if name == 'recommend': p.add_argument('--query', default='')
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
    p = commands.add_parser('external-report', help='report an actual phase; this does not claim automatic tool capture')
    p.add_argument('item_id'); p.add_argument('session_id')
    p.add_argument('phase', choices=['context','design','implementation','verification','knowledge','finished','blocked'])
    p.add_argument('summary'); p.add_argument('--check', action='append', default=[])
    p.add_argument('--knowledge', action='append', default=[]); p.add_argument('--request-id', default=None)
    p = commands.add_parser('external-list', help='read explicitly reported development activity for an item')
    p.add_argument('item_id')
    args = parser.parse_args(argv)
    url = urlsplit(args.url)
    if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment:
        parser.error('只支持本机 HTTP 服务；远程共享需要正式身份与连接配置。')
    base = args.url.rstrip('/') + '/api/lifeweave/' + args.workspace

    def call(path, data=None):
        request = Request(base + path, data=json.dumps(data, ensure_ascii=False).encode() if data is not None else None,
                          headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        item = quote(getattr(args, 'item_id', '') or '', safe='')
        if args.command == 'discover':
            result = call('/work-discovery?' + urlencode({'query': args.query}))
        elif args.command == 'continue':
            result = call(f'/items/{item}/continuation')
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
            result = call('/items', {'itemType': args.type, 'title': args.title,
                          'initialContext': {'goal': args.goal}, 'payload': {'goal': args.goal}})
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
            result = call(f'/items/{item}/external-development/sessions', {
                'requestId': request_id, 'repositoryPath': args.repo, 'summary': args.summary,
                'methodId': args.method, 'knowledgeRefs': args.knowledge})
        elif args.command == 'external-report':
            request_id = args.request_id or str(uuid4())
            print('external-report requestId: ' + request_id, file=sys.stderr)
            session = quote(args.session_id, safe='')
            result = call(f'/items/{item}/external-development/sessions/{session}/events', {
                'requestId': request_id, 'phase': args.phase, 'summary': args.summary,
                'checks': args.check, 'knowledgeRefs': args.knowledge})
        elif args.command == 'external-list':
            result = call(f'/items/{item}/external-development/sessions')
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

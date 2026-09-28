#!/usr/bin/env python3
"""Preview, apply, or undo item organization through the public local API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8010')
    parser.add_argument('--workspace', choices=['personal', 'team'], default='personal')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('catalog')
    for name in ('proposal', 'apply', 'undo'):
        command = sub.add_parser(name)
        command.add_argument('proposal_id')
        if name != 'proposal': command.add_argument('--request-id', default=None)
    for name in ('propose', 'rules'):
        command = sub.add_parser(name)
        command.add_argument('--file', type=Path, required=True, help='UTF-8 JSON request file')
    args = parser.parse_args(argv)
    url = urlsplit(args.url)
    if (url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment):
        parser.error('只支持本机 HTTP 服务')
    base = args.url.rstrip('/') + '/api/lifeweave/' + args.workspace + '/item-organization'
    body = None
    method = 'GET'
    if args.command == 'catalog': path = '/catalog'
    elif args.command == 'proposal': path = '/proposals/' + quote(args.proposal_id, safe='')
    elif args.command in {'apply', 'undo'}:
        path = '/proposals/' + quote(args.proposal_id, safe='') + '/' + args.command
        body, method = {'requestId': args.request_id or uuid4().hex}, 'POST'
    else:
        try:
            body = json.loads(args.file.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            parser.error(f'无法读取 JSON：{exc}')
        if not isinstance(body, dict): parser.error('请求文件必须是 JSON 对象')
        path = '/proposals' if args.command == 'propose' else '/rules'
        method = 'POST' if args.command == 'propose' else 'PUT'
        if args.command == 'propose': body.setdefault('requestId', uuid4().hex)
    request = Request(base + path,
                      data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                      headers={'Accept': 'application/json', 'Content-Type': 'application/json'}, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            print(json.dumps(json.load(response), ensure_ascii=False, indent=2, default=str))
        return 0
    except HTTPError as exc:
        print(f'HTTP {exc.code}: {exc.read().decode("utf-8", errors="replace")}')
    except URLError as exc:
        print(f'本机 LifeWeave 不可用：{exc.reason}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

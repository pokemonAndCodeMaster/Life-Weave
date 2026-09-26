#!/usr/bin/env python3
"""Forward minimal Codex lifecycle metadata for explicitly bound local sessions.

This script never sends prompts, commands, tool arguments, or tool output.
Unbound sessions exit immediately. Codex hook trust is handled by Codex itself.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '.runtime' / 'codex-hooks'
FILE = FOLDER / 'bindings.json'


def bind_session(native_id: str, *, base_url: str, workspace: str,
                 item_id: str, external_id: str, repository: str) -> None:
    parsed = urlsplit(base_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('Hook 只向本机 LifeWeave 服务上报')
    FOLDER.mkdir(parents=True, exist_ok=True)
    FOLDER.chmod(0o700)
    with (FOLDER / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = json.loads(FILE.read_text()) if FILE.exists() else {}
        root = _repository(repository)
        if not root:
            raise ValueError('Hook 绑定仓库必须是可读取的 Git 仓库')
        rows[native_id] = {'baseUrl': base_url.rstrip('/'), 'workspace': workspace,
                           'itemId': item_id, 'externalId': external_id,
                           'repository': root}
        temporary = FOLDER / f'bindings.{os.getpid()}.tmp'
        temporary.write_text(json.dumps(rows, ensure_ascii=False))
        temporary.chmod(0o600)
        temporary.replace(FILE)


def _repository(cwd: str) -> str | None:
    try:
        result = subprocess.run(['git', '-C', cwd, 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True, timeout=2, check=False)
        return str(Path(result.stdout.strip()).resolve()) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def event_payload(event: dict) -> dict | None:
    kind = event.get('hook_event_name')
    native_id = event.get('session_id')
    turn_id = event.get('turn_id')
    if kind not in {'PostToolUse', 'Stop', 'Interrupt'} or not native_id or not turn_id:
        return None
    tool_id = event.get('tool_use_id') if kind == 'PostToolUse' else None
    tool_name = event.get('tool_name') if kind == 'PostToolUse' else None
    if kind == 'PostToolUse' and (not tool_id or not tool_name):
        return None
    response = event.get('tool_response')
    exit_code = response.get('exit_code') if isinstance(response, dict) else None
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        exit_code = None
    arguments = event.get('tool_input')
    input_hash = ('sha256:' + hashlib.sha256(json.dumps(arguments, ensure_ascii=False,
                  sort_keys=True, default=str).encode()).hexdigest()) if kind == 'PostToolUse' else None
    return {'eventId': f'{kind}:{turn_id}:{tool_id or "turn"}',
            'nativeSessionId': native_id, 'kind': kind, 'turnId': turn_id,
            'toolUseId': tool_id, 'toolName': tool_name,
            'model': str(event.get('model') or '') or None,
            'inputHash': input_hash, 'exitCode': exit_code}


def emit(event: dict) -> bool:
    payload = event_payload(event)
    if payload is None or not FILE.exists():
        return False
    binding = json.loads(FILE.read_text()).get(payload['nativeSessionId'])
    if not binding or _repository(str(event.get('cwd') or '')) != binding['repository']:
        return False
    path = (f"/api/lifeweave/{binding['workspace']}/items/{quote(binding['itemId'], safe='')}"
            f"/external-development/sessions/{quote(binding['externalId'], safe='')}/hook-events")
    request = Request(binding['baseUrl'] + path,
                      data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=2) as response:
            return response.status == 201
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        FOLDER.mkdir(parents=True, exist_ok=True)
        with (FOLDER / 'errors.log').open('a') as log:
            log.write(json.dumps({'eventId': payload['eventId'], 'errorType': type(exc).__name__}) + '\n')
        (FOLDER / 'errors.log').chmod(0o600)
        return False


if __name__ == '__main__':
    try:
        emit(json.load(sys.stdin))
    except (ValueError, OSError, json.JSONDecodeError):
        pass  # Hooks are observational; failures must never alter Codex behavior.

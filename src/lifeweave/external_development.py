"""Explicit reports from a Codex session already running outside LifeWeave.

These records are item activities, not platform-managed Runs or captured tool traces.
"""
from __future__ import annotations

import hashlib
import difflib
import json
import subprocess
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from .models import WorkspaceKey

router = APIRouter(prefix='/api/lifeweave/{workspace}/items/{item_id}/external-development', tags=['external-development'])


class Start(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(min_length=1, max_length=128)
    repositoryPath: str = Field(min_length=1, max_length=4096)
    summary: str = Field(min_length=1, max_length=2000)
    methodId: str | None = None
    knowledgeRefs: list[str] = Field(default_factory=list, max_length=10)
    nativeSessionId: str | None = Field(default=None, min_length=8, max_length=128)


class Report(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(min_length=1, max_length=128)
    phase: Literal['context', 'design', 'implementation', 'verification', 'knowledge', 'finished', 'blocked']
    summary: str = Field(min_length=1, max_length=5000)
    checks: list[str] = Field(default_factory=list, max_length=20)
    knowledgeRefs: list[str] = Field(default_factory=list, max_length=10)


class Bind(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(min_length=1, max_length=128)
    nativeSessionId: str = Field(min_length=8, max_length=128)
    repositoryPath: str = Field(min_length=1, max_length=4096)


class HookEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    eventId: str = Field(min_length=1, max_length=128)
    nativeSessionId: str = Field(min_length=8, max_length=128)
    kind: Literal['PostToolUse', 'Stop', 'Interrupt']
    turnId: str | None = Field(default=None, max_length=128)
    toolUseId: str | None = Field(default=None, max_length=128)
    toolName: str | None = Field(default=None, max_length=256)
    model: str | None = Field(default=None, max_length=256)
    inputHash: str | None = Field(default=None, max_length=128)
    exitCode: int | None = None


def git_state(raw_path: str) -> dict:
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError('开发仓库目录不存在')

    def git(*args: str) -> str:
        result = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True,
                                timeout=10, check=False)
        if result.returncode:
            raise ValueError('所选目录不是可读取的 Git 工作区')
        return result.stdout.strip()

    root = Path(git('rev-parse', '--show-toplevel')).resolve()
    revision = git('rev-parse', 'HEAD')
    changed = git('diff', '--name-only', 'HEAD').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    return {'repositoryPath': str(root), 'revision': revision, 'changedPaths': changed[:100],
            'untrackedPaths': untracked[:100], 'changedCount': len(changed), 'untrackedCount': len(untracked)}


def inputs(request: Request, workspace: str, method_id: str | None, refs: list[str]) -> list[dict]:
    if not method_id and not refs:
        return []
    rows = request.app.state.task_sources.snapshot(workspace, method_id, refs)
    return [{key: row.get(key) for key in ('id', 'title', 'target', 'version', 'sourcePath')} for row in rows]


def receipt_id(workspace: str, item_id: str, request_id: str) -> str:
    return 'activity-' + hashlib.sha256(f'{workspace}:{item_id}:{request_id}'.encode()).hexdigest()[:32]


def save(request: Request, workspace: str, item_id: str, request_id: str, kind: str,
         body: str, payload: dict, fingerprint: str) -> dict:
    db = request.app.state.database_manager.postgres()
    identity = receipt_id(workspace, item_id, request_id)
    with db.transaction() as conn:
        existing = conn.execute('SELECT * FROM workbench.t_lifeweave_activity WHERE id=%s', (identity,)).fetchone()
        if existing:
            if existing['workspace_key'] != workspace or existing['item_id'] != item_id or existing['payload'].get('requestFingerprint') != fingerprint:
                raise ValueError('此请求身份已经用于不同内容')
            return dict(existing)
        item = conn.execute('SELECT id FROM workbench.t_lifeweave_item WHERE id=%s AND workspace_key=%s',
                            (item_id, workspace)).fetchone()
        if not item:
            raise KeyError(item_id)
        return dict(conn.execute('INSERT INTO workbench.t_lifeweave_activity '
                                 '(id,workspace_key,item_id,kind,body,payload,actor_id) '
                                 'VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                                 (identity, workspace, item_id, kind, body,
                                  Jsonb({**payload, 'requestFingerprint': fingerprint}), 'local-user')).fetchone())


def normalized(row: dict) -> dict:
    return {'id': row['id'], 'itemId': row['item_id'], 'kind': row['kind'], 'body': row['body'],
            'payload': row['payload'], 'createdAt': row['created_at']}


def fail(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, '事项或外部开发会话不存在')
    return HTTPException(409, str(exc))


def session_start(request: Request, workspace: str, item_id: str, session_id: str) -> tuple[list[dict], dict]:
    rows = request.app.state.lifeweave_service.repository.list_activities(workspace, item_id)
    start_row = next((row for row in rows if row['kind'] == 'external_development_start'
                      and row['payload'].get('sessionId') == session_id), None)
    if not start_row:
        raise KeyError(session_id)
    return rows, start_row


def start_record(request: Request, workspace: str, item_id: str, session_id: str) -> dict:
    if not session_id.startswith('external-'):
        raise KeyError(session_id)
    identity = 'activity-' + session_id.removeprefix('external-')
    row = request.app.state.database_manager.postgres().fetch_one(
        'SELECT * FROM workbench.t_lifeweave_activity '
        "WHERE id=%s AND workspace_key=%s AND item_id=%s AND kind='external_development_start'",
        (identity, workspace, item_id))
    if not row or row['payload'].get('sessionId') != session_id:
        raise KeyError(session_id)
    return dict(row)


def current_git_diff(start_state: dict) -> dict:
    root = Path(start_state['repositoryPath']).resolve()
    base = start_state['revision']
    current = git_state(str(root))
    tracked = subprocess.run(['git', '-C', str(root), 'diff', '--name-only', '-z', base],
                             capture_output=True, timeout=20, check=False)
    untracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '-z'],
                               capture_output=True, timeout=20, check=False)
    if tracked.returncode or untracked.returncode:
        raise ValueError('无法从原始提交读取当前 Git 差异')
    new_paths = [part.decode('utf-8', 'replace') for part in untracked.stdout.split(b'\0') if part]
    paths = list(dict.fromkeys([part.decode('utf-8', 'replace') for part in tracked.stdout.split(b'\0') if part] + new_paths))
    output = subprocess.run(['git', '-C', str(root), 'diff', '--no-ext-diff', base, '--'],
                            capture_output=True, timeout=20, check=False)
    if output.returncode:
        raise ValueError('Git 差异读取失败')
    patch = output.stdout.decode('utf-8', 'replace')
    for relative in new_paths[:100]:
        candidate = root / relative
        file = candidate.resolve()
        if candidate.is_symlink() or not file.is_relative_to(root) or not file.is_file() or file.stat().st_size > 100_000:
            continue
        try:
            content = file.read_text()
        except UnicodeError:
            continue
        patch += ''.join(difflib.unified_diff([], content.splitlines(keepends=True),
                         fromfile='/dev/null', tofile='b/' + relative))
    return {'baseRevision': base, 'currentRevision': current['revision'], 'files': paths[:100],
            'fileCount': len(paths), 'patch': patch[:200_000],
            'truncated': len(paths) > 100 or len(patch) > 200_000,
            'scope': '当前仓库相对起始提交的全部差异，可能包含其他会话修改'}


@router.post('/sessions', status_code=201)
def start(request: Request, workspace: WorkspaceKey, item_id: str, body: Start):
    try:
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
        identity = receipt_id(workspace, item_id, body.requestId)
        existing = next((row for row in request.app.state.lifeweave_service.repository.list_activities(workspace, item_id)
                         if row['id'] == identity), None)
        if existing:
            legacy = hashlib.sha256(json.dumps(body.model_dump(exclude={'nativeSessionId'}), sort_keys=True).encode()).hexdigest()
            if existing['payload'].get('requestFingerprint') not in {fingerprint, legacy} or existing['kind'] != 'external_development_start':
                raise ValueError('此请求身份已经用于不同内容')
            return {'sessionId': existing['payload']['sessionId'], 'event': existing}
        state = git_state(body.repositoryPath)
        choices = request.app.state.development.choices(workspace, item_id)
        method_id = body.methodId or choices['methodId']
        if not method_id:
            raise ValueError('开发方法未接入，无法登记可复用的开发 Agent 输入')
        refs = body.knowledgeRefs or (choices['knowledgeRefs'] if
                                     state['repositoryPath'] == choices['recommendedRepositoryPath'] else [])
        selected = inputs(request, workspace, method_id, refs)
        session_id = 'external-' + identity.removeprefix('activity-')
        row = save(request, workspace, item_id, body.requestId, 'external_development_start', body.summary,
                   {'sessionId': session_id, 'phase': 'started', 'observedGit': state,
                    'agentId': 'development', 'methodId': method_id,
                    'declaredInputs': selected, 'nativeSessionId': body.nativeSessionId,
                    'observation': '外部会话主动登记；Hook 只记录受支持且已绑定的后续事件'}, fingerprint)
        return {'sessionId': session_id, 'event': normalized(row)}
    except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        raise fail(exc) from exc


@router.post('/sessions/{session_id}/events', status_code=201)
def report(request: Request, workspace: WorkspaceKey, item_id: str, session_id: str, body: Report):
    try:
        activities, start_row = session_start(request, workspace, item_id, session_id)
        fingerprint = hashlib.sha256(json.dumps([session_id, body.model_dump()], sort_keys=True).encode()).hexdigest()
        identity = receipt_id(workspace, item_id, body.requestId)
        existing = next((row for row in activities if row['id'] == identity), None)
        if existing:
            if existing['payload'].get('requestFingerprint') != fingerprint or existing['payload'].get('sessionId') != session_id:
                raise ValueError('此请求身份已经用于不同内容')
            return existing
        if any(row['kind'] == 'external_development_event' and row['payload'].get('sessionId') == session_id
               and row['payload'].get('phase') == 'finished' for row in activities):
            raise ValueError('外部开发记录已结束')
        state = git_state(start_row['payload']['observedGit']['repositoryPath'])
        selected = inputs(request, workspace, None, body.knowledgeRefs)
        row = save(request, workspace, item_id, body.requestId, 'external_development_event', body.summary,
                   {'sessionId': session_id, 'phase': body.phase, 'observedGit': state,
                    'declaredInputs': selected, 'reportedChecks': body.checks,
                    'observation': '阶段与检查由外部会话上报；Git 状态由服务读取'}, fingerprint)
        return normalized(row)
    except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        raise fail(exc) from exc


@router.post('/sessions/{session_id}/binding', status_code=201)
def bind(request: Request, workspace: WorkspaceKey, item_id: str, session_id: str, body: Bind):
    try:
        activities, start_row = session_start(request, workspace, item_id, session_id)
        existing_native = start_row['payload'].get('nativeSessionId')
        bindings = [row for row in activities if row['kind'] == 'external_development_binding'
                    and row['payload'].get('sessionId') == session_id]
        if (existing_native and existing_native != body.nativeSessionId) or any(
                row['payload'].get('nativeSessionId') != body.nativeSessionId for row in bindings):
            raise ValueError('此开发记录已绑定另一 Codex 原生会话')
        if git_state(body.repositoryPath)['repositoryPath'] != start_row['payload']['observedGit']['repositoryPath']:
            raise ValueError('Codex 会话仓库与原开发记录不一致')
        fingerprint = hashlib.sha256(json.dumps([session_id, body.model_dump()], sort_keys=True).encode()).hexdigest()
        row = save(request, workspace, item_id, body.requestId, 'external_development_binding',
                   '已关联本机 Codex 原生会话，后续支持的 Hook 事件可写入此事项',
                   {'sessionId': session_id, 'phase': 'native_binding',
                    'nativeSessionId': body.nativeSessionId,
                    'observation': '本机 CLI 主动绑定；Hook 是否运行仍需实际事件证明'}, fingerprint)
        return normalized(row)
    except (KeyError, ValueError) as exc:
        raise fail(exc) from exc


@router.post('/sessions/{session_id}/hook-events', status_code=201)
def hook_event(request: Request, workspace: WorkspaceKey, item_id: str, session_id: str, body: HookEvent):
    try:
        start_row = start_record(request, workspace, item_id, session_id)
        bound_at_start = start_row['payload'].get('nativeSessionId') == body.nativeSessionId
        later_binding = request.app.state.database_manager.postgres().fetch_one(
            'SELECT id FROM workbench.t_lifeweave_activity '
            "WHERE workspace_key=%s AND item_id=%s AND kind='external_development_binding' "
            "AND payload->>'sessionId'=%s AND payload->>'nativeSessionId'=%s LIMIT 1",
            (workspace, item_id, session_id, body.nativeSessionId))
        if not (bound_at_start or later_binding):
            raise ValueError('Codex 原生会话未与此事项绑定')
        if body.kind == 'PostToolUse' and (not body.toolUseId or not body.toolName):
            raise ValueError('工具事件缺少工具名称或调用身份')
        identity = 'hook-' + hashlib.sha256(f'{body.nativeSessionId}:{body.eventId}'.encode()).hexdigest()[:32]
        fingerprint = hashlib.sha256(json.dumps([session_id, body.model_dump()], sort_keys=True).encode()).hexdigest()
        row = save(request, workspace, item_id, identity, 'external_development_hook',
                   f"Codex {body.toolName or body.kind} · {'退出码 '+str(body.exitCode) if body.exitCode is not None else '结果未报告'}",
                   {'sessionId': session_id, 'phase': 'tool' if body.kind == 'PostToolUse' else body.kind.lower(),
                    'source': 'codex_hook', 'nativeSessionId': body.nativeSessionId,
                    'turnId': body.turnId, 'toolUseId': body.toolUseId, 'toolName': body.toolName,
                    'model': body.model, 'inputHash': body.inputHash, 'exitCode': body.exitCode,
                    'observedGit': git_state(start_row['payload']['observedGit']['repositoryPath']),
                    'observation': 'Codex Hook 上报元数据；没有保存原始工具输入或输出'}, fingerprint)
        return normalized(row)
    except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        raise fail(exc) from exc


@router.get('/sessions')
def sessions(request: Request, workspace: WorkspaceKey, item_id: str):
    try:
        request.app.state.lifeweave_service.get_item(workspace, item_id)
        rows = request.app.state.lifeweave_service.repository.list_activities(workspace, item_id)
        return {'items': [row for row in rows if row['kind'].startswith('external_development_')]}
    except (KeyError, ValueError) as exc:
        raise fail(exc) from exc


@router.get('/sessions/{session_id}/diff')
def diff(request: Request, workspace: WorkspaceKey, item_id: str, session_id: str):
    try:
        start_row = start_record(request, workspace, item_id, session_id)
        return current_git_diff(start_row['payload']['observedGit'])
    except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        raise fail(exc) from exc

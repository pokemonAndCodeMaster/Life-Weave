"""Explicit reports from a Codex session already running outside LifeWeave.

These records are item activities, not platform-managed Runs or captured tool traces.
"""
from __future__ import annotations

import hashlib
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


class Report(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(min_length=1, max_length=128)
    phase: Literal['context', 'design', 'implementation', 'verification', 'knowledge', 'finished', 'blocked']
    summary: str = Field(min_length=1, max_length=5000)
    checks: list[str] = Field(default_factory=list, max_length=20)
    knowledgeRefs: list[str] = Field(default_factory=list, max_length=10)


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


@router.post('/sessions', status_code=201)
def start(request: Request, workspace: WorkspaceKey, item_id: str, body: Start):
    try:
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
        identity = receipt_id(workspace, item_id, body.requestId)
        existing = next((row for row in request.app.state.lifeweave_service.repository.list_activities(workspace, item_id)
                         if row['id'] == identity), None)
        if existing:
            if existing['payload'].get('requestFingerprint') != fingerprint or existing['kind'] != 'external_development_start':
                raise ValueError('此请求身份已经用于不同内容')
            return {'sessionId': existing['payload']['sessionId'], 'event': existing}
        state = git_state(body.repositoryPath)
        selected = inputs(request, workspace, body.methodId, body.knowledgeRefs)
        session_id = 'external-' + identity.removeprefix('activity-')
        row = save(request, workspace, item_id, body.requestId, 'external_development_start', body.summary,
                   {'sessionId': session_id, 'phase': 'started', 'observedGit': state,
                    'declaredInputs': selected, 'observation': '外部会话主动登记；平台未捕获内部命令'}, fingerprint)
        return {'sessionId': session_id, 'event': normalized(row)}
    except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        raise fail(exc) from exc


@router.post('/sessions/{session_id}/events', status_code=201)
def report(request: Request, workspace: WorkspaceKey, item_id: str, session_id: str, body: Report):
    try:
        activities = request.app.state.lifeweave_service.repository.list_activities(workspace, item_id)
        start_row = next((row for row in activities if row['kind'] == 'external_development_start'
                          and row['payload'].get('sessionId') == session_id), None)
        if not start_row:
            raise KeyError(session_id)
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


@router.get('/sessions')
def sessions(request: Request, workspace: WorkspaceKey, item_id: str):
    try:
        request.app.state.lifeweave_service.get_item(workspace, item_id)
        rows = request.app.state.lifeweave_service.repository.list_activities(workspace, item_id)
        return {'items': [row for row in rows if row['kind'].startswith('external_development_')]}
    except (KeyError, ValueError) as exc:
        raise fail(exc) from exc

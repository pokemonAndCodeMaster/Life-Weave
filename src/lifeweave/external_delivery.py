"""Capture explicitly scoped changes made by an already-bound local Agent."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from .development_delivery import (_git, _names, _tree_entries, _index_entries, _file_snapshot,
                                   _zip_bytes, snapshot_blobs, change_metadata, referenced_resources)
from .external_development import start_record
from .models import WorkspaceKey
from .output_files import safe_path

router = APIRouter(prefix='/api/lifeweave/{workspace}/items/{item_id}/external-development',
                   tags=['external-delivery'])


class ExternalDeliveryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=20000)
    paths: list[str] = Field(min_length=1)
    acknowledgePreexistingChanges: bool = False


def freeze_scoped(directory: Path, baseline: dict, paths: list[str], summary: str,
                  acknowledge_preexisting: bool = False) -> tuple[dict, bytes]:
    directory = directory.resolve()
    if Path(_git(directory, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != directory:
        raise ValueError('外部会话仓库身份已变化')
    paths = sorted(set(safe_path(path) for path in paths))
    for path in paths:
        if any(part.startswith('.') or part in {'node_modules', '__pycache__'} for part in Path(path).parts):
            raise ValueError('不归档运行目录、凭证或隐藏文件：' + path)
    changed = baseline.get('allChangedPaths', baseline.get('changedPaths', []))
    untracked = baseline.get('allUntrackedPaths', baseline.get('untrackedPaths', []))
    if baseline.get('changedCount', 0) > len(changed) or baseline.get('untrackedCount', 0) > len(untracked):
        raise ValueError('旧外部会话的初始变更清单不完整，无法确认交付归属；请建立新会话')
    preexisting = set(paths) & set(changed + untracked)
    if preexisting and not acknowledge_preexisting:
        raise ValueError('所选文件包含会话开始前的改动，需明确确认其归属：' + ', '.join(sorted(preexisting)))
    base = baseline['revision']
    _git(directory, 'cat-file', '-e', f'{base}^{{commit}}')
    before = _file_snapshot(directory, paths)
    with tempfile.TemporaryDirectory(prefix='lifeweave-external-delivery-') as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temporary) / 'index'), 'GIT_LITERAL_PATHSPECS': '1'}
        _git(directory, 'read-tree', base, env=env)
        _git(directory, 'add', '-A', '--', *paths, env=env)
        _git(directory, 'diff', '--cached', '--check', base, env=env)
        patch = _git(directory, 'diff', '--cached', '--binary', '--full-index', '--no-ext-diff', base, env=env)
        if not patch:
            raise ValueError('所选范围没有相对会话基线的变更')
        names = _names(_git(directory, 'diff', '--cached', '--name-only', '--no-renames', '-z', base, env=env))
        old = _tree_entries(_git(directory, 'ls-tree', '-r', '-z', base, '--', *names))
        new = _index_entries(_git(directory, 'ls-files', '--stage', '-z', '--', *names, env=env))
        files = [{'path': path, 'status': 'added' if path not in old else 'deleted' if path not in new else 'modified',
                  'before': old.get(path), 'after': new.get(path)} for path in names]
        change_metadata(directory, base, env, files)
        blobs = snapshot_blobs(directory, files)
        resources = referenced_resources(directory, files, blobs, env)
        tree = _git(directory, 'write-tree', env=env)
        verify = {**env, 'GIT_INDEX_FILE': str(Path(temporary) / 'verify-index')}
        _git(directory, 'read-tree', base, env=verify)
        result = subprocess.run(['git', '-C', str(directory), 'apply', '--cached', '--binary', '-'],
                                input=patch, capture_output=True, timeout=60, env=verify)
        if result.returncode or _git(directory, 'write-tree', env=verify) != tree:
            raise ValueError('所选变更补丁回放与捕获文件不一致')
    if before != _file_snapshot(directory, paths):
        raise ValueError('捕获过程中所选文件发生变化，请重试')
    manifest = {'schemaVersion': 2, 'origin': 'external-development', 'baseRevision': base,
                'files': files, 'resources': resources, 'selectedPaths': paths,
                'acknowledgedPreexistingPaths': sorted(preexisting),
                'patchSha256': hashlib.sha256(patch).hexdigest(),
                'implementationResultSha256': hashlib.sha256(summary.encode()).hexdigest(),
                'serviceChecks': ['git-diff-check', 'base-patch-replay-tree-match', 'stable-selected-files'],
                'verificationBoundary': '仅固定明确选择的文件；执行和测试结论由对应步骤证据说明。'}
    return manifest, _zip_bytes(manifest, patch, summary, blobs)


@router.post('/sessions/{session_id}/delivery', status_code=201)
def capture(request: Request, workspace: WorkspaceKey, item_id: str, session_id: str,
            body: ExternalDeliveryInput):
    try:
        start = start_record(request, workspace, item_id, session_id)
        db = request.app.state.database_manager.postgres()
        fingerprint = hashlib.sha256(json.dumps([session_id, body.model_dump()], sort_keys=True).encode()).hexdigest()
        suffix = hashlib.sha256(f'{workspace}:{item_id}:{body.requestId}'.encode()).hexdigest()[:32]
        identity = 'output-' + suffix
        with db.transaction() as conn:
            # Serialize same-item captures so a retry cannot publish two bundles.
            conn.execute('SELECT id FROM workbench.t_lifeweave_item WHERE workspace_key=%s AND id=%s FOR UPDATE',
                         (workspace, item_id)).fetchone()
            existing = conn.execute('SELECT payload FROM workbench.t_lifeweave_entity WHERE id=%s AND workspace_key=%s',
                                    (identity, workspace)).fetchone()
            if existing:
                if existing['payload'].get('requestFingerprint') != fingerprint:
                    raise ValueError('此请求身份已用于不同的交付')
                fixed = existing['payload']['fixedDelivery']
                return {'artifactId': identity, 'outputId': 'artifact:' + identity, 'version': fixed['sha256']}
            baseline = start['payload']['observedGit']
            manifest, data = freeze_scoped(Path(baseline['repositoryPath']), baseline, body.paths,
                                          body.summary, body.acknowledgePreexistingChanges)
            digest = hashlib.sha256(data).hexdigest()
            destination = request.app.state.output_files.root / '.runtime' / 'output-deliveries' / (digest + '.zip')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise ValueError('已有交付缓存校验失败')
            else:
                with destination.open('xb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            payload = {'kind': '代码交付', 'resultKind': 'code', 'body': body.summary,
                       'artifactVersion': digest, 'requestFingerprint': fingerprint,
                       'fixedDelivery': {'sha256': digest, 'manifest': manifest, 'sessionId': session_id,
                                         'repositoryPath': baseline['repositoryPath']}}
            conn.execute("INSERT INTO workbench.t_lifeweave_entity "
                         "(id,workspace_key,entity_type,title,payload,created_by,updated_by) "
                         "VALUES(%s,%s,'artifact',%s,%s,'local-user','local-user')",
                         (identity, workspace, body.title, Jsonb(payload)))
            conn.execute("INSERT INTO workbench.t_lifeweave_relation "
                         "(id,workspace_key,from_kind,from_id,to_kind,to_id,relation_type,created_by) "
                         "VALUES(%s,%s,'item',%s,'entity',%s,'produces','local-user')",
                         ('relation-' + suffix, workspace, item_id, identity))
        return {'artifactId': identity, 'outputId': 'artifact:' + identity, 'version': digest}
    except KeyError as exc:
        raise HTTPException(404, '外部开发会话不存在或不属于当前事项') from exc
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(409, str(exc)) from exc

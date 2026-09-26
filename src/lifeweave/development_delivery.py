"""Freeze an implementation worktree into a reproducible, immutable ZIP.

The temporary Git index captures tracked, untracked and binary changes without
modifying the agent's worktree index. Generated execution inputs are excluded
explicitly and listed in the manifest.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


def _git(directory: Path, *args: str, env: dict[str, str] | None = None) -> bytes:
    result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True,
                            timeout=60, check=False, env=env)
    if result.returncode:
        raise ValueError("交付文件的 Git 状态无法核对：" + result.stderr.decode("utf-8", "replace")[:400])
    return result.stdout


def _names(raw: bytes) -> list[str]:
    return [part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part]


def _tree_entries(raw: bytes) -> dict[str, dict[str, str]]:
    entries = {}
    for line in raw.split(b"\0"):
        if not line:
            continue
        details, path = line.split(b"\t", 1)
        mode, kind, oid = details.decode().split()
        entries[path.decode("utf-8", "surrogateescape")] = {"mode": mode, "type": kind, "oid": oid}
    return entries


def _index_entries(raw: bytes) -> dict[str, dict[str, str]]:
    entries = {}
    for line in raw.split(b"\0"):
        if not line:
            continue
        details, path = line.split(b"\t", 1)
        mode, oid, stage = details.decode().split()
        if stage != "0":
            raise ValueError("交付索引存在未解决冲突")
        entries[path.decode("utf-8", "surrogateescape")] = {"mode": mode, "type": "blob", "oid": oid}
    return entries


def _zip_bytes(manifest: dict[str, Any], patch: bytes, result: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode()),
                              ("changes.patch", patch), ("implementation-result.md", result.encode())):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return output.getvalue()


def freeze_delivery(project_root: Path, assignment: dict[str, Any], run: dict[str, Any]) -> tuple[dict[str, Any], str]:
    environment = run.get("environment_snapshot") or {}
    actual = environment.get("actualDirectory")
    if not actual:
        raise ValueError("实施运行缺少实际工作目录，不能生成交付包")
    directory = Path(actual).resolve()
    if not directory.is_relative_to(project_root / ".runtime" / "executions") or not directory.is_dir():
        raise ValueError("实施工作目录不在受管运行区")
    if Path(_git(directory, "rev-parse", "--show-toplevel").decode().strip()).resolve() != directory:
        raise ValueError("实施工作目录的 Git 根目录不匹配")
    base = assignment["repository_revision"]
    _git(directory, "cat-file", "-e", f"{base}^{{commit}}")
    before = _git(directory, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    tracked = _names(_git(directory, "diff", "--name-only", "-z", base))
    untracked = _names(_git(directory, "ls-files", "--others", "--exclude-standard", "-z"))
    generated = set(environment.get("materializedInputFiles") or environment.get("materializedCapabilities") or [])
    if generated:
        generated.add(".lifeweave/capability-manifest.json")
    def artifact(path: str) -> bool:
        parts = Path(path).parts
        return bool(set(parts) & {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}) or path.endswith((".pyc", ".pyo")) or path == ".coverage"
    excluded = sorted(path for path in set(tracked + untracked)
                      if path in generated or (path in untracked and artifact(path)))
    paths = sorted(path for path in set(tracked + untracked) if path not in excluded)
    if not paths:
        raise ValueError("实施运行没有可交付的文件变化")
    with tempfile.TemporaryDirectory(prefix="lifeweave-delivery-index-") as temporary:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index"), "GIT_LITERAL_PATHSPECS": "1"}
        _git(directory, "read-tree", base, env=env)
        _git(directory, "add", "-A", "--", *paths, env=env)
        _git(directory, "diff", "--cached", "--check", base, env=env)
        patch = _git(directory, "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", base, env=env)
        staged_tree = _git(directory, "write-tree", env=env).decode().strip()
        changed = _names(_git(directory, "diff", "--cached", "--name-only", "-z", base, env=env))
        old = _tree_entries(_git(directory, "ls-tree", "-r", "-z", base, "--", *changed))
        new = _index_entries(_git(directory, "ls-files", "--stage", "-z", "--", *changed, env=env))
        files = [{"path": path, "status": "added" if path not in old else "deleted" if path not in new else "modified",
                  "before": old.get(path), "after": new.get(path)} for path in changed]
    with tempfile.TemporaryDirectory(prefix="lifeweave-delivery-replay-") as temporary:
        replay = Path(temporary) / "repo"
        clone = subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(directory), str(replay)],
                               capture_output=True, timeout=120, check=False)
        if clone.returncode:
            raise ValueError("无法建立交付补丁回放目录")
        _git(replay, "checkout", "-q", "--detach", base)
        applied = subprocess.run(["git", "-C", str(replay), "apply", "--binary", "-"],
                                 input=patch, capture_output=True, timeout=60, check=False)
        if applied.returncode:
            raise ValueError("交付补丁无法在原始提交回放")
        _git(replay, "add", "-A")
        if _git(replay, "write-tree").decode().strip() != staged_tree:
            raise ValueError("交付补丁回放与文件清单不一致")
    if before != _git(directory, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise ValueError("打包过程中工作树发生变化，请重新生成")
    result = str(run.get("result") or "")
    manifest = {"schemaVersion": 1, "assignmentId": assignment["id"], "itemId": assignment["item_id"],
                "implementationRunId": run["id"], "baseRevision": base,
                "planSha256": assignment["plan_sha256"], "reviewRunId": assignment["review_run_id"],
                "reviewDecision": assignment["review_decision"], "inputVersions": assignment["input_versions"],
                "files": files, "excludedGenerated": excluded,
                "patchSha256": hashlib.sha256(patch).hexdigest(),
                "implementationResultSha256": hashlib.sha256(result.encode()).hexdigest(),
                "serviceChecks": ["git-diff-check", "base-patch-replay-tree-match", "stable-worktree-snapshot"],
                "verificationBoundary": "实施结果是 Agent 报告；补丁与文件清单由服务从 Git 工作树固定。"}
    content = _zip_bytes(manifest, patch, result)
    digest = hashlib.sha256(content).hexdigest()
    destination = project_root / ".runtime" / "development-deliveries" / f"{assignment['id']}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError("已有交付包与当前工作树不一致，不能覆盖固定版本")
    else:
        temp = destination.with_suffix(".tmp")
        with temp.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, destination)
    return manifest, digest

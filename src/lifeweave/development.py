"""A development assignment binds planning, review and implementation to one item.

The existing Run/Worker owns execution. This module only advances a fixed,
recoverable workflow after reading the real terminal state of each Run.
"""
from __future__ import annotations

import hashlib
import difflib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb


ACTIVE = {"planning", "reviewing", "implementing"}
TERMINAL_RUNS = {"succeeded", "failed", "unavailable", "cancelled", "paused"}
DEFAULT_PROJECT_REFS = [
    "lifeweave-project:docs/product.md",
    "lifeweave-project:docs/architecture.md",
    "lifeweave-project:docs/status.md",
    "lifeweave-project:docs/development.md",
]


class DevelopmentService:
    def __init__(self, db, work, runtime, sources, project_root: Path):
        self.db, self.work, self.runtime, self.sources = db, work, runtime, sources
        self.project_root = project_root.resolve()

    @staticmethod
    def _git(*args: str, cwd: Path) -> str:
        result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                                text=True, timeout=10, check=False)
        if result.returncode:
            raise ValueError("项目目录必须是可读取且已有提交的 Git 仓库")
        return result.stdout.strip()

    def _project(self, value: str) -> tuple[str, str, bool]:
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("项目目录不存在")
        root = Path(self._git("rev-parse", "--show-toplevel", cwd=path)).resolve()
        revision = self._git("rev-parse", "HEAD", cwd=root)
        dirty = bool(self._git("status", "--porcelain", cwd=root))
        return str(root), revision, dirty

    def choices(self, workspace: str, item_id: str) -> dict[str, Any]:
        item = self.work.get_item(workspace, item_id)
        method = next((row for row in self.sources.catalog(workspace)["items"]
                       if row["title"] == "lifeweave-development"), None)
        codex = self.runtime.executors["codex"].health()
        return {
            "itemId": item_id,
            "recommendedRepositoryPath": str(self.project_root),
            "agents": [
                {"id": "development", "title": "开发 Agent", "version": method["id"] if method else "builtin-v1",
                 "available": bool(method and codex.available), "reason": "适用于代码项目的方案、审查、实施和验证"},
                {"id": "general", "title": "通用助理", "version": "conversation-v1", "available": True,
                 "reason": "适用于讨论、研究与记录，不自动修改代码"},
            ],
            "recommendedAgentId": "development" if item.get("itemType") in {"requirement", "fix"} else "general",
            "executors": {"codex": {"available": codex.available, "version": codex.version,
                                    "reason": codex.reason},
                          "opencode": {"available": False,
                                       "reason": "真实模型调用尚未验证成功，暂不用于自动开发链"}},
            "methodId": method["id"] if method else None,
            "knowledgeRefs": DEFAULT_PROJECT_REFS,
        }

    def _input_versions(self, workspace: str, method_id: str | None, refs: list[str]) -> list[dict[str, str]]:
        return [{"id": entry["id"], "version": entry["version"],
                 "sourcePath": entry["sourcePath"]}
                for entry in self.sources.snapshot(workspace, method_id, refs)]

    def create(self, workspace: str, *, item_id: str, request_id: str,
               instruction: str, repository_path: str, engine: str = "codex",
               model: str | None = None, method_id: str | None = None,
               knowledge_refs: list[str] | None = None,
               review_mode: str = "independent",
               acknowledge_excluded_changes: bool = False) -> dict[str, Any]:
        if engine != "codex":
            raise ValueError("开发工作链先使用已验证的 Codex；OpenCode 尚无成功模型调用")
        if review_mode not in {"independent", "self"}:
            raise ValueError("审查方式只能是独立审阅或轻量自检")
        if not self.runtime.executors["codex"].health().available:
            raise ValueError("Codex CLI 不可用，请先检查本机执行设置")
        self.work.get_item(workspace, item_id)
        fingerprint = hashlib.sha256(json.dumps({
            "instruction": instruction, "repositoryPath": str(Path(repository_path).expanduser().resolve()),
            "engine": engine, "model": model, "methodId": method_id,
            "knowledgeRefs": knowledge_refs, "reviewMode": review_mode,
        }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        existing = self.db.fetch_one("SELECT * FROM workbench.lifeweave_development_assignment "
                                     "WHERE workspace=%s AND item_id=%s AND request_id=%s",
                                     (workspace, item_id, request_id))
        if existing:
            if existing["request_fingerprint"] != fingerprint:
                raise ValueError("此请求身份已用于不同开发内容")
            return self._wire(existing)
        root, revision, dirty = self._project(repository_path)
        if dirty and not acknowledge_excluded_changes:
            raise ValueError("所选仓库有未提交改动；受管 Run 只读取已提交版本。请确认排除这些改动后重试")
        if method_id is None:
            method_id = self.choices(workspace, item_id)["methodId"]
        if not method_id:
            raise ValueError("开发方法未接入，无法固定 Agent 版本")
        refs = list(dict.fromkeys(knowledge_refs if knowledge_refs is not None else
                                  (DEFAULT_PROJECT_REFS if Path(root) == self.project_root else [])))
        if len(refs) > 10:
            raise ValueError("一次开发最多选择 10 篇知识")
        versions = self._input_versions(workspace, method_id, refs)
        context = self.work.current_context_snapshot(workspace, item_id)
        identity = "dev-" + hashlib.sha256(f"{workspace}:{item_id}:{request_id}".encode()).hexdigest()[:32]
        with self.db.atomic() as conn:
            # Serialize different request IDs for the same item before checking the
            # active assignment; an empty SELECT ... FOR UPDATE cannot lock a row.
            conn.execute("SELECT id FROM workbench.t_lifeweave_item "
                         "WHERE workspace_key=%s AND id=%s FOR UPDATE", (workspace, item_id)).fetchone()
            existing = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                                    "WHERE workspace=%s AND item_id=%s AND request_id=%s FOR UPDATE",
                                    (workspace, item_id, request_id)).fetchone()
            if existing:
                if existing["request_fingerprint"] != fingerprint:
                    raise ValueError("此请求身份已用于不同开发内容")
                return self._wire(existing)
            active = conn.execute("SELECT id FROM workbench.lifeweave_development_assignment "
                                  "WHERE workspace=%s AND item_id=%s AND status IN ('planning','reviewing','implementing') "
                                  "FOR UPDATE", (workspace, item_id)).fetchone()
            if active:
                raise ValueError("此事项仍有开发委托进行中，请先查看原委托")
            row = conn.execute("INSERT INTO workbench.lifeweave_development_assignment "
                               "(id,workspace,item_id,request_id,request_fingerprint,instruction,agent_id,agent_version,"
                               "engine,model,repository_path,repository_revision,working_tree_excluded,context_version_id,"
                               "method_id,knowledge_refs,input_versions,review_mode,status) "
                               "VALUES (%s,%s,%s,%s,%s,%s,'development',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planning') RETURNING *",
                               (identity, workspace, item_id, request_id, fingerprint, instruction,
                                next((entry["version"] for entry in versions if entry["id"] == method_id), "unknown"),
                                engine, model, root, revision, dirty, context["versionId"], method_id,
                                Jsonb(refs), Jsonb(versions), review_mode)).fetchone()
            run = self._stage_run(row, "plan", instruction)
            row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                               "SET plan_run_id=%s,updated_at=now() WHERE id=%s RETURNING *",
                               (run["id"], identity)).fetchone()
        return self._wire(row)

    def _stage_run(self, assignment: dict[str, Any], stage: str, instruction: str) -> dict[str, Any]:
        common = dict(item_id=assignment["item_id"], engine=assignment["engine"],
                      model=assignment["model"], directory=assignment["repository_path"],
                      method_id=assignment["method_id"], knowledge_refs=assignment["knowledge_refs"],
                      actor_id="development-agent")
        if stage == "plan":
            prompt = ("开发委托的只读方案阶段。只能阅读仓库与已选知识，不能修改文件。"
                      "请写用户将看到的行为、受影响模块和接口、实现顺序、风险、验证、知识变化。"
                      "结尾必须有“自检”及尚未解决的问题。\n\n用户任务：" + instruction)
            return self.runtime.create_run(assignment["workspace"], instruction=prompt,
                                           permission="read-only", **common)
        if stage == "review":
            prompt = ("你是独立方案审阅者，本次为全新只读 Run。请核对用户原目标、项目提交、方案的遗漏和可验证性，"
                      "不得实施或修改文件。结束时单独一行写 REVIEW_DECISION: PASS 或 "
                      "REVIEW_DECISION: NEEDS_REVISION，并解释具体问题。\n\n"
                      f"用户任务：{assignment['instruction']}\n"
                      f"审查方案 SHA-256：{assignment['plan_sha256']}\n\n"
                      f"方案正文：\n{assignment['plan']}")
            return self.runtime.create_run(assignment["workspace"], instruction=prompt,
                                           permission="read-only", **common)
        prompt = ("按已审方案在本轮隔离工作树实施，运行与改动相称的真实验证。"
                  "交付时给出实际文件差异、测试结果、未完成项和知识更新；不要声称代码已合回原仓。\n\n"
                  f"用户任务：{assignment['instruction']}\n"
                  f"已审方案 SHA-256：{assignment['plan_sha256']}\n{assignment['plan']}\n\n"
                  f"审阅记录：{assignment['review']}")
        return self.runtime.create_run(assignment["workspace"], instruction=prompt,
                                       permission="workspace-write", **common)

    def _assert_unchanged(self, row: dict[str, Any]) -> None:
        root, revision, _ = self._project(row["repository_path"])
        if root != row["repository_path"] or revision != row["repository_revision"]:
            raise ValueError("项目提交已变化；旧方案不能直接用于新源码，请重新委托")
        context = self.work.current_context_snapshot(row["workspace"], row["item_id"])
        if context["versionId"] != row["context_version_id"]:
            raise ValueError("事项背景已更新；请按新共识重新形成方案")
        if self._input_versions(row["workspace"], row["method_id"], row["knowledge_refs"]) != row["input_versions"]:
            raise ValueError("所选方法或知识版本已变化；请重新形成方案")

    def advance(self, identity: str) -> None:
        with self.db.atomic() as conn:
            row = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                               "WHERE id=%s FOR UPDATE", (identity,)).fetchone()
            if not row or row["status"] not in ACTIVE:
                return
            status = row["status"]
            run_id = {"planning": row["plan_run_id"], "reviewing": row["review_run_id"],
                      "implementing": row["implementation_run_id"]}[status]
            if not run_id:
                raise RuntimeError("开发委托缺少当前阶段的 Run")
            run = self.runtime.get_run_snapshot(row["workspace"], run_id)
            if run["state"] not in TERMINAL_RUNS:
                return
            if run["state"] != "succeeded":
                target = "cancelled" if run["state"] == "cancelled" else "failed"
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status=%s,error=%s,updated_at=now() WHERE id=%s",
                             (target, f"{status} 阶段 {run['state']}：{str(run.get('error') or '')[:1500]}", identity))
                return
            if status == "implementing":
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='awaiting_acceptance',updated_at=now() WHERE id=%s", (identity,))
                return
            result = str(run.get("result") or "").strip()
            if status == "planning" and len(result) < 80:
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='blocked',error='方案正文过短，未进入实施',updated_at=now() WHERE id=%s",
                             (identity,))
                return
            if status == "planning":
                digest = hashlib.sha256(result.encode()).hexdigest()
                row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                   "SET plan=%s,plan_sha256=%s,updated_at=now() WHERE id=%s RETURNING *",
                                   (result, digest, identity)).fetchone()
            try:
                self._assert_unchanged(row)
            except (ValueError, OSError) as exc:
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='blocked',error=%s,updated_at=now() WHERE id=%s",
                             (str(exc), identity))
                return
            if status == "planning" and row["review_mode"] == "independent":
                review = self._stage_run(row, "review", row["instruction"])
                conn.execute("UPDATE workbench.lifeweave_development_assignment "
                             "SET status='reviewing',review_run_id=%s,updated_at=now() WHERE id=%s",
                             (review["id"], identity))
                return
            if status == "reviewing":
                decision = "pass" if re.search(r"^REVIEW_DECISION:\s*PASS\s*$", result, re.I | re.M) else "needs_revision"
                row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                   "SET review=%s,review_decision=%s,updated_at=now() WHERE id=%s RETURNING *",
                                   (result, decision, identity)).fetchone()
                if decision != "pass":
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='blocked',error='独立审阅未通过或没有明确 PASS',updated_at=now() WHERE id=%s",
                                 (identity,))
                    return
            else:
                if "自检" not in result:
                    conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                 "SET status='blocked',error='轻量方案缺少自检',updated_at=now() WHERE id=%s",
                                 (identity,))
                    return
                row = conn.execute("UPDATE workbench.lifeweave_development_assignment "
                                   "SET review='方案阶段自检（非独立审阅）',review_decision='self_checked',"
                                   "updated_at=now() WHERE id=%s RETURNING *", (identity,)).fetchone()
            implementation = self._stage_run(row, "implementation", row["instruction"])
            conn.execute("UPDATE workbench.lifeweave_development_assignment "
                         "SET status='implementing',implementation_run_id=%s,updated_at=now() WHERE id=%s",
                         (implementation["id"], identity))

    def scan(self) -> None:
        rows = self.db.fetch_all("SELECT id FROM workbench.lifeweave_development_assignment "
                                 "WHERE status IN ('planning','reviewing','implementing') ORDER BY created_at")
        for row in rows:
            try:
                self.advance(row["id"])
            except Exception as exc:
                # Fail visibly; never advance to writable execution after an uncertain transition.
                self.db.execute("UPDATE workbench.lifeweave_development_assignment "
                                "SET status='blocked',error=%s,updated_at=now() WHERE id=%s AND "
                                "status IN ('planning','reviewing','implementing')",
                                (f"阶段推进失败：{type(exc).__name__}: {str(exc)[:1400]}", row["id"]))

    def list(self, workspace: str, item_id: str) -> list[dict[str, Any]]:
        self.work.get_item(workspace, item_id)
        rows = self.db.fetch_all("SELECT * FROM workbench.lifeweave_development_assignment "
                                 "WHERE workspace=%s AND item_id=%s ORDER BY created_at DESC",
                                 (workspace, item_id))
        return [self._wire(row) for row in rows]

    def get(self, workspace: str, identity: str) -> dict[str, Any]:
        row = self.db.fetch_one("SELECT * FROM workbench.lifeweave_development_assignment "
                                "WHERE workspace=%s AND id=%s", (workspace, identity))
        if not row:
            raise KeyError(identity)
        return self._wire(row)

    def diff(self, workspace: str, identity: str) -> dict[str, Any]:
        assignment = self.get(workspace, identity)
        run_id = assignment['implementationRunId']
        if not run_id:
            raise ValueError('实施阶段尚未建立工作目录')
        run = self.runtime.get_run_snapshot(workspace, run_id)
        actual = (run.get('environment_snapshot') or {}).get('actualDirectory')
        if not actual:
            raise ValueError('执行机尚未报告实际工作目录')
        directory = Path(actual).resolve()
        if not directory.is_relative_to(self.project_root / '.runtime' / 'executions') or not directory.is_dir():
            raise ValueError('本机无法读取该运行的隔离工作目录')
        base = assignment['repositoryRevision']
        changed = subprocess.run(['git', '-C', str(directory), 'diff', '--name-only', '-z', base],
                                 capture_output=True, timeout=10, check=False)
        if changed.returncode:
            raise ValueError('无法从原始提交读取运行差异')
        untracked = subprocess.run(['git', '-C', str(directory), 'ls-files', '--others', '--exclude-standard', '-z'],
                                   capture_output=True, timeout=10, check=False)
        if untracked.returncode:
            raise ValueError('运行工作目录不是可读取的 Git 检出')
        environment = run.get('environment_snapshot') or {}
        generated = set(environment.get('materializedInputFiles') or environment.get('materializedCapabilities') or [])
        if generated:
            generated.add('.lifeweave/capability-manifest.json')
        untracked_paths = [part.decode('utf-8', 'replace') for part in untracked.stdout.split(b'\0') if part]
        paths = list(dict.fromkeys([part.decode('utf-8', 'replace') for part in changed.stdout.split(b'\0') if part] +
                                   untracked_paths))
        paths = [path for path in paths if path not in generated]
        patch = ''
        if paths:
            output = subprocess.run(['git', '-C', str(directory), 'diff', '--no-ext-diff', base, '--', *paths],
                                    capture_output=True, timeout=10, check=False,
                                    env={**os.environ, 'GIT_LITERAL_PATHSPECS': '1'})
            if output.returncode:
                raise ValueError('Git 差异读取失败')
            patch = output.stdout.decode('utf-8', 'replace')
        for relative in untracked_paths:
            if relative in generated:
                continue
            file = directory / relative
            if not file.is_file() or file.is_symlink() or file.stat().st_size > 100_000:
                continue
            try:
                content = file.read_text()
            except UnicodeError:
                continue
            patch += ''.join(difflib.unified_diff([], content.splitlines(keepends=True),
                         fromfile='/dev/null', tofile='b/' + relative))
        return {'runId': run_id, 'baseRevision': assignment['repositoryRevision'],
                'files': paths[:100], 'fileCount': len(paths), 'generatedInputsExcluded': sorted(generated),
                'patch': patch[:200_000], 'truncated': len(paths) > 100 or len(patch) > 200_000}

    def cancel(self, workspace: str, identity: str) -> dict[str, Any]:
        with self.db.atomic() as conn:
            row = conn.execute("SELECT * FROM workbench.lifeweave_development_assignment "
                               "WHERE workspace=%s AND id=%s FOR UPDATE", (workspace, identity)).fetchone()
            if not row:
                raise KeyError(identity)
            if row["status"] not in ACTIVE:
                raise ValueError("开发委托已结束")
            run_id = {"planning": row["plan_run_id"], "reviewing": row["review_run_id"],
                      "implementing": row["implementation_run_id"]}[row["status"]]
            self.runtime.request_cancel(workspace, run_id)
        return self.get(workspace, identity)

    @staticmethod
    def _wire(row: dict[str, Any]) -> dict[str, Any]:
        names = {"item_id": "itemId", "agent_id": "agentId", "agent_version": "agentVersion",
                 "repository_path": "repositoryPath", "repository_revision": "repositoryRevision",
                 "working_tree_excluded": "workingTreeExcluded", "review_mode": "reviewMode",
                 "review_decision": "reviewDecision", "plan_run_id": "planRunId",
                 "review_run_id": "reviewRunId", "implementation_run_id": "implementationRunId",
                 "plan_sha256": "planSha256", "created_at": "createdAt", "updated_at": "updatedAt",
                 "knowledge_refs": "knowledgeRefs", "input_versions": "inputVersions",
                 "context_version_id": "contextVersionId", "method_id": "methodId"}
        visible = {"id", "item_id", "instruction", "agent_id", "agent_version", "engine", "model",
                   "repository_path", "repository_revision", "working_tree_excluded", "review_mode",
                   "review_decision", "status", "plan_run_id", "review_run_id", "implementation_run_id",
                   "plan", "plan_sha256", "review", "error", "created_at", "updated_at",
                   "knowledge_refs", "input_versions", "context_version_id", "method_id"}
        return {names.get(key, key): value for key, value in row.items() if key in visible}

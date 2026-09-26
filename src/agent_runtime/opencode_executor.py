from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from typing import Any, Awaitable, Callable

from .executor import (
    ExecutorHealth,
    ExecutorRequest,
    ExecutorResult,
    SUBPROCESS_STREAM_LIMIT,
    classify_failure,
    cleanup_process_group,
    terminate_process,
)


EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


WRITE_BASH_PERMISSION = {
    "*": "allow",
    "git push*": "deny",
    "git merge*": "deny",
    "gh pr create*": "deny",
    "glab mr create*": "deny",
}


def _nested(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and item is not None and not isinstance(item, (dict, list)):
                return str(item)
            found = _nested(item, keys)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _nested(item, keys)
            if found:
                return found
    return None


def _text(value: Any) -> str:
    return _nested(value, {"text", "message", "content"}) or ""


def _event_summary(payload: dict[str, Any], event_type: str) -> str:
    part = payload.get("part")
    part_value = part if isinstance(part, dict) else {}
    part_type = str(part_value.get("type", ""))
    if event_type == "text" or part_type == "text":
        return str(part_value.get("text") or payload.get("text") or "text")
    if event_type == "tool_use" or part_type == "tool":
        tool = str(part_value.get("tool") or "tool")
        state = part_value.get("state")
        state_value = state if isinstance(state, dict) else {}
        title = str(state_value.get("title") or "")
        return f"{tool}: {title}" if title else tool
    if event_type == "step_finish" or part_type == "step-finish":
        reason = str(part_value.get("reason") or "finished")
        tokens = part_value.get("tokens")
        token_value = tokens if isinstance(tokens, dict) else {}
        total = token_value.get("total")
        return f"{reason} · {total} tokens" if total is not None else reason
    return _text(payload) or event_type


class OpenCodeExecutor:
    name = "opencode"

    def __init__(self, *, command: str = "opencode", endpoint: str = "") -> None:
        self.command = command
        self.endpoint = endpoint.strip()

    def health(self) -> ExecutorHealth:
        resolved = shutil.which(self.command)
        if not resolved:
            return ExecutorHealth(
                name=self.name,
                available=False,
                command=self.command,
                reason=f"找不到命令：{self.command}",
                details={"endpoint": self.endpoint or None},
            )
        try:
            result = subprocess.run(
                [resolved, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ExecutorHealth(
                name=self.name,
                available=False,
                command=resolved,
                reason=str(exc),
                details={"endpoint": self.endpoint or None},
            )
        lines = (result.stdout or result.stderr).strip().splitlines()
        return ExecutorHealth(
            name=self.name,
            available=result.returncode == 0,
            command=resolved,
            version=lines[0] if lines else None,
            reason=None if result.returncode == 0 else "OpenCode 版本检查失败",
            details={"endpoint": self.endpoint or None},
        )

    def command_for(
        self,
        request: ExecutorRequest,
    ) -> list[str]:
        argv = [
            *request.command_prefix,
            self.command,
            *(("--pure",) if request.sandbox == "read-only" else ()),
            "run",
            "--format",
            "json",
            "--auto",
            "--dir",
            str(request.worktree_argument or request.worktree),
            "--title",
            request.run_id,
        ]
        if self.endpoint:
            argv.extend(["--attach", self.endpoint])
        if request.model:
            argv.extend(["--model", request.model])
        if len(request.prompt.encode("utf-8")) > 100_000:
            if request.artifact_path is None:
                raise ValueError("大段任务输入需要产物目录")
            prompt_file = request.artifact_path / "task-input.md"
            prompt_file.write_text(request.prompt, encoding="utf-8")
            argument = (request.artifact_argument_root or request.artifact_path) / "task-input.md"
            argv.extend(["--file", str(argument), "请执行附件 task-input.md 中的完整任务，并交付实际结果。"])
        else:
            argv.append(request.prompt)
        return argv

    @staticmethod
    def environment_for(request: ExecutorRequest) -> dict[str, str]:
        env = {
            **(os.environ if request.inherit_environment else {}),
            **request.environment,
        }
        existing: dict[str, Any] = {}
        raw = env.get("OPENCODE_CONFIG_CONTENT", "").strip()
        if raw:
            try:
                candidate = json.loads(raw)
                if isinstance(candidate, dict):
                    existing = candidate
            except json.JSONDecodeError:
                pass
        if request.sandbox == "workspace-write":
            permission = {
                "edit": "allow",
                "bash": WRITE_BASH_PERMISSION,
                "task": "deny",
                "external_directory": "deny",
            }
        else:
            permission = {
                "edit": "deny",
                # Subagents have their own effective permissions. The Task tool
                # let one write during a read-only planning Run, so both task
                # delegation and shell execution are unavailable in this stage.
                "bash": "deny",
                "task": "deny",
                "external_directory": "deny",
            }
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            {**existing, "permission": permission},
            ensure_ascii=False,
        )
        return env

    async def run(
        self,
        request: ExecutorRequest,
        on_event: EventCallback,
        on_process: Callable[[asyncio.subprocess.Process], None],
    ) -> ExecutorResult:
        process = await asyncio.create_subprocess_exec(
            *self.command_for(request),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=SUBPROCESS_STREAM_LIMIT,
            cwd=request.worktree,
            env=self.environment_for(request),
            start_new_session=os.name == "posix",
        )
        on_process(process)
        session_id: str | None = None
        final_message = ""
        failure_reason: str | None = None
        failure_code: str | None = None
        captured: dict[str, list[str]] = {"stdout": [], "stderr": []}

        async def read(stream: asyncio.StreamReader | None, channel: str) -> None:
            nonlocal session_id, final_message, failure_reason, failure_code
            if stream is None:
                return
            while raw := await stream.readline():
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                if line and len(captured[channel]) < 200:
                    captured[channel].append(line)
                payload: dict[str, Any]
                try:
                    parsed = json.loads(line)
                    payload = parsed if isinstance(parsed, dict) else {"value": parsed}
                except json.JSONDecodeError:
                    payload = {"text": line}
                event_type = str(payload.get("type") or payload.get("event") or f"opencode.{channel}")
                found_session = _nested(
                    payload,
                    {"session_id", "sessionId", "sessionID", "thread_id", "threadId"},
                )
                if found_session:
                    session_id = found_session
                text = _event_summary(payload, event_type)
                part = payload.get("part")
                part_value = part if isinstance(part, dict) else {}
                if event_type == "text" or str(part_value.get("type", "")) == "text":
                    final_message = text
                if event_type.casefold() == "error":
                    failure_reason = _text(payload) or "OpenCode 返回错误事件"
                    raw_status = _nested(payload, {"statusCode", "status_code"})
                    try:
                        status_code = int(raw_status) if raw_status else None
                    except ValueError:
                        status_code = None
                    failure_code = classify_failure(failure_reason, status_code)
                    final_message = failure_reason
                await on_event(
                    {
                        "event_type": event_type,
                        "source": "opencode",
                        "channel": channel,
                        "summary": text,
                        "payload": payload,
                    }
                )

        readers = [
            asyncio.create_task(read(process.stdout, "stdout")),
            asyncio.create_task(read(process.stderr, "stderr")),
        ]
        try:
            exit_code = await process.wait()
            await cleanup_process_group(process)
            await asyncio.gather(*readers)
        except BaseException:
            await terminate_process(process)
            for reader in readers:
                reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
            raise

        if exit_code != 0 and not failure_reason:
            failure_reason = "\n".join(captured["stderr"] or captured["stdout"]).strip()
            failure_reason = failure_reason or f"OpenCode 退出码 {exit_code}"
            failure_code = classify_failure(failure_reason)
            final_message = failure_reason
        return ExecutorResult(
            executor=self.name,
            exit_code=exit_code,
            session_id=session_id,
            final_message=final_message,
            failure_code=failure_code,
            failure_reason=failure_reason,
        )

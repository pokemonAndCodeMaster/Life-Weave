"""Readable PostgreSQL text with lossless evidence for PDF NUL characters."""
from __future__ import annotations

import base64
import json
from typing import Any


def preserve_nul_text(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Project NUL as its visible symbol; retain the exact original JSON separately.

    PostgreSQL rejects NUL in both text and JSONB. Do not let an executor's PDF
    extraction terminate an otherwise healthy run, or silently discard evidence.
    This is a storage projection, not a change to the executor's source files.
    """
    changed = False

    def project(item: Any) -> Any:
        nonlocal changed
        if isinstance(item, str):
            if "\0" in item:
                changed = True
                return item.replace("\0", "␀")
            return item
        if isinstance(item, list):
            return [project(child) for child in item]
        if isinstance(item, dict):
            # A NUL-bearing key could collide with a literal visible-symbol key.
            # Keep those objects as a readable list of entries instead of losing
            # either member. The original JSON below also preserves key identity.
            if any("\0" in key for key in item):
                return {"entries": [[project(key), project(child)] for key, child in item.items()]}
            return {key: project(child) for key, child in item.items()}
        return item

    projected = project(value)
    if not changed:
        return projected, None
    original = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return projected, {
        "format": "original-json-base64-v1",
        "note": "PostgreSQL 不支持 NUL；可读正文以 ␀ 显示，原始 JSON 无损保存在 originalJsonBase64。",
        "originalJsonBase64": base64.b64encode(original).decode("ascii"),
    }


def result_text_storage(run: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return original executor bytes as text and an optional reader-facing note.

    An earlier running report may have stored metadata for an unrelated field;
    only use a record whose result fields still match the stored projection.
    """
    result = run.get("result")
    metadata = (run.get("environment_snapshot") or {}).get("_lifeweaveTextStorage")
    if not isinstance(metadata, dict) or metadata.get("format") != "original-json-base64-v1":
        return result, None
    try:
        original = json.loads(base64.b64decode(metadata["originalJsonBase64"], validate=True))
        fields = {key: original.get(key) for key in ("result", "result_payload")}
        projected, encoding = preserve_nul_text(fields)
        if not encoding or any(projected[key] != run.get(key) for key in fields):
            return result, None
    except (ValueError, TypeError, KeyError, AttributeError):
        return result, None
    return fields["result"], (
        "原始执行文本含不可显示的 NUL 字符，阅读正文用 ␀ 标出；"
        "正文下载与当前阅读版本一致，原始执行文本另行保留，不要把 ␀ 当作论文公式。"
    )

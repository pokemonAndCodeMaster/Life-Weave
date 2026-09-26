"""Resolve a local Git file to a verified immutable GitHub source URL."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import quote


def confirmed_github_blob(root: Path, path: str, content: bytes,
                          archive_base_url: str, timeout: int = 15) -> str:
    match = re.fullmatch(r'https://github\.com/([^/]+)/([^/]+)/blob/main',
                         archive_base_url.rstrip('/'))
    if not match:
        raise ValueError('GitHub 原文地址不是可核验的 main 分支')
    if Path(path).is_absolute() or '..' in Path(path).parts:
        raise ValueError('GitHub 原文路径越界')
    try:
        head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        committed = subprocess.run(['git', '-C', str(root), 'show', f'HEAD:{path}'],
                                   capture_output=True, timeout=10, check=True).stdout
        remote = subprocess.run(['git', 'ls-remote',
                                 f'https://github.com/{match.group(1)}/{match.group(2)}.git',
                                 'refs/heads/main'], capture_output=True, text=True,
                                timeout=timeout, check=True).stdout.split()
    except subprocess.SubprocessError as exc:
        raise ValueError('无法核验 GitHub 原文版本；请先提交并推送，再重试') from exc
    if committed != content or not remote or remote[0] != head:
        raise ValueError('原文尚未作为当前 main 提交推送到 GitHub')
    return f'https://github.com/{match.group(1)}/{match.group(2)}/blob/{head}/{quote(path, safe="/")}'

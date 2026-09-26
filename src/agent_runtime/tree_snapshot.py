"""Content identity of an isolated execution tree, independent of Git metadata."""

import hashlib
import os
from pathlib import Path
import stat


def tree_sha256(root: Path) -> str:
    """Hash files, empty directories, modes and symlink targets without following links."""
    digest = hashlib.sha256()
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("执行目录不存在")

    def visit(directory: Path) -> None:
        for entry in sorted(os.scandir(directory), key=lambda value: value.name):
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix().encode("utf-8", "surrogateescape")
            info = entry.stat(follow_symlinks=False)
            kind = stat.S_IFMT(info.st_mode)
            digest.update(len(relative).to_bytes(8, "big") + relative)
            digest.update(kind.to_bytes(8, "big"))
            digest.update(stat.S_IMODE(info.st_mode).to_bytes(8, "big"))
            if stat.S_ISDIR(info.st_mode):
                visit(path)
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(path).encode("utf-8", "surrogateescape")
                digest.update(len(target).to_bytes(8, "big") + target)
            elif stat.S_ISREG(info.st_mode):
                digest.update(info.st_size.to_bytes(8, "big"))
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
            else:
                raise ValueError("执行目录出现无法核对的文件类型")

    visit(root)
    return digest.hexdigest()

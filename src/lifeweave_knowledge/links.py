"""Rebuildable Markdown relations for the library's current visible files."""
from __future__ import annotations

import posixpath
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import unquote, urlsplit

import mistune

from .library import Library, fingerprint


def _label(token: dict[str, Any]) -> str:
    return ''.join(str(child.get('raw', '')) if child.get('type') in {'text', 'codespan'} else _label(child)
                   for child in token.get('children', []))


class KnowledgeLinks:
    def __init__(self, library: Library) -> None:
        self.library = library
        self.parser = mistune.create_markdown(renderer='ast', plugins=['table', 'math'])
        self.cache: dict[tuple[str, str, str], tuple[tuple[str, int, int], dict[str, Any]]] = {}
        self.lock = RLock()

    def _links(self, workspace: str, source_id: str, path: str, content: str) -> list[dict[str, Any]]:
        found: dict[tuple[str, str], dict[str, Any]] = {}

        def walk(tokens: list[dict[str, Any]]) -> None:
            for token in tokens:
                if token.get('type') == 'link':
                    href = str(token.get('attrs', {}).get('url') or '')
                    parsed = urlsplit(href)
                    if not parsed.scheme and not parsed.netloc and parsed.path and not parsed.path.startswith('/'):
                        decoded = unquote(parsed.path)
                        if decoded.lower().endswith('.md'):
                            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), decoded))
                            status = 'valid'
                            try:
                                self.library.file(workspace, source_id, target)
                            except (ValueError, KeyError, OSError):
                                status = 'blocked'
                            key = (target if status == 'valid' else href, status)
                            if key not in found:
                                found[key] = {'label': _label(token).strip() or Path(decoded).stem,
                                              'href': href, 'path': target if status == 'valid' else None,
                                              'status': status, 'count': 0}
                            found[key]['count'] += 1
                walk(token.get('children', []))

        walk(self.parser(content))
        return list(found.values())

    def _document(self, workspace: str, source_id: str, path: str, file: Path,
                  selected: dict[str, Any] | None = None) -> dict[str, Any]:
        stat = file.stat()
        stamp = (str(file), stat.st_mtime_ns, stat.st_size)
        key = (workspace, source_id, path)
        cached = self.cache.get(key)
        if cached and cached[0] == stamp and (not selected or cached[1]['version'] == selected['version']):
            return cached[1]
        content = selected['content'] if selected else file.read_text(encoding='utf-8')
        row = {'sourceId': source_id, 'path': path,
               'title': selected['title'] if selected else self.library.title(content, path),
               'version': fingerprint(content), 'links': self._links(workspace, source_id, path, content)}
        self.cache[key] = (stamp, row)
        return row

    def document_links(self, workspace: str, source_id: str, path: str) -> dict[str, Any]:
        selected = self.library.document(workspace, source_id, path)
        with self.lock:
            corpus: dict[tuple[str, str], dict[str, Any]] = {}
            unavailable_sources: list[str] = []
            unavailable_documents: list[dict[str, str]] = []
            # Relations are defined only within one source; scanning unrelated
            # project or personal directories adds cost without possible links.
            for source in [self.library.source(workspace, source_id)]:
                root = Path(source['root'])
                if not root.is_dir():
                    unavailable_sources.append(source['title'])
                    continue
                for relative, entry in self.library.files(source):
                    if any(part.startswith('.') or part in {'raw', 'node_modules'} for part in Path(relative).parts):
                        continue
                    try:
                        safe = self.library.file(workspace, source['id'], relative)
                        if not safe.is_file():
                            continue
                        if safe.stat().st_size > 2_000_000:
                            raise ValueError('文件超过 2 MB')
                        corpus[(source['id'], relative)] = self._document(
                            workspace, source['id'], relative, safe,
                            selected if (source['id'], relative) == (source_id, path) else None,
                        )
                    except (ValueError, KeyError, OSError, UnicodeError) as exc:
                        unavailable_documents.append({'path': source['id'] + ':' + relative, 'reason': str(exc)})
            active = {(workspace, source, relative) for source, relative in corpus}
            for key in list(self.cache):
                if key[0] == workspace and key not in active:
                    del self.cache[key]
            outgoing = []
            backlinks = []
            for (current_source, current_path), doc in corpus.items():
                for link in doc['links']:
                    target = (current_source, link['path']) if link['path'] else None
                    if (current_source, current_path) == (source_id, path):
                        outgoing.append({**link, 'sourceId': current_source,
                                         'status': 'missing' if link['status'] == 'valid' and target not in corpus else link['status']})
                    if target == (source_id, path) and (current_source, current_path) != target:
                        backlinks.append({'sourceId': current_source, 'path': current_path,
                                          'title': doc['title'], 'label': link['label'], 'count': link['count']})
            return {'sourceId': source_id, 'path': path, 'version': selected['version'],
                    'outgoing': outgoing, 'backlinks': backlinks,
                    'scannedDocuments': len(corpus), 'unavailableSources': unavailable_sources,
                    'unavailableDocuments': unavailable_documents}

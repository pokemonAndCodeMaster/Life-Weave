"""Derive run-relative reference identity without rewriting Markdown originals."""
from urllib.parse import quote, unquote, urlsplit
import mistune


def references(content, workspace, run_id):
    result = {'links':{}, 'images':{}, 'warnings':[]}
    parser = mistune.create_markdown(renderer='ast', plugins=['table','math'])
    base = f'/api/lifeweave/{workspace}/runs/{quote(run_id,safe="")}'
    def walk(tokens):
        for token in tokens:
            if token['type'] in {'link','image'}:
                href = token.get('attrs',{}).get('url','')
                parsed = urlsplit(href)
                if href and not parsed.scheme and not parsed.netloc and parsed.path and not href.startswith(('/','#')):
                    kind = 'images' if token['type']=='image' else 'links'
                    result[kind][href] = base+('/assets' if kind=='images' else '/source')+'?path='+quote(unquote(parsed.path),safe='')
            walk(token.get('children',[]))
    walk(parser(content))
    return result


def merge_references(groups):
    result = {'links':{}, 'images':{}, 'warnings':[]}
    conflicts = {'links':set(), 'images':set()}
    for group in groups:
        for kind in ('links','images'):
            for href,target in group[kind].items():
                if href in conflicts[kind]:
                    continue
                if href in result[kind] and result[kind][href] != target:
                    del result[kind][href]
                    conflicts[kind].add(href)
                    result['warnings'].append('多个来源使用相同相对引用 '+href+'，请从各自来源成果打开；未自动选择其中一次运行。')
                else:
                    result[kind][href] = target
    return result

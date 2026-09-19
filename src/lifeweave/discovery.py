"""Explainable lexical discovery, shared by work and input discovery.

This ranks candidates; it neither resolves user intent nor authorizes execution.
"""
import re


def terms(text: str) -> set[str]:
    result = set(re.findall(r'[a-z0-9][a-z0-9_-]+', text.casefold()))
    for segment in re.findall(r'[\u4e00-\u9fff]+', text):
        result.update(segment[i:i + 2] for i in range(len(segment) - 1))
    return result - {'the', 'and', 'for', 'with', 'this', 'that', '一个', '我们', '帮我', '想要', '一下', '什么', '可以', '这个', '继续'}


def match(query: str, title: str, body: str = '') -> dict:
    wanted = terms(query)
    title_hits = wanted & terms(title)
    body_hits = wanted & terms(body)
    exact = bool(query.strip()) and query.strip().casefold() in title.casefold()
    return {'score': 4 * len(title_hits) + len(body_hits) + (8 if exact else 0),
            'matchedTerms': sorted(title_hits | body_hits),
            'reason': '标题或正文包含：' + '、'.join(sorted(title_hits | body_hits)) if title_hits or body_hits else ('标题直接匹配' if exact else '')}

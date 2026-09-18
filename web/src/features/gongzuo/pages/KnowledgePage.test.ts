import { describe, expect, it } from 'vitest'
import { resolveKnowledgePath } from '../utils/knowledgeLinks'

describe('KnowledgePage links', () => {
  it('把知识目录内的相对 Markdown 链接解析为可读取路径', () => {
    expect(resolveKnowledgePath('docs/specs/current.md', '../blueprint.md#section')).toBe('docs/blueprint.md')
    expect(resolveKnowledgePath('README.md', 'docs/now.md')).toBe('docs/now.md')
  })

  it('不把目录外定位、源码或危险协议伪装成可导航知识', () => {
    expect(resolveKnowledgePath('README.md', '../outside.md')).toBeNull()
    expect(resolveKnowledgePath('docs/current.md', '../src/app.py')).toBeNull()
    expect(resolveKnowledgePath('docs/current.md', 'javascript:alert(1)')).toBeNull()
  })
})

describe('真实中文链接', () => {
  it('只解码一次并保持目录边界', () => {
    expect(resolveKnowledgePath('index.md', '%E5%BC%80%E5%A7%8B%E4%BD%BF%E7%94%A8.md')).toBe('开始使用.md')
    expect(resolveKnowledgePath('目录/入口.md', '../有%20空格.md')).toBe('有 空格.md')
    expect(resolveKnowledgePath('index.md', '%2E%2E/outside.md')).toBeNull()
  })
})

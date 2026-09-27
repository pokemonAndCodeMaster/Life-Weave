// @vitest-environment jsdom
import { render, cleanup, screen, fireEvent, waitFor } from '@testing-library/vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MarkdownBody from '../MarkdownBody.vue'
import { renderMermaid } from '../../utils/mermaidRenderer'
vi.mock('../../utils/mermaidRenderer', () => ({ renderMermaid: vi.fn() }))
afterEach(cleanup)
beforeEach(() => { vi.mocked(renderMermaid).mockReset(); vi.mocked(renderMermaid).mockResolvedValue('<svg viewBox="0 0 100 30"><text>中文流程</text></svg>') })

describe('shared document reading', () => {
  it('renders Mermaid without changing code samples, and provides readable failure source', async () => {
    const view=render(MarkdownBody,{props:{content:'# 报告\n\n```mermaid\nflowchart LR\nA[输入] --> B[输出]\n```\n\n```text\nflowchart LR\n```'}})
    await waitFor(() => expect(view.container.querySelector('.diagram-svg svg')).not.toBeNull())
    expect(renderMermaid).toHaveBeenCalledWith(expect.any(String),'flowchart LR\nA[输入] --> B[输出]')
    expect(view.container.querySelector('pre code')?.textContent).toContain('flowchart LR')
    vi.mocked(renderMermaid).mockRejectedValueOnce(new Error('第 2 行缺少结束括号'))
    await view.rerender({content:'```mermaid\nflowchart LR\nA[broken\n```'})
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('第 2 行'))
    expect(view.container.querySelector('.diagram-source')?.hasAttribute('open')).toBe(true)
    expect(view.container.querySelector('.diagram-source code')?.textContent).toContain('A[broken')
  })

  it('ignores a late diagram after the document changes', async () => {
    let resolve!: (svg:string)=>void
    vi.mocked(renderMermaid).mockImplementationOnce(()=>new Promise(done=>{resolve=done}))
    const view=render(MarkdownBody,{props:{content:'```mermaid\nflowchart LR\nA-->B\n```'}})
    await flushPromises()
    await view.rerender({content:'# 新文档\n\n正文没有框图'})
    resolve('<svg><text>旧文档框图</text></svg>');await flushPromises()
    expect(view.container.textContent).toContain('新文档')
    expect(view.container.textContent).not.toContain('旧文档框图')
    expect(view.container.querySelector('.diagram-svg')).toBeNull()
  })

  it('accepts only registered same-workspace media routes', () => {
    const references={links:{},warnings:[],images:{
      'current.png':'/api/lifeweave/personal/library/asset?sourceId=project&documentPath=docs/a.md&version=v1&path=current.png',
      'fixed.png':'/api/lifeweave/personal/items/i/outputs/asset?outputId=o&version=v1&path=fixed.png',
      'other.png':'/api/lifeweave/team/items/i/outputs/asset?outputId=o&version=v1&path=other.png',
      'remote.png':'https://external.test/image.png',
      'network.png':'//external.test/api/lifeweave/personal/library/asset?path=image.png',
    }}
    const {container}=render(MarkdownBody,{props:{workspace:'personal',content:'![当前](current.png) ![固定](fixed.png) ![越界](other.png) ![外部](remote.png) ![外网](network.png)',references}})
    expect(Array.from(container.querySelectorAll('img')).map(x=>x.alt)).toEqual(['当前','固定'])
    expect(container.querySelectorAll('.reading-image-open')).toHaveLength(2)
  })

  it('provides outline, local table scrolling, code copy and bad-formula fallback', async () => {
    const writeText=vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator,'clipboard',{value:{writeText},configurable:true})
    const {container}=render(MarkdownBody,{props:{outline:true,content:'# 报告\n\n## 结果\n\n|列一|列二|\n|---|---|\n|值一|值二|\n\n```python\nprint("ok")\n```\n\n$\\notARealCommand{x}$'}})
    expect(screen.getByRole('navigation',{name:'文档目录'}).querySelectorAll('a')).toHaveLength(2)
    expect(screen.getByRole('region',{name:'表格，可横向滚动'}).querySelector('th')?.textContent).toBe('列一')
    await fireEvent.click(screen.getByRole('button',{name:'复制代码'}))
    expect(writeText).toHaveBeenCalledWith('print("ok")\n')
    expect(container.textContent).toContain('公式未能排版，保留原式')
  })
})

it('keeps plain-text artifacts literal instead of interpreting Markdown or HTML',async()=>{
 const writeText=vi.fn().mockResolvedValue(undefined);Object.defineProperty(navigator,'clipboard',{value:{writeText},configurable:true})
 const content='# This is source text\n<script>alert(1)</script>\n$raw$'
 const {container}=render(MarkdownBody,{props:{content,plainText:true}})
 expect(container.querySelector('h1,script,.katex')).toBeNull()
 expect(container.querySelector('pre code')?.textContent).toBe(content)
 await fireEvent.click(screen.getByRole('button',{name:'复制原文'}))
 expect(writeText).toHaveBeenCalledWith(content)
})

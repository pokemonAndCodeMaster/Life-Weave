// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { MAX_DIAGRAM_TEXT, renderMermaid } from './mermaidRenderer'
describe('Mermaid host resource policy',()=>{
 it('rejects graph-owned configuration and external resource commands before rendering',async()=>{
  for(const source of ['%%{init: {"securityLevel":"loose"}}%%\nflowchart LR\nA-->B','flowchart LR\nA@{img:"https://remote.test/a.png"}','---\nconfig:\n  theme: dark\n---\nflowchart LR\nA-->B']) {
   await expect(renderMermaid('blocked',source)).rejects.toThrow('配置或外部资源')
  }
 })
 it('explains the supported diagram source limit',async()=>{
  await expect(renderMermaid('too-long','x'.repeat(MAX_DIAGRAM_TEXT+1))).rejects.toThrow('50,000')
 })
})

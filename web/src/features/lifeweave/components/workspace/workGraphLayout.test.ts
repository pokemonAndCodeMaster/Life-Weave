import { describe, expect, it } from 'vitest'
import { layoutWorkGraph } from './workGraphLayout'
import type { WorkStep } from '../../api/workView'

function step(id: string, dependsOn: string[] = []): WorkStep {
  return { id, title: id, description: '', state: 'planned', summary: '', dependsOn, outputIds: [] }
}

describe('共享工作图布局', () => {
  it('第三种自定义人工计划也按依赖连接并行分支和汇合', () => {
    const graph = layoutWorkGraph([
      step('收集材料'), step('整理笔记', ['收集材料']), step('人工核对', ['收集材料']),
      step('提交成果', ['整理笔记', '人工核对']),
    ])
    const positions = new Map(graph.nodes.map(node => [node.step.id, node]))
    expect(graph.edges.map(edge => [edge.from, edge.to])).toEqual([
      ['收集材料', '整理笔记'], ['收集材料', '人工核对'],
      ['整理笔记', '提交成果'], ['人工核对', '提交成果'],
    ])
    expect(positions.get('整理笔记')!.depth).toBe(positions.get('人工核对')!.depth)
    expect(positions.get('提交成果')!.depth).toBe(2)
    expect(graph.edges.every(edge => edge.path.startsWith('M '))).toBe(true)
  })

  it('空计划与缺失依赖安全呈现，不伪造节点', () => {
    expect(layoutWorkGraph([]).nodes).toEqual([])
    expect(layoutWorkGraph([step('实际记录', ['历史已删除'])]).edges).toEqual([])
  })
})

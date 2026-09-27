import type { WorkStep } from '../../api/workView'

export interface PositionedStep { step: WorkStep; x: number; y: number; depth: number }
export interface WorkGraphEdge { from: string; to: string; path: string }
export interface WorkGraphLayout { nodes: PositionedStep[]; edges: WorkGraphEdge[]; width: number; height: number }

const NODE_WIDTH = 248
const COLUMN_GAP = 72
const ROW_HEIGHT = 114
const MARGIN = 24

/** Position any acyclic declared or observed plan without provider-specific branches. */
export function layoutWorkGraph(steps: WorkStep[]): WorkGraphLayout {
  const byId = new Map(steps.map(step => [step.id, step]))
  const depths = new Map<string, number>()
  const visiting = new Set<string>()
  function depth(id: string): number {
    if (depths.has(id)) return depths.get(id)!
    if (visiting.has(id)) return 0 // The server rejects cycles; keep a malformed read usable.
    visiting.add(id)
    const step = byId.get(id)
    const value = step ? Math.max(0, ...step.dependsOn.filter(dep => byId.has(dep)).map(dep => depth(dep) + 1)) : 0
    visiting.delete(id)
    depths.set(id, value)
    return value
  }
  steps.forEach(step => depth(step.id))
  const counts = new Map<number, number>()
  const nodes = steps.map(step => {
    const column = depths.get(step.id) || 0
    const row = counts.get(column) || 0
    counts.set(column, row + 1)
    return { step, depth: column, x: MARGIN + column * (NODE_WIDTH + COLUMN_GAP), y: MARGIN + row * ROW_HEIGHT }
  })
  const positioned = new Map(nodes.map(node => [node.step.id, node]))
  const edges: WorkGraphEdge[] = []
  for (const node of nodes) {
    for (const id of node.step.dependsOn) {
      const source = positioned.get(id)
      if (!source) continue
      const x1 = source.x + NODE_WIDTH
      const x2 = node.x
      const y1 = source.y + 36
      const y2 = node.y + 36
      const bend = Math.max(24, (x2 - x1) / 2)
      edges.push({ from: id, to: node.step.id, path: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}` })
    }
  }
  return {
    nodes, edges,
    width: Math.max(320, MARGIN * 2 + (Math.max(0, ...nodes.map(node => node.depth)) + 1) * NODE_WIDTH + Math.max(0, ...nodes.map(node => node.depth)) * COLUMN_GAP),
    height: Math.max(112, MARGIN * 2 + Math.max(1, ...counts.values()) * ROW_HEIGHT),
  }
}

export const stepStateLabel: Record<WorkStep['state'], string> = {
  planned: '待开始', running: '进行中', waiting: '等待中', succeeded: '已完成', failed: '失败',
  cancelled: '已取消', unobserved: '未观察到执行',
}

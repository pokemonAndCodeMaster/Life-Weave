import type { HomeCardLayout, WorkspaceKind } from '../types'

export const homeCardLabels: Record<HomeCardLayout['key'], string> = {
  attention: '需要我处理', active: '我关注的结果', capture: '随手记录',
  context: '最近的共同理解', environment: '当前工作环境',
}

const keys = Object.keys(homeCardLabels) as HomeCardLayout['key'][]

export function defaultHomeLayout(workspace: WorkspaceKind): HomeCardLayout[] {
  const order: HomeCardLayout['key'][] = workspace === 'team'
    ? ['attention', 'context', 'active', 'capture', 'environment']
    : ['attention', 'active', 'capture', 'context', 'environment']
  return order.map(key => ({ key, column: workspace === 'team' && key === 'context'
    ? 'main' : ['attention', 'active'].includes(key) ? 'main' : 'aside', visible: true }))
}

export function normalizeHomeLayout(value: unknown, workspace: WorkspaceKind): HomeCardLayout[] {
  const defaults = defaultHomeLayout(workspace)
  const raw = value && typeof value === 'object' && 'cards' in value ? (value as { cards?: unknown }).cards : null
  if (!Array.isArray(raw)) return defaults
  const used = new Set<string>()
  const chosen: HomeCardLayout[] = []
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object' || !keys.includes(entry.key) || used.has(entry.key)) continue
    used.add(entry.key)
    chosen.push({ key: entry.key, column: entry.column === 'aside' ? 'aside' : 'main', visible: entry.visible !== false })
  }
  return [...chosen, ...defaults.filter(entry => !used.has(entry.key))]
}

export function moveHomeCard(cards: HomeCardLayout[], key: HomeCardLayout['key'], direction: -1 | 1): HomeCardLayout[] {
  const index = cards.findIndex(entry => entry.key === key)
  const target = index + direction
  if (index < 0 || target < 0 || target >= cards.length) return cards
  const result = [...cards]
  ;[result[index], result[target]] = [result[target]!, result[index]!]
  return result
}

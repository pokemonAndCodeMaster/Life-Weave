import type { WorkItem, WorkspacePreferences } from '../../types'

export type Focus = 'active' | 'all' | 'completed' | 'mine'
export type GroupBy = 'none' | 'topic' | 'domain' | 'state' | 'owner'
export type SortBy = 'updated' | 'created' | 'due' | 'priority' | 'title'
export type DateField = 'created' | 'updated' | 'due'
export type Column = 'update' | 'owner' | 'state' | 'priority' | 'type' | 'tag' | 'domain' | 'topic' | 'due' | 'created' | 'updated' | 'completed'

export interface ItemView extends Omit<WorkspacePreferences, 'group'> {
  focus: Focus
  query: string
  status: string
  priority: string
  type: string
  tag: string
  domain: string
  topic: string
  owner: string
  dateField: DateField
  dateFrom: string
  dateTo: string
  group: GroupBy
  sort: SortBy
  columns: Column[]
}

export interface ItemRow { item: WorkItem; depth: number; hasChildren: boolean; context: boolean; forcedOpen: boolean }
export interface ItemGroup { label: string; rows: ItemRow[]; count: number }

export const columnLabels: Record<Column, string> = {
  update: '最新进展', owner: '负责人', state: '状态', priority: '优先级', type: '类型', tag: '标签', domain: '领域', topic: '专题',
  due: '目标时间', created: '创建时间', updated: '更新时间', completed: '完成时间',
}
export const allColumns = Object.keys(columnLabels) as Column[]
export const defaultColumns: Column[] = ['state', 'priority', 'due', 'updated', 'owner']

export const priorityLabels = ['未设置', '紧急', '高', '普通', '低'] as const
export function priorityValue(item: WorkItem): number {
  const value = Number(item.payload?.priority ?? 0)
  return Number.isInteger(value) && value >= 1 && value <= 4 ? value : 0
}
export function priorityLabel(item: WorkItem): string { return priorityLabels[priorityValue(item)] ?? '未设置' }
export function ownerLabel(owner: string): string { return owner === 'local-user' ? '我' : owner }
export function isMine(item: WorkItem, actor: string): boolean {
  return item.owner === actor || (['我', 'local-user'].includes(actor) && ['我', 'local-user'].includes(item.owner))
}

const typeNames: Record<string, string> = { requirement: '需求', research: '研究', fix: '修复', learning: '学习', review: '复盘', personal: '个人', hobby: '爱好', game: '游戏', other: '工作项' }
export function typeLabel(item: WorkItem): string { return item.itemType ? typeNames[item.itemType] ?? item.itemType : item.kind || '工作项' }
export function itemTags(item: WorkItem): string[] {
  const raw = item.payload?.tags
  const tags = Array.isArray(raw) ? raw.filter((entry): entry is string => typeof entry === 'string' && Boolean(entry.trim())) : []
  const customKind = item.payload?.kind
  if (typeof customKind === 'string' && customKind.trim() && customKind !== typeLabel(item)) tags.unshift(customKind)
  return [...new Set(tags)]
}

export function defaultItemView(): ItemView {
  return { focus: 'active', query: '', status: '', priority: '', type: '', tag: '', domain: '', topic: '', owner: '', dateField: 'updated', dateFrom: '', dateTo: '', group: 'none', sort: 'updated', columns: [...defaultColumns] }
}

export function restoreItemView(saved: unknown): ItemView {
  const defaults = defaultItemView()
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return defaults
  const source = saved as Record<string, unknown>
  const choice = <T extends string>(key: string, options: readonly T[], fallback: T): T => options.includes(source[key] as T) ? source[key] as T : fallback
  const date = (key: string): string => typeof source[key] === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(source[key]) ? source[key] as string : ''
  return {
    focus: choice('focus', ['active', 'all', 'completed', 'mine'], source.kind === 'mine' ? 'mine' : defaults.focus),
    query: typeof source.query === 'string' ? source.query : '',
    status: typeof source.status === 'string' ? source.status : '',
    priority: typeof source.priority === 'string' ? source.priority : '',
    type: typeof source.type === 'string' ? source.type : '',
    tag: typeof source.tag === 'string' ? source.tag : '',
    domain: typeof source.domain === 'string' ? source.domain : '',
    topic: typeof source.topic === 'string' ? source.topic : '',
    owner: typeof source.owner === 'string' ? source.owner : '',
    dateField: choice('dateField', ['created', 'updated', 'due'], defaults.dateField),
    dateFrom: date('dateFrom'),
    dateTo: date('dateTo'),
    group: choice('group', ['none', 'topic', 'domain', 'state', 'owner'], defaults.group),
    sort: choice('sort', ['updated', 'created', 'due', 'priority', 'title'], defaults.sort),
    columns: Array.isArray(source.columns) ? [...new Set(source.columns.filter((value): value is Column => typeof value === 'string' && allColumns.includes(value as Column)))] : [...defaultColumns],
  }
}

export function isCompleted(item: WorkItem): boolean { return ['已完成', 'completed'].includes(item.state) }
function isClosed(item: WorkItem): boolean { return isCompleted(item) || ['已取消', 'cancelled'].includes(item.state) }
export function completedAt(item: WorkItem): string | null {
  const value = item.payload?.completedAt
  return typeof value === 'string' && value.trim() ? value : null
}

function matches(item: WorkItem, view: ItemView, actor: string): boolean {
  if (view.focus === 'active' && isClosed(item)) return false
  if (view.focus === 'completed' && !isCompleted(item)) return false
  if (view.focus === 'mine' && (isClosed(item) || !isMine(item, actor))) return false
  if (view.status && item.state !== view.status) return false
  if (view.priority && String(priorityValue(item)) !== view.priority) return false
  if (view.type && (item.itemType || item.kind) !== view.type) return false
  if (view.tag && !itemTags(item).includes(view.tag)) return false
  if (view.domain && !item.domains.includes(view.domain)) return false
  if (view.topic && !item.topics.includes(view.topic)) return false
  if (view.owner && ownerLabel(item.owner) !== view.owner) return false
  if (view.dateFrom || view.dateTo) {
    const value = (view.dateField === 'created' ? item.createdAt : view.dateField === 'updated' ? item.updatedAt : item.due)?.slice(0, 10)
    if (!value || (view.dateFrom && value < view.dateFrom) || (view.dateTo && value > view.dateTo)) return false
  }
  const query = view.query.trim().toLocaleLowerCase()
  return !query || `${item.id} ${item.title} ${item.update}`.toLocaleLowerCase().includes(query)
}

function groupKeys(item: WorkItem, group: GroupBy): string[] {
  if (group === 'topic') return item.topics.length ? item.topics : ['未关联专题']
  if (group === 'domain') return item.domains.length ? item.domains : ['未关联领域']
  if (group === 'state') return [item.state || '未标状态']
  if (group === 'owner') return [ownerLabel(item.owner) || '未分配负责人']
  return ['全部事项']
}

function sortItems(items: WorkItem[], sort: SortBy): WorkItem[] {
  return items.sort((a, b) => {
    if (sort === 'title') return a.title.localeCompare(b.title, 'zh-CN') || a.id.localeCompare(b.id)
    if (sort === 'priority') return (priorityValue(a) || 5) - (priorityValue(b) || 5) || a.id.localeCompare(b.id)
    const field = sort === 'updated' ? 'updatedAt' : sort === 'created' ? 'createdAt' : 'due'
    const left = a[field] ?? ''
    const right = b[field] ?? ''
    if (sort === 'due') return (left ? 0 : 1) - (right ? 0 : 1) || (left && right ? left.localeCompare(right) : 0) || a.id.localeCompare(b.id)
    return (right ? 1 : 0) - (left ? 1 : 0) || (left && right ? right.localeCompare(left) : 0) || a.id.localeCompare(b.id)
  })
}

export function buildItemGroups(items: WorkItem[], view: ItemView, actor: string, expanded: ReadonlySet<string>): { groups: ItemGroup[]; count: number } {
  const byId = new Map(items.map((item) => [item.id, item]))
  const matched = items.filter((item) => matches(item, view, actor))
  const matchedIds = new Set(matched.map((item) => item.id))
  const buckets = new Map<string, Set<string>>()
  for (const item of matched) for (const key of groupKeys(item, view.group)) {
    const members = buckets.get(key) ?? new Set<string>()
    members.add(item.id)
    const seen = new Set([item.id])
    let parent = item.parentId ? byId.get(item.parentId) : undefined
    while (parent && !seen.has(parent.id)) {
      members.add(parent.id)
      seen.add(parent.id)
      parent = parent.parentId ? byId.get(parent.parentId) : undefined
    }
    buckets.set(key, members)
  }
  const contextPaths = new Set<string>()
  for (const item of matched) {
    const seen = new Set([item.id])
    let parent = item.parentId ? byId.get(item.parentId) : undefined
    let crossedUnmatched = false
    while (parent && !seen.has(parent.id)) {
      if (!matchedIds.has(parent.id)) crossedUnmatched = true
      if (crossedUnmatched) contextPaths.add(parent.id)
      seen.add(parent.id)
      parent = parent.parentId ? byId.get(parent.parentId) : undefined
    }
  }
  const forcePaths = Boolean(view.query.trim() || view.status || view.priority || view.type || view.tag || view.domain || view.topic || view.owner || view.dateFrom || view.dateTo)
  const groups = [...buckets.entries()].sort(([a], [b]) => a.localeCompare(b, 'zh-CN')).map(([label, members]) => {
    const children = new Map<string, WorkItem[]>()
    const roots: WorkItem[] = []
    for (const id of members) {
      const item = byId.get(id)!
      if (item.parentId && item.parentId !== id && members.has(item.parentId)) children.set(item.parentId, [...(children.get(item.parentId) ?? []), item])
      else roots.push(item)
    }
    const reachable = new Set<string>()
    const markReachable = (item: WorkItem) => {
      if (reachable.has(item.id)) return
      reachable.add(item.id)
      for (const child of children.get(item.id) ?? []) markReachable(child)
    }
    for (const root of roots) markReachable(root)
    const rows: ItemRow[] = []
    const visited = new Set<string>()
    const visit = (item: WorkItem, depth: number) => {
      if (visited.has(item.id)) return
      visited.add(item.id)
      const descendants = sortItems(children.get(item.id) ?? [], view.sort)
      const forcedOpen = descendants.length > 0 && (forcePaths || contextPaths.has(item.id))
      rows.push({ item, depth, hasChildren: descendants.length > 0, context: !matchedIds.has(item.id), forcedOpen })
      if (expanded.has(item.id) || forcedOpen) for (const child of descendants) visit(child, depth + 1)
    }
    for (const item of sortItems(roots, view.sort)) visit(item, 0)
    // A malformed parent cycle still leaves each matching item reachable.
    for (const id of members) if (!reachable.has(id)) visit(byId.get(id)!, 0)
    return { label, rows, count: [...members].filter((id) => matchedIds.has(id)).length }
  })
  return { groups, count: matched.length }
}

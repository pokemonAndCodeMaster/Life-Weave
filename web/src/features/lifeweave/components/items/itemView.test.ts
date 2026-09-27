import { describe, expect, it } from 'vitest'
import type { WorkItem } from '../../types'
import { buildItemGroups, completedAt, defaultItemView, itemTags, priorityLabel, restoreItemView, typeLabel } from './itemView'

function item(id: string, overrides: Partial<WorkItem> = {}): WorkItem {
  return {
    id, title: id, parentId: null, state: '进行中', kind: '研究', owner: '我',
    domains: [], topics: [], update: '', payload: {}, createdAt: '2026-09-01', updatedAt: '2026-09-02',
    ...overrides,
  } as WorkItem
}

describe('事项列表视图', () => {
  it('默认关注进行中；状态、类型、领域、专题、负责人独立生效', () => {
    const rows = [
      item('target', { kind: '修复', domains: ['平台'], topics: ['秋季'], owner: '甲', state: '待验收' }),
      item('wrong-type', { kind: '研究', domains: ['平台'], topics: ['秋季'], owner: '甲', state: '待验收' }),
      item('wrong-domain', { kind: '修复', domains: ['其他'], topics: ['秋季'], owner: '甲', state: '待验收' }),
      item('wrong-topic', { kind: '修复', domains: ['平台'], topics: [], owner: '甲', state: '待验收' }),
      item('wrong-owner', { kind: '修复', domains: ['平台'], topics: ['秋季'], owner: '乙', state: '待验收' }),
      item('done', { kind: '修复', domains: ['平台'], topics: ['秋季'], owner: '甲', state: '已完成' }),
    ]
    const view = { ...defaultItemView(), status: '待验收', type: '修复', domain: '平台', topic: '秋季', owner: '甲' }
    const result = buildItemGroups(rows, view, '我', new Set())
    expect(result.count).toBe(1)
    expect(result.groups[0]!.rows.map((row) => row.item.id)).toEqual(['target'])
    expect(buildItemGroups(rows, defaultItemView(), '我', new Set()).count).toBe(5)
  })

  it('跨专题分组允许同一事项出现两次，但总数去重，并保留未分类', () => {
    const rows = [item('shared', { topics: ['甲', '乙'] }), item('unclassified')]
    const result = buildItemGroups(rows, { ...defaultItemView(), group: 'topic' }, '我', new Set())
    expect(result.count).toBe(2)
    expect(result.groups.map((group) => [group.label, group.count])).toEqual([['甲', 1], ['未关联专题', 1], ['乙', 1]])
    expect(result.groups.flatMap((group) => group.rows.map((row) => row.item.id)).filter((id) => id === 'shared')).toHaveLength(2)
  })

  it('未完成子项不会被已完成父路径遮住；普通未完成父子仍可折叠', () => {
    const rows = [item('parent', { title: '上级', state: '已完成' }), item('child', { title: '命中的子项', parentId: 'parent' })]
    const normal = buildItemGroups(rows, defaultItemView(), '我', new Set())
    expect(normal.count).toBe(1)
    expect(normal.groups[0]!.rows.map((row) => row.item.id)).toEqual(['parent', 'child'])
    expect(normal.groups[0]!.rows[0]).toMatchObject({ context: true, forcedOpen: true })
    expect(buildItemGroups(rows, defaultItemView(), '我', new Set(['parent'])).groups[0]!.rows.map((row) => row.item.id)).toEqual(['parent', 'child'])
    const searched = buildItemGroups(rows, { ...defaultItemView(), query: '命中' }, '我', new Set())
    expect(searched.groups[0]!.rows.map((row) => [row.item.id, row.context, row.depth])).toEqual([['parent', true, 0], ['child', false, 1]])
    const ordinary = [item('open-parent'), item('open-child', { parentId: 'open-parent' })]
    expect(buildItemGroups(ordinary, defaultItemView(), '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['open-parent'])
    expect(buildItemGroups(ordinary, defaultItemView(), '我', new Set(['open-parent'])).groups[0]!.rows.map((row) => row.item.id)).toEqual(['open-parent', 'open-child'])
  })

  it('多级路径有未命中的中间父项时，也展开上层路径', () => {
    const rows = [item('root'), item('closed-middle', { parentId: 'root', state: '已完成' }), item('open-leaf', { parentId: 'closed-middle' })]
    const result = buildItemGroups(rows, defaultItemView(), '我', new Set())
    expect(result.groups[0]!.rows.map((row) => [row.item.id, row.forcedOpen])).toEqual([['root', true], ['closed-middle', true], ['open-leaf', false]])
  })

  it('恢复保存的视图并忽略损坏字段；完成时间只读取真实 payload', () => {
    const restored = restoreItemView({ focus: 'mine', group: 'state', columns: ['owner', 'completed', 'invalid', 'owner'], sort: 'due' })
    expect(restored).toMatchObject({ focus: 'mine', group: 'state', sort: 'due', columns: ['owner', 'completed'] })
    expect(restoreItemView({ focus: 'unknown', columns: 'bad' })).toMatchObject({ focus: 'active', columns: defaultItemView().columns })
    expect(restoreItemView({ kind: 'mine' }).focus).toBe('mine')
    expect(restoreItemView({ dateFrom: 'broken' }).dateFrom).toBe('')
    expect(completedAt(item('done', { state: '已完成' }))).toBeNull()
    expect(completedAt(item('done', { payload: { completedAt: '2026-09-27T10:00:00Z' } }))).toBe('2026-09-27T10:00:00Z')
  })

  it('类型来自 itemType，标签仅来自真实 payload 字段，领域仍独立', () => {
    const row = item('labeled', { itemType: 'research', kind: '方法探索', domains: ['知识'], payload: { kind: '方法探索', tags: ['紧急', '紧急'] } })
    expect(typeLabel(row)).toBe('研究')
    expect(itemTags(row)).toEqual(['方法探索', '紧急'])
    expect(buildItemGroups([row], { ...defaultItemView(), type: 'research', domain: '知识' }, '我', new Set()).count).toBe(1)
    expect(buildItemGroups([row], { ...defaultItemView(), type: '方法探索' }, '我', new Set()).count).toBe(0)
    expect(buildItemGroups([row], { ...defaultItemView(), tag: '紧急' }, '我', new Set()).count).toBe(1)
    expect(buildItemGroups([row], { ...defaultItemView(), tag: '不存在' }, '我', new Set()).count).toBe(0)
  })

  it('可按创建、更新或目标日期筛选，空日期不误命中', () => {
    const rows = [item('early', { createdAt: '2026-09-01T08:00:00Z', updatedAt: '2026-09-20T08:00:00Z', due: null }), item('late', { createdAt: '2026-09-18T08:00:00Z', updatedAt: undefined, due: '2026-09-30' })]
    const base = { ...defaultItemView(), dateFrom: '2026-09-15', dateTo: '2026-09-25' }
    expect(buildItemGroups(rows, { ...base, dateField: 'created' }, '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['late'])
    expect(buildItemGroups(rows, { ...base, dateField: 'updated' }, '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['early'])
    expect(buildItemGroups(rows, { ...base, dateField: 'due' }, '我', new Set()).count).toBe(0)
    expect(restoreItemView({ dateField: 'due', dateFrom: '2026-09-01' })).toMatchObject({ dateField: 'due', dateFrom: '2026-09-01' })
  })

  it('优先级筛选、排序与近期目标时间排序使用真实计划字段', () => {
    const rows = [item('low', { due: '2026-09-01', payload: { priority: 4 } }), item('urgent', { due: '2026-10-01', payload: { priority: 1 } }), item('unset', { due: null })]
    expect(priorityLabel(rows[1]!)).toBe('紧急')
    expect(buildItemGroups(rows, { ...defaultItemView(), priority: '1' }, '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['urgent'])
    expect(buildItemGroups(rows, { ...defaultItemView(), sort: 'priority' }, '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['urgent', 'low', 'unset'])
    expect(buildItemGroups(rows, { ...defaultItemView(), sort: 'due' }, '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['low', 'urgent', 'unset'])
  })

  it('本机 actor 的“我”和 local-user 两种标记指向同一负责人', () => {
    const rows = [item('local', { owner: 'local-user' }), item('old', { owner: '我' }), item('named', { owner: '同事' })]
    expect(buildItemGroups(rows, { ...defaultItemView(), focus: 'mine' }, '我', new Set()).groups[0]!.rows.map((row) => row.item.id)).toEqual(['local', 'old'])
    expect(buildItemGroups([item('old', { owner: '我' })], { ...defaultItemView(), focus: 'mine' }, 'local-user', new Set()).count).toBe(1)
    expect(buildItemGroups(rows, { ...defaultItemView(), owner: '我' }, '我', new Set()).count).toBe(2)
    expect(buildItemGroups(rows, { ...defaultItemView(), group: 'owner' }, '我', new Set()).groups.find((group) => group.label === '我')?.count).toBe(2)
  })
})

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { WorkItem, WorkspacePreferences } from '../../types'
import ItemList from './ItemList.vue'

const item = {
  id: 'full-item-identifier-42', title: '待处理事项', parentId: null, state: '进行中',
  kind: '研究', owner: '我', domains: [], topics: [], update: '处理中', payload: {},
} as unknown as WorkItem
const routerStub = { template: '<a><slot /></a>' }
afterEach(cleanup)

describe('事项列表交互', () => {
  it('恢复工作空间保存的范围，并在保存失败时保留当前调整', async () => {
    const saveView = vi.fn().mockRejectedValue(new Error('network'))
    render(ItemList, {
      props: { items: [item], actor: '我', workspace: 'personal', saved: { focus: 'completed', columns: ['owner'] } as WorkspacePreferences, saveView },
      global: { stubs: { RouterLink: routerStub } },
    })
    expect(screen.getByRole('button', { name: '已完成' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText(/没有符合条件的事项/)).toBeTruthy()
    await fireEvent.click(screen.getByRole('button', { name: '待我处理' }))
    expect(screen.getByText('待处理事项')).toBeTruthy()
    expect(screen.getByText('full-item-identifier-42')).toBeTruthy()
    await fireEvent.click(screen.getByRole('button', { name: '保存视图' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('保存失败'))
    expect(saveView).toHaveBeenCalledWith(expect.objectContaining({ focus: 'mine', columns: ['owner'] }))
    expect(screen.getByText('待处理事项')).toBeTruthy()
  })

  it('切换工作空间时恢复对应的独立视图', async () => {
    const saveView = vi.fn().mockResolvedValue(undefined)
    const { rerender } = render(ItemList, {
      props: { items: [item], actor: '我', workspace: 'personal', saved: { focus: 'completed' } as WorkspacePreferences, saveView },
      global: { stubs: { RouterLink: routerStub } },
    })
    expect(screen.getByRole('button', { name: '已完成' }).getAttribute('aria-pressed')).toBe('true')
    await rerender({ workspace: 'team', saved: { focus: 'all', status: '进行中' } as WorkspacePreferences })
    expect(screen.getByRole('button', { name: '全部' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('待处理事项')).toBeTruthy()
    expect(screen.getByRole('button', { name: '筛选（1）' }).getAttribute('aria-expanded')).toBe('false')
    expect(screen.getByText(/已启用 1 项筛选：状态：进行中/)).toBeTruthy()
  })

  it('低频筛选默认收起，保存时明确列出仍然生效的筛选', async () => {
    const saveView = vi.fn().mockResolvedValue(undefined)
    render(ItemList, {
      props: { items: [item], actor: '我', workspace: 'personal', saved: {}, saveView },
      global: { stubs: { RouterLink: routerStub } },
    })
    expect(screen.getByRole('button', { name: '未完成' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.queryByRole('combobox', { name: '筛选优先级' })).toBeNull()
    await fireEvent.update(screen.getByRole('searchbox', { name: '搜索事项' }), '待处理')
    await fireEvent.update(screen.getByRole('combobox', { name: '筛选状态' }), '进行中')
    await fireEvent.click(screen.getByRole('button', { name: '筛选（2）' }))
    await fireEvent.update(screen.getByRole('combobox', { name: '筛选优先级' }), '0')
    expect(screen.getByText(/已启用 3 项筛选：搜索：待处理 · 状态：进行中 · 优先级：未设置/)).toBeTruthy()
    await fireEvent.click(screen.getByRole('button', { name: '筛选（3）' }))
    expect(screen.queryByRole('combobox', { name: '筛选优先级' })).toBeNull()
    expect(screen.getByText('待处理事项')).toBeTruthy()
    await fireEvent.click(screen.getByRole('button', { name: '保存视图' }))
    await waitFor(() => expect(screen.getByText('视图已保存，包含 3 项筛选。')).toBeTruthy())
    expect(saveView).toHaveBeenCalledWith(expect.objectContaining({ query: '待处理', status: '进行中', priority: '0' }))
  })

  it('强制展开的父路径标明原因，普通父子仍可手动展开', async () => {
    const parent = { ...item, id: 'closed-parent', title: '已完成父项', state: '已完成' }
    const child = { ...item, id: 'open-child', title: '未完成子项', parentId: parent.id }
    render(ItemList, {
      props: { items: [parent, child], actor: '我', workspace: 'personal', saved: {}, saveView: vi.fn() },
      global: { stubs: { RouterLink: routerStub } },
    })
    expect(screen.getByText('未完成子项')).toBeTruthy()
    const forced = screen.getByRole('button', { name: '筛选中保留子项' }) as HTMLButtonElement
    expect(forced.disabled).toBe(true)
    expect(forced.title).toBe('筛选中保留子项')
    expect(screen.queryByRole('button', { name: '收起 已完成父项' })).toBeNull()
  })
})

// @vitest-environment jsdom
import { defineComponent, shallowRef } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useItemWorkView } from './useItemWorkView'
import * as api from '../api/workView'
import type { ItemWorkView } from '../api/workView'

vi.mock('../api/workView', () => ({ getWorkView: vi.fn(), saveWorkPlan: vi.fn() }))
const first: ItemWorkView = {
  itemId: 'item-1', itemVersion: 1, current: { state: 'active', label: '进行中', summary: '第一版' },
  plan: { id: 'plan-1', title: '人工计划', provider: 'manual', source: 'declared', version: 1, editable: true, nodes: [] },
  outputs: [], warnings: [],
}
const second: ItemWorkView = { ...first, itemVersion: 2, current: { ...first.current, summary: '第二版' } }
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
function harness() {
  const component = defineComponent({
    setup() {
      const workspace = shallowRef<'personal' | 'team'>('personal')
      const itemId = shallowRef('item-1')
      return { workspace, itemId, work: useItemWorkView(workspace, itemId) }
    },
    template: '<div />',
  })
  return mount(component)
}
beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.getWorkView).mockResolvedValue(first); vi.mocked(api.saveWorkPlan).mockResolvedValue(second) })

describe('事项视图保存与切换', () => {
  it('保存后迟到的旧 GET 不会覆盖新版本', async () => {
    const view = harness()
    await flushPromises()
    const stale = deferred<ItemWorkView>()
    vi.mocked(api.getWorkView).mockReturnValueOnce(stale.promise)
    const loading = view.vm.work.refresh()
    await view.vm.work.save({ version: 1, title: '人工计划', provider: 'manual', nodes: [] })
    expect(view.vm.work.view.value?.itemVersion).toBe(2)
    stale.resolve(first)
    await loading
    expect(view.vm.work.view.value?.itemVersion).toBe(2)
    view.unmount()
  })

  it('旧草稿版本不被轮询所得新版本悄悄抬升', async () => {
    const view = harness()
    await flushPromises()
    vi.mocked(api.getWorkView).mockResolvedValueOnce(second)
    await view.vm.work.refresh()
    const saved = await view.vm.work.save({ version: 1, title: '旧草稿', provider: 'manual', nodes: [] })
    expect(saved).toBe(false)
    expect(view.vm.work.conflict.value).toBe(true)
    expect(api.saveWorkPlan).not.toHaveBeenCalled()
    view.unmount()
  })

  it('切换事项后旧请求不能覆盖新事项', async () => {
    const pending = deferred<ItemWorkView>()
    vi.mocked(api.getWorkView).mockReturnValueOnce(pending.promise).mockResolvedValueOnce({ ...second, itemId: 'item-2' })
    const view = harness()
    view.vm.itemId = 'item-2'
    await flushPromises()
    pending.resolve(first)
    await flushPromises()
    expect(view.vm.work.view.value?.itemId).toBe('item-2')
    view.unmount()
  })
})

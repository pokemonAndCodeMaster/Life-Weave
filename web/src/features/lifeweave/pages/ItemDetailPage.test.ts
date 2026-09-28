import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/vue'
import { flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
vi.mock('@/shared/api/http', () => ({ http: { get, post, put, request: vi.fn() } }))

import LifeWeaveModalHost from '../components/LifeWeaveModalHost.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import ItemDetailPage from './ItemDetailPage.vue'

const Harness = defineComponent({
  components: { ItemDetailPage, LifeWeaveModalHost },
  template: '<ItemDetailPage /><LifeWeaveModalHost />',
})

function fixture(id: string, parentId?: string, established = true) {
  return {
    id, title: parentId ? '解释分配缺口' : '改善验收体验', itemType: 'research', status: 'in_progress',
    payload: { parentId, goal: parentId ? '说明每个未分配原因' : '让验收人员看懂结果', scope: '只解释，不改分配规则' },
    context: established ? {
      id: 'context-' + id, currentVersionId: 'version-' + id,
      revisionNo: parentId ? 1 : 7,
      content: { goal: parentId ? '说明每个未分配原因' : '让验收人员看懂结果', scope: '只解释，不改分配规则' },
    } : null,
  }
}

async function openPage(id = 'child-1', parentEstablished = true) {
  const parent = fixture('parent-1', undefined, parentEstablished)
  const child = fixture('child-1', 'parent-1')
  const items = [parent, child]
  get.mockImplementation(async (url: string) => {
    if (url.endsWith('/agent-choices')) return { data: { itemId: id, recommendedAgentId: 'general', items: [{ id:'general', name:'通用 Agent', description:'处理事项', version:1, capability:'general', pluginId:'lifeweave.general', engine:'codex', enabled:true, available:true, modes:['managed_run'] }], engines:[{id:'codex',label:'Codex',available:true}], environment:{} } }
    if (url.endsWith('/input-recommendations')) return { data: { methods:[], documents:[], suggested:{methodId:null,knowledgeRefs:[]}, unavailable:[], boundary:'' } }
    if (url.endsWith('/capabilities')) return { data: { items:[] } }
    if (url.endsWith('/research-output')) return { data: { current: null, versions: [] } }
    if (url.endsWith('/work-view')) {
      const workItemId = url.split('/').at(-2)
      return { data: {
        itemId: workItemId, itemVersion: 1,
        current: { state: 'in_progress', label: '进行中', summary: '等待整理照片', updatedAt: '2026-09-27T00:00:00Z' },
        plan: { id: 'plan-1', title: '整理周末照片', provider: 'manual', source: 'declared', version: 1, editable: true, nodes: [
          { id: 'select', title: '挑选照片', description: '选出要留下的照片', summary: '选出十张', state: 'succeeded', dependsOn: [], outputIds: [] },
          { id: 'group', title: '给照片分组', description: '按地点分组', summary: '已分好三组', state: 'planned', dependsOn: ['select'], outputIds: [] },
        ] }, outputs: [], warnings: [],
      } }
    }
    if (url.endsWith('/state')) return { data: { items, ideas: [], topics: [], domains: [], resources: [], relations: [] } }
    if (url.endsWith('/runs') || url.endsWith('/machines')) return { data: { items: [] } }
    return { data: items.find((entry) => url.endsWith('/items/' + entry.id)) }
  })
  post.mockResolvedValue({ data: { kind:'managed_run', id:'run-1', itemId:id, agentId:'general', status:'queued' } })
  const workspace = useLifeWeaveWorkspace()
  await workspace.load('personal')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/lifeweave/:workspace/items/:itemId/:tab', component: Harness }, { path: '/lifeweave/:workspace/conversation', component: { template: '<div />' } }, { path: '/lifeweave/:workspace/agent-executions/:kind/:executionId', component: { template: '<div />' } }],
  })
  await router.push('/lifeweave/personal/items/' + id + '/overview')
  await router.isReady()
  render(Harness, { global: { plugins: [router] } })
  return router
}

beforeEach(() => {
  get.mockReset(); post.mockReset(); put.mockReset()
  const workspace = useLifeWeaveWorkspace()
  workspace.closeModal()
  workspace.itemDetails.value = {}
  workspace.state.value = null
  workspace.runs.value = []
})
afterEach(cleanup)

describe('事项页委托', () => {
  it('默认只呈现当前局面和通用工作图，节点详情需要点击才展开', async () => {
    await openPage()
    await waitFor(() => expect(screen.getByRole('group', { name: '工作步骤依赖图' })).toBeTruthy())
    expect(screen.queryByRole('dialog', { name: '给照片分组' })).toBeNull()
    expect(screen.getByText('等待整理照片')).toBeTruthy()
    expect(screen.getByText('已声明计划 · 人工')).toBeTruthy()
    await fireEvent.click(screen.getAllByRole('button', { name: /给照片分组/ })[0]!)
    await waitFor(() => expect(screen.getByText('按地点分组')).toBeTruthy())
    expect(screen.getByRole('dialog', { name: '给照片分组' })).toBeTruthy()
    await fireEvent.click(screen.getByRole('button', { name: '关闭步骤详情' }))
    await waitFor(() => expect(screen.queryByText('按地点分组')).toBeNull())
  })
  it('节点链接恢复、依赖切换、编辑定位与讨论携带同一步引用', async () => {
    const router = await openPage()
    await router.push({ query: { step: 'group' } })
    const detail = await screen.findByRole('dialog', { name: '给照片分组' })
    expect(within(detail).getByText('按地点分组')).toBeTruthy()
    await fireEvent.click(within(detail).getByRole('button', { name: /挑选照片/ }))
    await waitFor(() => expect(router.currentRoute.value.query.step).toBe('select'))
    expect(within(detail).getByRole('heading', { name: '挑选照片' })).toBeTruthy()
    await fireEvent.click(within(detail).getByRole('button', { name: '讨论这一步' }))
    await waitFor(() => expect(router.currentRoute.value.query.mode).toBe('discuss'))
    expect(router.currentRoute.value.query.itemId).toBe('child-1')
    const quote = JSON.parse(sessionStorage.getItem('lifeweave:quote:personal:child-1')!)
    expect(quote.text).toContain('选出要留下的照片')
    expect(quote.anchor).toBe('步骤：挑选照片 [select]')
    expect(post).not.toHaveBeenCalled()
    expect(put).not.toHaveBeenCalled()
  })
  it('从深链接进入步骤可关闭，并保持概览位置用于编辑', async () => {
    const router = await openPage()
    await router.push({ query: { step: 'select' } })
    const detail = await screen.findByRole('dialog', { name: '挑选照片' })
    await fireEvent.click(within(detail).getByRole('button', { name: '编辑本步与成果关联' }))
    await waitFor(() => expect(router.currentRoute.value.query.step).toBeUndefined())
    await waitFor(() => expect((document.activeElement as HTMLInputElement)?.value).toBe('挑选照片'))
  })
  it('冲突后的刷新失败不会丢失未保存步骤草稿', async () => {
    await openPage()
    await waitFor(() => expect(screen.getByRole('button', { name: '编辑步骤' })).toBeTruthy())
    await fireEvent.click(screen.getByRole('button', { name: '编辑步骤' }))
    const description = screen.getAllByRole('textbox', { name: '这一步要做什么' })[0]! as HTMLTextAreaElement
    await fireEvent.update(description, '本次未保存的改动')
    await fireEvent.update(screen.getByRole('textbox', { name: '本次调整原因' }), '补充交付说明')
    put.mockRejectedValueOnce({ response: { status: 409, data: { message: '冲突' } } })
    await fireEvent.click(screen.getByRole('button', { name: '保存步骤计划' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '刷新后重新编辑' })).toBeTruthy())
    const original = get.getMockImplementation()!
    get.mockImplementation((url: string) => url.endsWith('/work-view') ? Promise.reject(new Error('暂时无法读取')) : original(url))
    await fireEvent.click(screen.getByRole('button', { name: '刷新后重新编辑' }))
    await flushPromises()
    await waitFor(() => expect((screen.getAllByRole('textbox', { name: '这一步要做什么' })[0]! as HTMLTextAreaElement).value).toBe('本次未保存的改动'))
  })
  it('子事项的共同触发保留子标识、目标和父背景', async () => {
    await openPage()
    await waitFor(() => expect(screen.getByRole('button', { name: '委托 Agent' })).toBeTruthy())
    await fireEvent.click(screen.getByRole('button', { name: '委托 Agent' }))
    expect(screen.getByText(/本次事项：child-1 · 解释分配缺口/)).toBeTruthy()
    expect(screen.getByText(/共同背景来自 parent-1 · v7/)).toBeTruthy()
    await waitFor(() => expect(screen.getByRole('textbox', { name: '本次任务' })).toBeTruthy())
    await fireEvent.update(screen.getByRole('textbox', { name: '本次任务' }), '检查缺口解释是否完整')
    await fireEvent.click(screen.getByRole('button', { name: '开始委托' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/lifeweave/personal/items/child-1/agent-dispatch', expect.objectContaining({ agentId:'general', mode:'managed_run', instruction:'检查缺口解释是否完整' })))
  })

  it('主事项的共同触发仍绑定自己', async () => {
    await openPage('parent-1')
    await waitFor(() => expect(screen.getByRole('button', { name: '委托 Agent' })).toBeTruthy())
    await fireEvent.click(screen.getByRole('button', { name: '委托 Agent' }))
    expect(screen.getByText(/本次事项：parent-1 · 改善验收体验/)).toBeTruthy()
    expect(screen.getByText(/共同背景 v7/)).toBeTruthy()
    await waitFor(() => expect(screen.getByRole('button', { name: '开始委托' })).toBeTruthy())
    await fireEvent.click(screen.getByRole('button', { name: '开始委托' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/lifeweave/personal/items/parent-1/agent-dispatch', expect.objectContaining({ agentId:'general' })))
  })

  it('父共同背景缺失时，仍在父事项建立背景，不误发子事项运行', async () => {
    await openPage('child-1', false)
    await waitFor(() => expect(screen.getByRole('button', { name: '先建立上下文' })).toBeTruthy())
    await fireEvent.click(screen.getByRole('button', { name: '先建立上下文' }))
    expect(screen.getByRole('dialog', { name: '建立初始共享上下文' })).toBeTruthy()
    expect((screen.getByRole('textbox', { name: '目标' }) as HTMLTextAreaElement).value).toBe('让验收人员看懂结果')
    expect(post).not.toHaveBeenCalled()
  })
})

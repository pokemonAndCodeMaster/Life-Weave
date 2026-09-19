import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ConversationTurn } from '../../api/conversations'
const api = vi.hoisted(() => ({ listConversations: vi.fn(), getConversation: vi.fn(), createConversation: vi.fn(), sendConversationTurn: vi.fn(), cancelConversationTurn: vi.fn(), getRun: vi.fn(), runAction: vi.fn(), replace: vi.fn(), push: vi.fn() }))
vi.mock('../../api/conversations', () => api)
vi.mock('../../api/lifeweave', () => ({ ...api, apiError: (error: unknown) => ({ message: String(error), status: 0 }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: api.replace, push: api.push }) }))
import ConversationWorkspace from './ConversationWorkspace.vue'
import ConversationRunReceipt from './ConversationRunReceipt.vue'

const failedTurn: ConversationTurn = {
  id: 'failed-turn', body: '请围绕这段补充来源', mode: 'execute', status: 'failed', reply: '', receipts: [],
  itemId: 'derived-item', runId: 'new-attempt', error: '处理失败', createdAt: '', updatedAt: '', sources: [],
  inputContext: { itemId: 'original-item', runId: 'original-run', anchor: '报告第三段：数据来源' },
}
const wrappers: Array<ReturnType<typeof mount>> = []
const stubs = { RouterLink: true, PersonalModelEditor: true, ConversationRunReceipt: true }
function workspace() {
  const wrapper = mount(ConversationWorkspace, { props: { workspace: 'personal', conversationId: 'conversation-1', itemId: 'current-item' }, global: { stubs } })
  wrappers.push(wrapper); return wrapper
}
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear()
  api.listConversations.mockResolvedValue({ items: [], total: 0 })
  api.getConversation.mockResolvedValue({ id: 'conversation-1', title: '讨论', itemId: 'current-item', turns: [failedTurn] })
  api.sendConversationTurn.mockResolvedValue({ ...failedTurn, id: 'retry-turn', status: 'queued' })
})
afterEach(() => { wrappers.forEach(wrapper => wrapper.unmount()); wrappers.length = 0 })

describe('失败消息接续与成果阅读', () => {
  it('失败原文带回后，发送保留原始事项、运行和引用定位', async () => {
    const wrapper = workspace(); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '将原文带回输入框')!.trigger('click')
    expect(wrapper.get('textarea').element.value).toBe(failedTurn.body)
    expect(wrapper.get('textarea').attributes('maxlength')).toBe('20000')
    expect(wrapper.text()).toContain(failedTurn.inputContext!.anchor)
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(api.sendConversationTurn).toHaveBeenCalledWith('personal', 'conversation-1', expect.objectContaining({
      body: failedTurn.body, mode: 'execute', ...failedTurn.inputContext,
    }))
  })
  it('失败原文带回后刷新，仍保留原引用上下文', async () => {
    const first = workspace(); await flushPromises()
    await first.findAll('button').find(button => button.text() === '将原文带回输入框')!.trigger('click')
    first.unmount()
    const recovered = workspace(); await flushPromises()
    expect(recovered.text()).toContain(failedTurn.inputContext!.anchor)
    await recovered.get('form').trigger('submit'); await flushPromises()
    expect(api.sendConversationTurn.mock.lastCall?.[2]).toEqual(expect.objectContaining({ ...failedTurn.inputContext, mode: 'execute' }))
  })
  it('成功回执默认展示可读成果，原始运行正文不重复，提示可查看历史版本', async () => {
    api.getRun.mockResolvedValue({ id: 'historical-run', itemId: 'item-1', state: 'succeeded', result: '# 原始长报告\n不应重复显示', error: null })
    const wrapper = mount(ConversationRunReceipt, { props: { workspace: 'personal', runId: 'historical-run' }, global: { stubs: {
      RouterLink: true, ResearchOutputPanel: { template: '<article><h2>当前成果</h2><p>可直接阅读的正文</p><select aria-label="成果版本"><option>当前成果</option><option>历史成果</option></select></article>' },
    } } })
    wrappers.push(wrapper); await flushPromises()
    expect(wrapper.text()).toContain('可直接阅读的正文')
    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('# 原始长报告')
    expect(wrapper.text()).toContain('可能包含后续运行的修订')
    expect(wrapper.find('select').exists()).toBe(true)
  })
})

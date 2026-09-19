import { defineComponent, shallowRef } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Conversation, ConversationTurn } from '../api/conversations'
import type { WorkspaceKind } from '../types'
const api = vi.hoisted(() => ({ listConversations: vi.fn(), getConversation: vi.fn(), createConversation: vi.fn(), sendConversationTurn: vi.fn(), cancelConversationTurn: vi.fn() }))
vi.mock('../api/conversations', () => api)
import { useConversation } from './useConversation'

const conversation: Conversation = { id: 'conversation-1', title: '理解研究方法', itemId: null, createdAt: '', updatedAt: '', turns: [] }
const turn: ConversationTurn = { id: 'turn-1', body: '请解释研究方法', mode: 'discuss', status: 'queued', reply: '', receipts: [], itemId: null, runId: null, error: null, createdAt: '', updatedAt: '', sources: [] }
const wrappers: Array<ReturnType<typeof mount>> = []
function harness(id = '') {
  const workspace = shallowRef<WorkspaceKind>('personal'); const selected = vi.fn()
  let state!: ReturnType<typeof useConversation>
  const wrapper = mount(defineComponent({ setup() { state = useConversation({ workspace: () => workspace.value, conversationId: () => id, itemId: () => '', selected }); return () => null } }))
  wrappers.push(wrapper)
  return { state, workspace, selected, wrapper }
}
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear()
  api.listConversations.mockResolvedValue({ items: [], total: 0 })
  api.getConversation.mockResolvedValue(conversation)
  api.createConversation.mockResolvedValue(conversation)
  api.sendConversationTurn.mockResolvedValue(turn)
})
afterEach(() => { wrappers.forEach(wrapper => wrapper.unmount()); wrappers.length = 0 })

describe('对话持久接续与请求边界', () => {
  it('请求结果不确定时保留原文和同一请求标识，重试不会重新创建会话', async () => {
    const { state } = harness(); await flushPromises()
    api.sendConversationTurn.mockRejectedValueOnce(new Error('network disconnected'))
    expect(await state.submit({ body: turn.body, mode: 'discuss' })).toBe(false)
    const original = api.sendConversationTurn.mock.calls[0]![2]
    expect(state.pending.value?.input.body).toBe(turn.body)
    expect(await state.submit({ body: '不会替换待核对原请求', mode: 'execute' })).toBe(true)
    expect(api.sendConversationTurn.mock.calls[1]![2]).toEqual(original)
    expect(api.createConversation).toHaveBeenCalledTimes(1)
    expect(state.pending.value).toBeNull()
  })
  it('刷新后恢复结果未确认的请求，沿同一会话和请求标识核对', async () => {
    const first = harness(); await flushPromises()
    api.sendConversationTurn.mockRejectedValueOnce(new Error('timeout'))
    await first.state.submit({ body: turn.body, mode: 'discuss' })
    const requestId = first.state.pending.value?.input.requestId
    first.wrapper.unmount()
    const next = harness(); await flushPromises()
    expect(next.state.pending.value?.input.requestId).toBe(requestId)
    expect(next.state.current.value?.id).toBe(conversation.id)
    await next.state.submit({ body: turn.body, mode: 'discuss' })
    expect(api.createConversation).toHaveBeenCalledTimes(1)
    expect(api.sendConversationTurn.mock.lastCall?.[2].requestId).toBe(requestId)
  })
  it('从地址恢复历史并读取排队状态，无需重新发送', async () => {
    api.getConversation.mockResolvedValue({ ...conversation, turns: [turn] })
    const { state } = harness(conversation.id); await flushPromises()
    expect(state.current.value?.turns[0]?.body).toBe(turn.body)
    expect(state.busy.value).toBe(true)
    expect(api.sendConversationTurn).not.toHaveBeenCalled()
  })
  it('切换空间后忽略旧请求的迟到响应', async () => {
    let resolveOld!: (value: { items: typeof conversation[]; total: number }) => void
    api.listConversations.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
    api.listConversations.mockResolvedValue({ items: [{ ...conversation, id: 'team-conversation' }], total: 1 })
    const { state, workspace } = harness()
    workspace.value = 'team'; await flushPromises()
    resolveOld({ items: [conversation], total: 1 }); await flushPromises()
    expect(state.history.value.map(row => row.id)).toEqual(['team-conversation'])
  })
})

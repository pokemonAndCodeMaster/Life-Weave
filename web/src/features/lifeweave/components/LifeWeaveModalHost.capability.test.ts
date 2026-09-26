import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/shared/api/http', () => ({ http: { get, post, request: vi.fn() } }))

import LifeWeaveModalHost from './LifeWeaveModalHost.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'

async function show(improvement?: Record<string, unknown>) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: LifeWeaveModalHost }] })
  await router.push('/')
  await router.isReady()
  render(LifeWeaveModalHost, { global: { plugins: [router] } })
  useLifeWeaveWorkspace().openModal('capability-create', improvement ? { improvement } : {})
  return within(await screen.findByRole('dialog', { name: '准备可试验能力候选' }))
}

beforeEach(() => {
  get.mockReset(); post.mockReset()
  const workspace = useLifeWeaveWorkspace()
  workspace.closeModal()
  workspace.activeWorkspace.value = 'personal'
  post.mockResolvedValue({ data: { id: 'cap-new' } })
  get.mockImplementation(async (url: string) => ({ data: url.endsWith('/cap-old')
    ? { id: 'cap-old', target: 'agent' }
    : url.endsWith('/evaluations')
      ? { items: [], total: 0, lineage: [] }
      : url.endsWith('/runs')
        ? { items: [], total: 0 }
        : { id: 'cap-new', target: 'harness', title: '流程改进', status: 'candidate', verifications: [] } }))
})
afterEach(cleanup)

describe('能力候选创建入口', () => {
  it('allows a new Agent candidate without an improvement source', async () => {
    const dialog = await show()
    expect((dialog.getByLabelText('能力类型') as HTMLSelectElement).value).toBe('agent')
    await fireEvent.update(dialog.getByLabelText('候选名称'), '资料查证助手')
    await fireEvent.update(dialog.getByLabelText('真实候选内容'), '只用所选来源回答，并列出无法核实的部分。')
    await fireEvent.update(dialog.getByLabelText('期望行为'), '每个结论附来源')
    await fireEvent.update(dialog.getByLabelText('验证计划'), '以真实事项和已接受证据评测')
    await fireEvent.click(dialog.getByRole('button', { name: '建立可试验候选' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/lifeweave/personal/capabilities', expect.objectContaining({
      title: '资料查证助手', target: 'agent', sourceEntityId: undefined, predecessorCandidateId: undefined,
    })))
  })

  it('keeps a cross-type improvement source without inheriting the old Agent candidate', async () => {
    const dialog = await show({ id: 'improvement-one', kind: 'skill', title: '改进方法', body: '旧 Agent 缺少来源',
      desiredBehavior: '解释依据', validationPlan: '沿原标准复测', targetRef: 'cap-old' })
    const kind = dialog.getByLabelText('能力类型') as HTMLSelectElement
    const content = dialog.getByLabelText('真实候选内容') as HTMLTextAreaElement
    expect(kind.value).toBe('skill')
    expect(content.value).toContain('name: candidate-skill')
    await fireEvent.update(kind, 'harness')
    expect(content.value).toBe('旧 Agent 缺少来源')
    await fireEvent.click(dialog.getByRole('button', { name: '建立可试验候选' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/lifeweave/personal/capabilities', expect.objectContaining({
      target: 'harness', content: '旧 Agent 缺少来源', sourceEntityId: 'improvement-one',
      predecessorCandidateId: undefined,
    })))
  })

  it('inherits a same-type predecessor while preserving edited candidate content', async () => {
    const dialog = await show({ id: 'improvement-two', kind: 'agent', title: '改进助手', body: '旧 Agent 缺少来源',
      desiredBehavior: '解释依据', validationPlan: '沿原标准复测', targetRef: 'cap-old' })
    await fireEvent.update(dialog.getByLabelText('真实候选内容'), '新版 Agent 应列出所用来源与未知项。')
    await fireEvent.click(dialog.getByRole('button', { name: '建立可试验候选' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/lifeweave/personal/capabilities', expect.objectContaining({
      target: 'agent', content: '新版 Agent 应列出所用来源与未知项。',
      sourceEntityId: 'improvement-two', predecessorCandidateId: 'cap-old',
    })))
  })
})

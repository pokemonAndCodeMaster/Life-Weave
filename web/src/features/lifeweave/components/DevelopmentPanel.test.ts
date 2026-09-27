// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DevelopmentPanel from './DevelopmentPanel.vue'
import { createDevelopment, developmentChoices, listDevelopment } from '../api/development'
import { getWorkView, type ItemWorkView, type WorkStep } from '../api/workView'

vi.mock('../api/lifeweave', () => ({ apiError: (error: unknown) => ({ message: String(error) }), getRun: vi.fn(), getRunEvents: vi.fn() }))
vi.mock('../api/development', () => ({ createDevelopment: vi.fn(), developmentChoices: vi.fn(), listDevelopment: vi.fn(), getDevelopmentDelivery: vi.fn(), getDevelopmentDiff: vi.fn(), cancelDevelopment: vi.fn() }))
vi.mock('../api/workView', () => ({ getWorkView: vi.fn() }))
vi.mock('../api/plugins', () => ({ pluginProcess: vi.fn(async () => null) }))

const step = (id: string): WorkStep => ({
  id, title: `步骤 ${id}`, description: '', summary: '', state: 'planned', dependsOn: [], outputIds: [],
  expectedOutputs: [{ id: 'plan', title: `方案 ${id}`, kind: 'plan', required: true }], acceptance: '审阅通过',
})
const workView: ItemWorkView = {
  itemId: 'item-1', itemVersion: 8, current: { state: 'planned', label: '已计划', summary: '' },
  plan: { id: 'plan-1', title: '业务计划', provider: 'development', source: 'declared', version: 3, editable: true, nodes: [step('plan-a'), step('plan-b')] },
  outputs: [], warnings: [],
}
const stubs = { RunTrace: true, PluginProcess: true, DevelopmentDelivery: true, ExternalDevelopmentPanel: true, MarkdownBody: true }
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(developmentChoices).mockResolvedValue({
    itemId: 'item-1', recommendedAgentId: 'development', recommendedRepositoryPath: '/project', methodId: 'method-1', knowledgeRefs: [],
    agents: [{ id: 'development', title: '开发', version: 'v1', available: true, reason: '' }],
    executors: { codex: { available: true }, opencode: { available: false } },
  })
  vi.mocked(listDevelopment).mockResolvedValue([])
  vi.mocked(getWorkView).mockResolvedValue(workView)
  vi.mocked(createDevelopment).mockResolvedValue({ id: 'dev-1' } as never)
})

describe('网页开发委托关联业务步骤', () => {
  it('多候选时明确选择步骤，并携带当前计划版本提交', async () => {
    const wrapper = mount(DevelopmentPanel, { props: { workspace: 'personal', itemId: 'item-1', initialInstruction: '完成方案' }, global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('计划 v3')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.find('.target-step select').setValue('plan-b')
    expect(wrapper.text()).toContain('方案 plan-b')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createDevelopment).toHaveBeenCalledWith('personal', expect.objectContaining({ stepId: 'plan-b', planVersion: 3 }))
    wrapper.unmount()
  })

  it('尚无声明计划时交由服务登记开发步骤', async () => {
    vi.mocked(getWorkView).mockResolvedValue({ ...workView, plan: { ...workView.plan, source: 'empty', nodes: [] } })
    const wrapper = mount(DevelopmentPanel, { props: { workspace: 'personal', itemId: 'item-1', initialInstruction: '完成方案' }, global: { stubs } })
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const input = vi.mocked(createDevelopment).mock.calls[0]![1]
    expect(input).not.toHaveProperty('stepId')
    expect(input).not.toHaveProperty('planVersion')
    wrapper.unmount()
  })
})

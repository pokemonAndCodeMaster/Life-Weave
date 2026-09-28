// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DevelopmentPanel from './DevelopmentPanel.vue'
import AgentLaunch from './agents/AgentLaunch.vue'
import { listDevelopment } from '../api/development'

vi.mock('../api/lifeweave', () => ({ apiError: (error: unknown) => ({ message: String(error) }), getRun: vi.fn(), getRunEvents: vi.fn() }))
vi.mock('../api/development', () => ({ listDevelopment: vi.fn(), getDevelopmentDelivery: vi.fn(), getDevelopmentDiff: vi.fn(), cancelDevelopment: vi.fn() }))
vi.mock('../api/plugins', () => ({ pluginProcess: vi.fn(async () => null) }))

beforeEach(() => { vi.clearAllMocks(); vi.mocked(listDevelopment).mockResolvedValue([]) })

describe('开发入口复用共同派发', () => {
  it('打开同一 AgentLaunch，并将事项与开发 Agent 作为默认选择', async () => {
    const wrapper = mount(DevelopmentPanel, { props: { workspace: 'personal', itemId: 'item-1', initialInstruction: '完成方案' }, global: { stubs: { AgentLaunch: true, ExternalDevelopmentPanel: true } } })
    await flushPromises()
    expect(wrapper.findComponent(AgentLaunch).exists()).toBe(false)
    await wrapper.find('button[aria-expanded]').trigger('click')
    const launch = wrapper.findComponent(AgentLaunch)
    expect(launch.exists()).toBe(true)
    expect(launch.props()).toMatchObject({ workspace: 'personal', itemId: 'item-1', initialAgentId: 'development', initialInstruction: '完成方案' })
    wrapper.unmount()
  })
})

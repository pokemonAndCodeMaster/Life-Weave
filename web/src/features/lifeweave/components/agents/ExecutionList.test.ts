// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { listAgentExecutions, type ExecutionRef } from '../../api/agents'
import ExecutionList from './ExecutionList.vue'

vi.mock('../../api/agents', () => ({ listAgentExecutions: vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ apiError: (error: unknown) => ({ message: String(error) }) }))

describe('执行记录状态筛选', () => {
  it('进行中使用 active 跨阶段筛选，其他状态保持精确，列表展示中文状态', async () => {
    const statuses = ['planning', 'reviewing', 'implementing', 'blocked', 'plan_ready', 'delivery_failed']
    const items: ExecutionRef[] = statuses.map((status, index) => ({
      kind: 'managed_development', id: `dev-${index}`, itemId: 'item-1', agentId: 'developer', status,
      createdAt: '2026-09-28T10:00:00Z', traceCoverage: 'platform', title: `任务 ${index}`,
    }))
    vi.mocked(listAgentExecutions).mockResolvedValue({ items, total: items.length })
    const wrapper = mount(ExecutionList, { props: { workspace: 'personal' }, global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()
    const select = wrapper.find('select')
    await select.setValue('active')
    await flushPromises()
    expect(listAgentExecutions).toHaveBeenLastCalledWith('personal', expect.objectContaining({ status: 'active' }))
    const displayed = wrapper.findAll('.execution-link span').map(row => row.text()).join(' ')
    expect(displayed).toContain('形成方案')
    expect(displayed).toContain('审阅中')
    expect(displayed).toContain('实施中')
    expect(displayed).toContain('受阻')
    expect(displayed).toContain('方案待审阅')
    expect(displayed).toContain('交付生成失败')
    expect(displayed).not.toContain('planning')
    for (const status of ['blocked', 'plan_ready', 'delivery_failed', 'succeeded']) {
      await select.setValue(status)
      await flushPromises()
      expect(listAgentExecutions).toHaveBeenLastCalledWith('personal', expect.objectContaining({ status }))
    }
    wrapper.unmount()
  })
})

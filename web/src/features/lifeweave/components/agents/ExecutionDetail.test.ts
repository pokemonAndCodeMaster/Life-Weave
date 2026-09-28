// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getAgentExecution } from '../../api/agents'
import type { ExecutionDetail as ExecutionDetailRecord } from '../../api/agents'
import ExecutionDetail from './ExecutionDetail.vue'
import ExecutionEventList from './ExecutionEventList.vue'

vi.mock('../../api/agents', () => ({ getAgentExecution: vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ apiError: (error: unknown) => ({ message: String(error) }) }))
afterEach(() => vi.clearAllMocks())

describe('执行详情阅读', () => {
  it('长固定输入与配置默认折叠，仍可展开全文；摘要和阶段使用可读名称', async () => {
    const prompt = '固定提示全文'.repeat(2000)
    const longConfig = '配置全文'.repeat(2500)
    const record: ExecutionDetailRecord = {
      execution: { kind: 'managed_development', id: 'dev-1', itemId: 'item-1', agentId: 'developer', agentName: '开发 Agent', status: 'queued', createdAt: '2026-09-28T10:00:00Z', traceCoverage: 'platform', title: '完善事项中心' },
      configuration: { engine: 'codex', model: 'gpt-6-sol', methodId: 'method-technical-id', knowledgeRefs: ['knowledge-1', 'knowledge-2'], longConfig },
      inputs: { instruction: '完善事项中心的执行详情', repositoryPath: '/home/yyh/project/lifeweave', promptSnapshot: prompt },
      events: [{ id: 'event-1', source: 'platform', observed: 'platform', eventType: 'queued', summary: '任务已入队', occurredAt: '2026-09-28T10:00:00Z' }],
      outputs: [{ kind: 'plan', id: 'run:run-plan', content: '# 可读方案\n\n' + '阶段正文'.repeat(1000) }, { kind: 'artifact_candidate', candidateId: 'candidate-1', summary: '尚未固定' }],
      children: [
        { stage: 'plan', kind: 'managed_run', id: 'run-plan', status: 'succeeded' },
        { stage: 'review', kind: 'managed_run', id: 'run-review', status: 'queued' },
      ],
      coverage: { level: 'platform', description: '已记录平台事件', missing: [] },
      links: {},
    }
    vi.mocked(getAgentExecution).mockResolvedValue(record)
    const wrapper = mount(ExecutionDetail, { props: { workspace: 'personal', kind: 'managed_development', executionId: 'dev-1' }, global: { stubs: { RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' } } } })
    await flushPromises()

    const summaries = wrapper.findAll('.summary-list').map(row => row.text()).join(' ')
    expect(summaries).toContain('完善事项中心的执行详情')
    expect(summaries).toContain('Codex')
    expect(summaries).toContain('gpt-6-sol')
    expect(summaries).toContain('已绑定方法')
    expect(summaries).toContain('2 篇')
    expect(summaries).toContain('/home/yyh/project/lifeweave')
    expect(summaries).not.toContain(prompt)
    expect(summaries).not.toContain(longConfig)
    expect(summaries).not.toContain('method-technical-id')
    expect(wrapper.find('.detail-status').text()).toContain('等待执行')
    expect(wrapper.find('[aria-label="执行步骤"]').text()).toContain('方案')
    expect(wrapper.find('[aria-label="执行步骤"]').text()).toContain('审阅')

    const rawRecords = wrapper.findAll('details.raw-record')
    expect(rawRecords).toHaveLength(2)
    expect(rawRecords.every(row => !(row.element as HTMLDetailsElement).open)).toBe(true)
    expect(rawRecords[0]?.find('pre').text()).toContain(prompt)
    expect(rawRecords[1]?.find('pre').text()).toContain(longConfig)
    await rawRecords[0]?.find('summary').trigger('click')
    expect((rawRecords[0]?.element as HTMLDetailsElement).open).toBe(true)
    const reading = wrapper.find('details.output-reading')
    expect((reading.element as HTMLDetailsElement).open).toBe(false)
    expect(wrapper.find('.output-list p').text()).toContain('可读方案')
    expect(wrapper.find('.output-list p').text().length).toBeLessThan(230)
    await reading.find('summary').trigger('click')
    expect((reading.element as HTMLDetailsElement).open).toBe(true)
    expect(reading.text()).toContain('阶段正文')
    expect(wrapper.findAll('.output-list a')).toHaveLength(1)
    expect(wrapper.findAll('.output-list a')[0]?.attributes('data-to')).toContain('run:run-plan')
    expect(wrapper.findComponent(ExecutionEventList).props('events')).toEqual(record.events)
    wrapper.unmount()
  })
})

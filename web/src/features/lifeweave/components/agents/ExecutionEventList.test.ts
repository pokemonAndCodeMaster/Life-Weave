// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { ExecutionEvent } from '../../api/agents'
import ExecutionEventList from './ExecutionEventList.vue'

describe('运行轨迹按需阅读', () => {
  it('先显示最近 50 条，搜索仍覆盖全部事件，长消息可展开全文', async () => {
    const full = '方案正文'.repeat(2000)
    const events: ExecutionEvent[] = Array.from({ length: 120 }, (_, index) => ({
      id: `event-${index}`, source: 'codex', observed: 'native', eventType: 'agent_message',
      summary: index === 0 ? `最早事件 ${full}` : `步骤 ${index}`,
      occurredAt: '2026-09-28T10:00:00Z', payload: { text: index === 0 ? full : `步骤 ${index}` },
    }))
    const wrapper = mount(ExecutionEventList, { props: { events } })
    expect(wrapper.findAll('.event-list > li')).toHaveLength(50)
    expect(wrapper.find('.older-events').text()).toContain('70 条')
    await wrapper.find('.older-events').trigger('click')
    expect(wrapper.findAll('.event-list > li')).toHaveLength(100)
    await wrapper.find('input[type="search"]').setValue('最早事件')
    expect(wrapper.findAll('.event-list > li')).toHaveLength(1)
    expect(wrapper.find('.trace-header').text()).toContain('匹配 1 / 全部 120 条')
    const event = wrapper.find('details.event')
    expect((event.element as HTMLDetailsElement).open).toBe(false)
    expect(event.find('summary strong').text().length).toBeLessThan(220)
    expect(event.find('summary strong').text()).not.toContain(full)
    await event.find('summary').trigger('click')
    expect((event.element as HTMLDetailsElement).open).toBe(true)
    expect(event.find('.event-full-summary').text()).toContain(full)
    expect(event.find('pre').text()).toContain(full)
  })
})

// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import WorkNodeDetail from './WorkNodeDetail.vue'
import type { WorkOutputRef, WorkStep } from '../../api/workView'

const outputs: WorkOutputRef[] = ['one', 'two', 'other'].map(id => ({ id: `artifact:${id}`, artifactId: id, title: `成果 ${id}`, kind: 'artifact', summary: `摘要 ${id}` }))
const node: WorkStep = {
  id: 'read', title: '阅读', description: '分析方法', summary: '已梳理', state: 'succeeded',
  outputIds: ['artifact:one', 'artifact:two'], dependsOn: ['find'],
  expectedOutputs: [{ id: 'report', title: '分析报告', kind: 'document', required: true }],
  acceptance: '报告列出来源', deliveryStatus: 'missing', missingRequirements: ['缺少固定版本报告'],
  attempts: [{ id: 'attempt-1', outcome: 'missing', applied: false, summary: '报告未固定', createdAt: '2026-09-27T00:00:00Z', outputIds: [], issues: ['缺少版本'] }],
}
const before: WorkStep = { id: 'find', title: '找论文', description: '', summary: '', state: 'succeeded', outputIds: [], dependsOn: [] }
const props = { workspace: 'personal' as const, itemId: 'i', node, nodes: [before, node], outputs, observed: false }
const stubs = { WorkOutputReader: true }

describe('步骤交付摘要', () => {
  it('展示预期、验收和缺交付，产物只限当前步骤', async () => {
    const wrapper = mount(WorkNodeDetail, { props, global: { stubs } })
    expect(wrapper.text()).toContain('分析报告')
    expect(wrapper.text()).toContain('报告列出来源')
    expect(wrapper.text()).toContain('缺少固定版本报告')
    expect(wrapper.text()).not.toContain('成果 other')
    expect(wrapper.findAll('.output-choices button')).toHaveLength(2)
    await wrapper.findAll('.output-choices button')[1]!.trigger('click')
    expect(wrapper.emitted('selectOutput')?.[0]).toEqual(['artifact:two'])
    expect(wrapper.emitted('output')).toBeUndefined()
    wrapper.unmount()
  })

  it('讨论引用包含步骤和当前产物，历史尝试按需展开', async () => {
    const wrapper = mount(WorkNodeDetail, { props: { ...props, selectedOutputId: 'artifact:two' }, global: { stubs } })
    await wrapper.find('.step-actions button').trigger('click')
    const quote = wrapper.emitted('quote')?.[0]?.[0] as { text: string; anchor: string }
    expect(quote.text).toContain('步骤：阅读')
    expect(quote.text).toContain('artifact:two')
    expect(quote.anchor).toBe('步骤：阅读 [read]')
    expect(wrapper.find('.attempts').exists()).toBe(true)
    wrapper.unmount()
  })

  it('旧完成节点无关联成果时说明边界', () => {
    const wrapper = mount(WorkNodeDetail, { props: { ...props, node: { ...node, outputIds: [], expectedOutputs: undefined, deliveryStatus: 'legacy_unverified' } }, global: { stubs } })
    expect(wrapper.text()).toContain('旧记录未核实交付')
    expect(wrapper.text()).toContain('没有关联成果')
    wrapper.unmount()
  })
})

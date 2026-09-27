// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import WorkPlanEditor from './WorkPlanEditor.vue'
import type { ItemWorkView, WorkPlanInput } from '../../api/workView'

const view: ItemWorkView = {
  itemId: 'item-1', itemVersion: 7, current: { state: 'planned', label: '已计划', summary: '' },
  plan: { id: 'plan-1', title: '开发', provider: 'development', source: 'declared', version: 2, editable: true, nodes: [{
    id: 'implement', title: '实施', description: '写代码', summary: '', state: 'planned', dependsOn: [], outputIds: [],
    expectedOutputs: [{ id: 'code', title: '固定代码交付', kind: 'code', required: true }], acceptance: '通过真实运行验证',
  }] }, outputs: [], warnings: [],
}

describe('步骤计划编辑', () => {
  it('保存时保留预期交付和验收，并记录修改原因', async () => {
    const wrapper = mount(WorkPlanEditor, { props: { view, saving: false, error: '', conflict: false, outputs: [] } })
    expect(wrapper.find('.expected-row input').element).toHaveProperty('value', '固定代码交付')
    expect(wrapper.find('textarea[maxlength="5000"]').element).toHaveProperty('value', '写代码')
    await wrapper.find('textarea[maxlength="2000"]').setValue('补充验证范围')
    await wrapper.find('form').trigger('submit')
    const saved = wrapper.emitted('save')?.[0]?.[0] as WorkPlanInput
    expect(saved.revisionReason).toBe('补充验证范围')
    expect(saved.nodes[0]!.expectedOutputs).toEqual([{ id: 'code', title: '固定代码交付', kind: 'code', required: true }])
    expect(saved.nodes[0]!.acceptance).toBe('通过真实运行验证')
    wrapper.unmount()
  })

  it('可新增有类别的必要交付，未填写名称时阻止保存', async () => {
    const wrapper = mount(WorkPlanEditor, { props: { view, saving: false, error: '', conflict: false, outputs: [] } })
    await wrapper.find('.expected-fieldset > button').trigger('click')
    await wrapper.find('textarea[maxlength="2000"]').setValue('增加验证结果')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.text()).toContain('每份预期交付都需要名称')
    expect(wrapper.emitted('save')).toBeUndefined()
    await wrapper.findAll('.expected-row input.lw-field')[1]!.setValue('测试报告')
    await wrapper.findAll('.expected-row select')[1]!.setValue('validation')
    await wrapper.find('form').trigger('submit')
    const saved = wrapper.emitted('save')?.[0]?.[0] as WorkPlanInput
    expect(saved.nodes[0]!.expectedOutputs?.[1]).toMatchObject({ title: '测试报告', kind: 'validation', required: true })
    wrapper.unmount()
  })
})

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import EvaluationCreateForm from './EvaluationCreateForm.vue'

const candidate = { id: 'cap-one', title: '攻略研究', status: 'candidate', version: 'v1' }

describe('EvaluationCreateForm', () => {
  it('keeps a task as a plan until the user supplies a target, task and pass criteria', async () => {
    const wrapper = mount(EvaluationCreateForm, { props: { candidates: [candidate], items: [{ id: 'item-one', title: '攻略' }], busy: false } })
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.find('input[list="evaluation-items"]').setValue('item-one')
    await wrapper.findAll('select')[0]!.setValue('capability')
    await wrapper.findAll('select')[1]!.setValue('cap-one')
    await wrapper.find('input[placeholder^="例如"]').setValue('攻略验证')
    await wrapper.findAll('textarea')[0]!.setValue('解释阵容')
    await wrapper.findAll('textarea')[1]!.setValue('列出来源与限制')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('create')?.[0]?.[0]).toEqual({
      itemId: 'item-one', targetKind: 'capability', candidateId: 'cap-one',
      title: '攻略验证', instruction: '解释阵容', criteria: '列出来源与限制',
    })
  })

  it('holds the same task and criteria when reusing an assessed case', async () => {
    const template = { id: 'eval-old', itemId: 'item-one', targetKind: 'capability' as const,
      candidateId: 'cap-one', title: '旧评测', instruction: '解释阵容', criteria: '列出来源与限制' }
    const wrapper = mount(EvaluationCreateForm, { props: { candidates: [candidate], items: [], busy: false, template: null } })
    await wrapper.setProps({ template: template as never })
    expect((wrapper.findAll('textarea')[0]!.element as HTMLTextAreaElement).disabled).toBe(true)
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('create')?.[0]?.[0]).toMatchObject({ repeatOf: 'eval-old', itemId: 'item-one',
      instruction: '解释阵容', criteria: '列出来源与限制' })
  })
})

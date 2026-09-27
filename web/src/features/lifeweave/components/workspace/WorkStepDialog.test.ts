// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import WorkStepDialog from './WorkStepDialog.vue'
import type { WorkStep } from '../../api/workView'

const node: WorkStep = { id: 'step-1', title: '检查报告', description: '', summary: '', state: 'planned', dependsOn: [], outputIds: [] }

describe('步骤弹窗', () => {
  it('约束底层滚动，Escape 关闭，卸载后还原触发点焦点', async () => {
    const trigger = document.createElement('button')
    trigger.textContent = '打开步骤'
    document.body.append(trigger)
    trigger.focus()
    const originalOverflow = document.body.style.overflow
    const wrapper = mount(WorkStepDialog, { props: { workspace: 'personal', itemId: 'item-1', node, nodes: [node] }, slots: { default: '<button type="button">查看</button>' } })
    await wrapper.vm.$nextTick()
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(document.body.style.overflow).toBe('hidden')
    expect(document.activeElement?.getAttribute('aria-label')).toBe('关闭步骤详情')
    document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
    expect(document.body.style.overflow).toBe(originalOverflow)
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })
})

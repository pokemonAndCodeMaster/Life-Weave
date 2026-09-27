// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkNodeDetail from './WorkNodeDetail.vue'
import type { WorkOutputRef, WorkStep } from '../../api/workView'
import { getEntityDetail } from '../../api/lifeweave'

vi.mock('../../api/lifeweave', () => ({ getEntityDetail: vi.fn(), getRun: vi.fn(), apiError: (e: unknown) => ({ message: String(e) }) }))
vi.mock('../../api/development', () => ({ getDevelopmentDelivery: vi.fn(), getDevelopmentDiff: vi.fn() }))
const outputs: WorkOutputRef[] = ['one', 'two', 'other'].map(id => ({ id: `artifact:${id}`, artifactId: id, title: `成果 ${id}`, kind: 'artifact', summary: `摘要 ${id}` }))
const node: WorkStep = { id: 'read', title: '阅读', description: '分析方法', summary: '已梳理', state: 'succeeded', outputIds: ['artifact:one', 'artifact:two'], dependsOn: ['find'] }
const next: WorkStep = { id: 'write', title: '写报告', description: '', summary: '', state: 'planned', outputIds: [], dependsOn: ['read'] }
const before: WorkStep = { ...next, id: 'find', title: '找论文', dependsOn: [], state: 'succeeded' }
const props = { workspace: 'personal' as const, itemId: 'i', node, nodes: [before, node, next], outputs, observed: false }
const stubs = { ResearchOutputPanel: true, DevelopmentDelivery: true }
beforeEach(() => { vi.clearAllMocks(); vi.mocked(getEntityDetail).mockImplementation(async (_space, id) => ({ payload: { body: `# 正文 ${id}` } })) })
describe('步骤展开内容', () => {
  it('本步内读取关联正文，多份切换；不混入整件事项的其他产物', async () => {
    const wrapper = mount(WorkNodeDetail, { props, global: { stubs } }); await flushPromises()
    expect(wrapper.find('.output-reader').text()).toContain('正文 one')
    expect(wrapper.text()).not.toContain('成果 other')
    expect(getEntityDetail).toHaveBeenCalledTimes(1)
    await wrapper.findAll('.output-choices button')[1]!.trigger('click'); await flushPromises()
    expect(wrapper.find('.output-reader').text()).toContain('正文 two')
    expect(wrapper.emitted('output')).toBeUndefined()
    await wrapper.findAll('.outputs-heading button')[0]!.trigger('click')
    expect(wrapper.emitted('output')?.[0]).toEqual(['artifact:two'])
    await wrapper.findAll('.neighbor-links button')[1]!.trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual(['write'])
    wrapper.unmount()
  })
  it('切到无成果步骤时不泄漏前一步正文；明确完成但无成果与读取缺口', async () => {
    const wrapper = mount(WorkNodeDetail, { props, global: { stubs } }); await flushPromises()
    await wrapper.setProps({ node: { ...next, state: 'succeeded' } })
    expect(wrapper.find('.output-reader').exists()).toBe(false)
    expect(wrapper.text()).toContain('标记为已完成，但没有关联成果')
    await wrapper.setProps({ node: { ...next, outputIds: ['artifact:missing'] } })
    expect(wrapper.text()).toContain('已关联的成果目前不可读取')
    wrapper.unmount()
  })
  it('失败读取可重试，刷新同一产物版本会更新正文', async () => {
    vi.mocked(getEntityDetail).mockRejectedValueOnce(new Error('连接中断'))
    const wrapper = mount(WorkNodeDetail, { props, global: { stubs } }); await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('连接中断')
    await wrapper.find('[role="alert"] button').trigger('click'); await flushPromises()
    expect(wrapper.find('.output-reader').text()).toContain('正文 one')
    vi.mocked(getEntityDetail).mockResolvedValue({ payload: { body: '# 补充后的正文' } })
    await wrapper.setProps({ outputs: outputs.map(output => ({ ...output, version: '2' })) }); await flushPromises()
    expect(wrapper.find('.output-reader').text()).toContain('补充后的正文')
    wrapper.unmount()
  })
  it('最大 80 步和 80 份产物的讨论引用不超过输入上限，省略显式说明', async () => {
    const previous = Array.from({ length: 79 }, (_, i) => ({ ...before, id: `p${i}`, title: '前'.repeat(256) }))
    const manyOutputs = Array.from({ length: 80 }, (_, i) => ({ ...outputs[0]!, id: `${i}`.padEnd(256, 'x'), title: '果'.repeat(256) }))
    const maxNode = { ...node, id: 'n'.repeat(128), title: '题'.repeat(256), description: '描'.repeat(5000), summary: '结'.repeat(2000), outputIds: manyOutputs.map(output => output.id), dependsOn: previous.map(step => step.id) }
    const wrapper = mount(WorkNodeDetail, { props: { ...props, node: maxNode, nodes: [...previous, maxNode], outputs: manyOutputs }, global: { stubs: { ...stubs, WorkOutputReader: true } } })
    await wrapper.findAll('.output-choices button')[79]!.trigger('click')
    await wrapper.findAll('button').find(button => button.text() === '讨论这一步')!.trigger('click')
    const quote = wrapper.emitted('quote')![0]![0] as { text: string; anchor: string }
    expect(quote.text.length).toBeLessThan(12000)
    expect(quote.anchor.length).toBeLessThan(2000)
    expect(quote.text).toContain('另有 71 个')
    expect(quote.text).toContain('另有 72 份')
    expect(quote.text).toContain(manyOutputs[79]!.id)
    expect(quote.text).toContain(maxNode.description)
    wrapper.unmount()
  })

})

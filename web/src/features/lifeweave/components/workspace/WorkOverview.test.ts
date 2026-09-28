// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkOverview from './WorkOverview.vue'
import { saveItemOverview, type ItemWorkView } from '../../api/workView'
import type { WorkItem } from '../../types'

vi.mock('../../api/workView', () => ({ saveItemOverview: vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ apiError: (error: unknown) => ({message:String(error)}) }))
const view: ItemWorkView = { itemId:'item-1',itemVersion:4,overview:{background:'来自验收反馈',intent:'说明结果',expectedResult:'可审阅说明',progress:{summary:'已完成两步',state:'running',completedSteps:2,totalSteps:3},outputIds:['out-1'],sources:{}},current:{state:'running',label:'进行中',summary:''},plan:{id:'p',title:'步骤',provider:'manual',source:'empty',version:1,editable:true,nodes:[]},outputs:[{id:'out-1',title:'说明文档',kind:'document',summary:'已固定'}],warnings:[] }
const item = {id:'item-1',title:'改善验收',goal:'说明结果'} as WorkItem
beforeEach(() => vi.clearAllMocks())
describe('事项首卡', () => {
  it('同屏显示工作依据、进展和可阅读产出，并带版本保存介绍', async () => {
    vi.mocked(saveItemOverview).mockResolvedValue({...view,itemVersion:5})
    const wrapper=mount(WorkOverview,{props:{workspace:'personal',item,view}})
    expect(wrapper.text()).toContain('来自验收反馈')
    expect(wrapper.text()).toContain('已完成两步')
    await wrapper.find('button.lw-text-btn').trigger('click')
    expect(wrapper.emitted('output')?.[0]).toEqual(['out-1'])
    await wrapper.find('button.lw-btn').trigger('click')
    await wrapper.findAll('textarea')[0]!.setValue('补充背景')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(saveItemOverview).toHaveBeenCalledWith('personal','item-1',{version:4,background:'补充背景',intent:'说明结果',expectedResult:'可审阅说明'})
    expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({itemVersion:5})
    wrapper.unmount()
  })
  it('保存失败保留编辑内容并显示原因', async () => {
    vi.mocked(saveItemOverview).mockRejectedValue(new Error('版本冲突'))
    const wrapper=mount(WorkOverview,{props:{workspace:'personal',item,view}})
    await wrapper.find('button.lw-btn').trigger('click')
    await wrapper.findAll('textarea')[0]!.setValue('尚未保存')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('版本冲突')
    expect((wrapper.findAll('textarea')[0]!.element as HTMLTextAreaElement).value).toBe('尚未保存')
    wrapper.unmount()
  })
  it('真实进展和产出只展示清理后的短摘要，原报告与产出记录仍保持完整', async () => {
    const report = `implementation 阶段完成：仅修改 [README.md] (/home/yyh/project/lifeweave/.runtime/executions/personal/very-long-id/repo/README.md)，保留原标题和介绍。\n\n\`\`\`markdown\n## 运行示例\n${'日志与绝对路径 /home/yyh/project/lifeweave/.runtime/logs/run.txt '.repeat(30)}\n\`\`\``
    const rawOutput = `**本轮已形成** [方案](/home/yyh/project/lifeweave/.runtime/plan.md)：${'审阅后可阅读的固定正文。'.repeat(40)}`
    const noisyView: ItemWorkView = {
      ...view,
      overview: { ...view.overview!, progress: { ...view.overview!.progress, summary: report } },
      outputs: [{ ...view.outputs[0]!, title: '开发方案', summary: rawOutput }],
    }
    const wrapper = mount(WorkOverview, { props: { workspace: 'personal', item, view: noisyView } })
    const progress = wrapper.findAll('.overview-fact')[3]!.find('p').text()
    const summary = wrapper.find('.output-summary').text()
    expect(progress).toContain('仅修改 README.md')
    expect(progress.length).toBeLessThanOrEqual(181)
    expect(progress).not.toContain('/home/yyh')
    expect(progress).not.toContain('```')
    expect(summary).toContain('本轮已形成 方案')
    expect(summary.length).toBeLessThanOrEqual(161)
    expect(summary).not.toContain('/home/yyh')
    expect(wrapper.find('.output-title').text()).toBe('开发方案')
    expect(noisyView.overview?.progress.summary).toBe(report)
    expect(noisyView.outputs[0]?.summary).toBe(rawOutput)
    await wrapper.find('.output-title').trigger('click')
    expect(wrapper.emitted('output')?.[0]).toEqual(['out-1'])
    wrapper.unmount()
  })
})

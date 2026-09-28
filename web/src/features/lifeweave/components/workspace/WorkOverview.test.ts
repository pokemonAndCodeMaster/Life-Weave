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
})

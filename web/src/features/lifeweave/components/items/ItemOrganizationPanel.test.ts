// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ItemOrganizationPanel from './ItemOrganizationPanel.vue'
import { createOrganizationProposal, getOrganizationCatalog, type OrganizationCatalog } from '../../api/itemOrganization'

vi.mock('../../api/itemOrganization', () => ({getOrganizationCatalog:vi.fn(),createOrganizationProposal:vi.fn(),getOrganizationProposal:vi.fn(),applyOrganizationProposal:vi.fn(),undoOrganizationProposal:vi.fn(),saveOrganizationRules:vi.fn()}))
vi.mock('../../api/lifeweave', () => ({apiError:(error:unknown)=>({message:String(error)})}))
const items = [
  {id:'item-a',title:'已分类甲',status:'open',version:2,topicIds:['topic-1'],domainIds:[],parentId:null},
  {id:'item-b',title:'已分类乙',status:'open',version:2,topicIds:['topic-1'],domainIds:[],parentId:null},
]
function catalog(unorganized=false): OrganizationCatalog { return {workspace:'personal',topics:[{id:'topic-1',title:'专题',entityType:'topic'}],domains:[],items,unorganizedItems:unorganized?[items[0]!]:[],rules:[],rulesVersion:null,proposals:[]} }
const proposal = {id:'proposal-1',status:'proposed' as const,reason:'聚合',changes:[],groups:[],warnings:[],createdAt:'2026-09-28T00:00:00Z'}
beforeEach(() => {vi.clearAllMocks();vi.mocked(getOrganizationCatalog).mockResolvedValue(catalog());vi.mocked(createOrganizationProposal).mockResolvedValue(proposal)})

describe('事项聚合成员选择', () => {
  it('全部事项已分类时，仍可搜索并选入聚合建议', async () => {
    const wrapper=mount(ItemOrganizationPanel,{props:{workspace:'personal'}})
    await flushPromises()
    expect(wrapper.text()).toContain('0 项待整理')
    expect(wrapper.findAll('.organize-card')[0]!.find('button').attributes('disabled')).toBeDefined()
    const group=wrapper.findAll('.organize-card')[2]!
    expect(group.find('details.group-picker').attributes('open')).toBeUndefined()
    await group.find('summary').trigger('click')
    await group.find('input[type="search"]').setValue('已分类乙')
    expect(group.findAll('.item-choices input[type="checkbox"]')).toHaveLength(1)
    await group.find('.item-choices input[type="checkbox"]').setValue(true)
    expect(group.find('.group-members').text()).toContain('已分类乙')
    await group.find('input:not([type])').setValue('共同研究')
    await group.find('textarea').setValue('汇总两条线索')
    await group.find('button.lw-btn').trigger('click')
    await flushPromises()
    expect(createOrganizationProposal).toHaveBeenCalledWith('personal',expect.objectContaining({groups:[expect.objectContaining({title:'共同研究',goal:'汇总两条线索',itemIds:['item-b']})]}))
    expect(vi.mocked(createOrganizationProposal).mock.calls[0]![1]).not.toHaveProperty('itemIds')
    wrapper.unmount()
  })
  it('规则预览与聚合成员分别保存选择', async () => {
    vi.mocked(getOrganizationCatalog).mockResolvedValue(catalog(true))
    const wrapper=mount(ItemOrganizationPanel,{props:{workspace:'personal'}})
    await flushPromises()
    const cards=wrapper.findAll('.organize-card')
    await cards[0]!.find('input[type="checkbox"]').setValue(true)
    expect(cards[2]!.find('summary').text()).toContain('0 项')
    await cards[2]!.find('summary').trigger('click')
    await cards[2]!.findAll('.item-choices input[type="checkbox"]')[1]!.setValue(true)
    await cards[0]!.find('button').trigger('click')
    await flushPromises()
    expect(vi.mocked(createOrganizationProposal).mock.calls[0]![1]).toMatchObject({itemIds:['item-a']})
    await cards[2]!.find('input:not([type])').setValue('聚合目标')
    await cards[2]!.find('textarea').setValue('完成共同目标')
    await cards[2]!.find('button.lw-btn').trigger('click')
    await flushPromises()
    expect(vi.mocked(createOrganizationProposal).mock.calls[1]![1].groups?.[0]?.itemIds).toEqual(['item-b'])
    wrapper.unmount()
  })
})

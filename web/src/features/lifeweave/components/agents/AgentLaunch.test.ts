// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AgentLaunch from './AgentLaunch.vue'
import { dispatchAgent, getAgentChoices } from '../../api/agents'
import { getWorkView } from '../../api/workView'
import { getRecommendations } from '../../api/continuation'
import { developmentChoices } from '../../api/development'
import { listCapabilities } from '../../api/lifeweave'

vi.mock('../../api/agents', () => ({ getAgentChoices: vi.fn(), dispatchAgent: vi.fn() }))
vi.mock('../../api/workView', () => ({ getWorkView: vi.fn() }))
vi.mock('../../api/continuation', () => ({ getRecommendations: vi.fn() }))
vi.mock('../../api/development', () => ({ developmentChoices: vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ apiError: (error: unknown) => ({message:String(error)}), listCapabilities: vi.fn() }))

const router = createRouter({ history:createMemoryHistory(), routes:[{path:'/lifeweave/:workspace/agent-executions/:kind/:executionId',component:{template:'<div />'}}] })
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getAgentChoices).mockResolvedValue({itemId:'item-1',recommendedAgentId:'research',items:[{id:'research',name:'研究 Agent',description:'研究',version:1,capability:'research',pluginId:'lifeweave.research',engine:'opencode',enabled:true,available:false,reason:'默认执行器不可用',modes:['managed_run']}],engines:[{id:'opencode',label:'OpenCode',available:false,reason:'受限'},{id:'codex',label:'Codex',available:true}],environment:{}})
  vi.mocked(getWorkView).mockResolvedValue({itemId:'item-1',itemVersion:1,current:{state:'open',label:'进行中',summary:''},plan:{id:'p',title:'计划',provider:'manual',source:'empty',version:0,editable:true,nodes:[]},outputs:[],warnings:[]})
  vi.mocked(getRecommendations).mockResolvedValue({methods:[{id:'method-1',title:'研究方法',description:'',version:'1',reason:''}],documents:[{ref:'source:doc.md',sourceId:'source',title:'论文',sourceTitle:'本地',path:'doc.md',version:'1',reason:''}],suggested:{methodId:'method-1',knowledgeRefs:['source:doc.md']},unavailable:[],boundary:'建议需核对'})
  vi.mocked(developmentChoices).mockRejectedValue(new Error('不是开发事项'))
  vi.mocked(listCapabilities).mockResolvedValue({items:[]} as never)
  vi.mocked(dispatchAgent).mockResolvedValue({kind:'managed_run',id:'run-1',itemId:'item-1',agentId:'research',status:'queued',createdAt:'',traceCoverage:''})
})

describe('共同 Agent 派发', () => {
  it('可用执行器按次覆盖，并保留目录、权限、方法与知识选择', async () => {
    const wrapper = mount(AgentLaunch,{props:{workspace:'personal',itemId:'item-1',initialInstruction:'读论文'},global:{plugins:[router]}})
    await flushPromises()
    expect(wrapper.text()).toContain('默认执行器不可用')
    await wrapper.find('select').setValue('research')
    await wrapper.findAll('select')[1]!.setValue('codex')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined()
    const inputs=wrapper.findAll('input')
    await inputs.find(input=>input.attributes('placeholder')==='留空使用事项默认目录')!.setValue('/tmp/research')
    await wrapper.findAll('select').find(select=>select.text().includes('只读分析'))!.setValue('workspace-write')
    await wrapper.find('details button').trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(dispatchAgent).toHaveBeenCalledWith('personal','item-1',expect.objectContaining({agentId:'research',mode:'managed_run',engine:'codex',directory:'/tmp/research',permission:'workspace-write',methodId:'method-1',knowledgeRefs:['source:doc.md']}))
    expect(vi.mocked(dispatchAgent).mock.calls[0]![2]).not.toHaveProperty('model')
    wrapper.unmount()
  })
})

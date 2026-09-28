// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AgentRegistry from './AgentRegistry.vue'
import { createAgent, listAgents, updateAgent } from '../../api/agents'
import { listMethods } from '../../api/lifeweave'

vi.mock('../../api/agents', () => ({ listAgents:vi.fn(), createAgent:vi.fn(), updateAgent:vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ listMethods:vi.fn(), apiError:(error:unknown)=>({message:String(error)}) }))
const agent = {id:'general',name:'通用 Agent',description:'处理工作',version:2,capability:'general' as const,pluginId:'lifeweave.general',methodId:null,engine:'codex' as const,model:null,runtime:'native' as const,permission:'read-only' as const,enabled:true,available:true,modes:['managed_run']}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listAgents).mockResolvedValue({items:[agent],engines:[{id:'codex',label:'Codex',available:true}]})
  vi.mocked(listMethods).mockResolvedValue({items:[],unavailable:[]})
  vi.mocked(createAgent).mockResolvedValue(agent)
  vi.mocked(updateAgent).mockResolvedValue(agent)
})
describe('Agent 注册与更新契约', () => {
  it('注册只提交能力字段，插件由服务端决定', async () => {
    const wrapper=mount(AgentRegistry,{props:{workspace:'personal'},global:{stubs:{RouterLink:true}}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='注册 Agent')!.trigger('click')
    await wrapper.find('input[pattern]').setValue('research-helper')
    await wrapper.find('input[required]:not([pattern])').setValue('论文帮手')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const body=vi.mocked(createAgent).mock.calls[0]![1]
    expect(body).toMatchObject({id:'research-helper',name:'论文帮手',capability:'general',engine:'codex'})
    expect(body).not.toHaveProperty('pluginId')
    wrapper.unmount()
  })
  it('更新带版本且不提交不可变能力与插件', async () => {
    const wrapper=mount(AgentRegistry,{props:{workspace:'personal'},global:{stubs:{RouterLink:true}}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='编辑配置')!.trigger('click')
    expect(wrapper.find('select[disabled]').exists()).toBe(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const body=vi.mocked(updateAgent).mock.calls[0]![2]
    expect(body.version).toBe(2)
    expect(body).not.toHaveProperty('capability')
    expect(body).not.toHaveProperty('pluginId')
    wrapper.unmount()
  })
})

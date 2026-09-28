// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, shallowRef } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getAgentExecution } from '../api/agents'
import { useExecutionDetail } from './useExecutionDetail'
import type { ExecutionDetail } from '../api/agents'

vi.mock('../api/agents', () => ({ getAgentExecution: vi.fn() }))
vi.mock('../api/lifeweave', () => ({ apiError: (error: unknown) => ({message:String(error)}) }))
const record = (status: string): ExecutionDetail => ({execution:{kind:'managed_run',id:'run-1',itemId:'item-1',agentId:'general',status,createdAt:'',traceCoverage:''},configuration:{},inputs:{},events:[],outputs:[],children:[],coverage:{level:'full',description:'',missing:[]},links:{}})
const Harness = defineComponent({ setup() { const scope=shallowRef<'personal'>('personal'); const kind=shallowRef<'managed_run'>('managed_run'); const id=shallowRef('run-1'); const state=useExecutionDetail(scope,kind,id); return {...state} }, template:'<p>{{ detail?.execution.status || error }}</p>' })
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

describe('执行详情刷新', () => {
  it('运行中每三秒读取，进入终态后停止，离页清理计时器', async () => {
    vi.useFakeTimers()
    vi.mocked(getAgentExecution).mockResolvedValueOnce(record('running')).mockResolvedValueOnce(record('succeeded'))
    const wrapper=mount(Harness)
    await flushPromises()
    expect(wrapper.text()).toBe('running')
    expect(getAgentExecution).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    expect(wrapper.text()).toBe('succeeded')
    expect(getAgentExecution).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(9000)
    expect(getAgentExecution).toHaveBeenCalledTimes(2)
    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
  it('请求失败明确展示错误并可重试', async () => {
    vi.mocked(getAgentExecution).mockRejectedValueOnce(new Error('trace unavailable')).mockResolvedValueOnce(record('failed'))
    const wrapper=mount(Harness)
    await flushPromises()
    expect(wrapper.text()).toContain('trace unavailable')
    await (wrapper.vm as unknown as {refresh:()=>Promise<void>}).refresh()
    await flushPromises()
    expect(wrapper.text()).toBe('failed')
    wrapper.unmount()
  })
})

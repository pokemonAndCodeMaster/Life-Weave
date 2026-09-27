import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/shared/api/http', () => ({ http: { get, post, request: vi.fn() } }))

import { apiError, createRun, getRunArtifactResult, getRunEvents, machineAction, runAction } from './lifeweave'

describe('lifeweave runtime API contract', () => {
  beforeEach(() => { get.mockReset(); post.mockReset() })

  it('Axios 同时带 status/message 时仍优先显示服务返回的具体错误', () => {
    const problem = { message: 'Request failed with status code 409', status: 409,
      response: { status: 409, data: { detail: '指定成果版本与保存的交付不一致' } } }
    expect(apiError(problem).message).toBe('指定成果版本与保存的交付不一致')
    expect(apiError(null).status).toBe(0)
  })

  it('从独立事件与固定结果端点读取真实运行数据', async () => {
    get.mockResolvedValueOnce({ data: { items: [{ sequence: 1, type: 'started' }], nextSequence: 2 } })
      .mockResolvedValueOnce({ data: 'verified output', headers: { 'x-artifact-version': 'sha256:abc' } })
    expect(await getRunEvents('personal', 'run/1')).toEqual([{ sequence: 1, type: 'started' }])
    expect(get).toHaveBeenNthCalledWith(1, '/lifeweave/personal/runs/run%2F1/events', { params: { afterSequence: 0, limit: 200 } })
    expect(await getRunArtifactResult('personal', 'run/1')).toEqual({ content: 'verified output', version: 'sha256:abc' })
  })

  it('使用最终机器状态和按当前上下文重试契约', async () => {
    post.mockResolvedValue({ data: {} })
    await machineAction('team', 'node-1', 'pause')
    expect(post).toHaveBeenCalledWith('/lifeweave/team/machines/node-1/state', { action: 'pause' })
    await runAction('team', 'run-1', 'retry')
    expect(post).toHaveBeenCalledWith('/lifeweave/team/runs/run-1/retry', { syncContext: true })
    await createRun('team', { itemId: 'item-1', instruction: '验证', engine: 'codex', runtime: 'native', model: 'gpt-5.6-luna', permission: 'workspace-write', capabilityCandidateId: 'cap-1' })
    expect(post).toHaveBeenLastCalledWith('/lifeweave/team/runs', expect.objectContaining({ model: 'gpt-5.6-luna', permission: 'workspace-write', capabilityCandidateId: 'cap-1' }))
  })
})

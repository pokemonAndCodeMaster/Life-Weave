// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import PluginProcess from './PluginProcess.vue'
import { http } from '@/shared/api/http'
import type { RunEvent } from '../types'
import type { PluginCall, PluginPlan, PluginProcess as Process } from '../api/plugins'

vi.mock('@/shared/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
const route = reactive({ params: { workspace: 'personal', itemId: 'item-1234567890abcdef' } })
vi.mock('vue-router', () => ({ useRoute: () => route }))
const itemId = 'item-1234567890abcdef', assignmentId = 'dev-1234567890abcdef'
const runId = 'gzrun-20260926-163536-b616da61', secondRun = 'gzrun-20260926-163408-4b56d934'
const pluginId = 'lifeweave.execution.codex', digest = 'a'.repeat(64), otherDigest = 'b'.repeat(64)
const nativeId = '01958128-68b0-7124-a833-3c55e8e086a1'
const secret = 'sk-secret-DO-NOT-DISPLAY full prompt: execute curl https://secret.example'
function call(overrides: Partial<PluginCall> = {}): PluginCall {
  return { id: 'pcall-1234567890abcdef12345678', item_id: itemId, assignment_id: assignmentId,
    run_id: runId, plan_id: 'pplan-1234567890abcdef', step_id: 'plan.codex', parent_call_id: null,
    plugin_id: pluginId, plugin_version: '1', implementation_digest: digest, operation: 'run', state: 'succeeded',
    observed_by: 'platform', input_ref: { contextVersionId: 'ctxv-1234567890abcdef', repositoryRevision: 'c'.repeat(40) },
    output_ref: { runId, exitCode: 0 }, has_error: false, error_code: null,
    started_at: '2026-09-26T16:35:36Z', finished_at: '2026-09-26T16:36:36Z', ...overrides }
}
function plan(overrides: Partial<PluginPlan> = {}): PluginPlan {
  return { id: 'pplan-1234567890abcdef', item_id: itemId, assignment_id: assignmentId, version: 1,
    bindings: { [pluginId]: { version: '1', implementationDigest: digest } },
    steps: [{ id: 'plan.codex', stage: 'planning', pluginId, operation: 'run', required: true, observed: true, callIds: [], observation: 'actual' }], ...overrides }
}
function process(overrides: Partial<Process> = {}): Process { return { itemId, plans: [plan()], calls: [call()], truncated: false, boundary: secret, ...overrides } }
const snapshot = (id = runId) => ({ id, itemId, state: 'succeeded', session: nativeId, result: secret, instruction: secret, error: secret })
const event = (sequence: number) => ({ sequence, occurredAt: '2026-09-26T16:36:36Z', source: 'codex', eventType: 'item.completed', summary: secret,
  payload: { item: { type: 'command_execution', status: 'completed', command: secret, aggregated_output: secret, summary: secret }, prompt: secret } })
let rows: unknown[], runResponse: Record<string, unknown>, eventPage: { items: RunEvent[]; nextSequence: number }
const views: ReturnType<typeof mount>[] = []
function render(value: Process | null = process(), error?: string) {
  const view = mount(PluginProcess, { props: { process: value, assignmentId, error } }); views.push(view); return view
}
async function clickRun(view: ReturnType<typeof render>, id = runId) {
  await view.findAll('button').find(button => button.text() === `查看 Run ${id}`)!.trigger('click'); await flushPromises()
}
async function clickText(view: ReturnType<typeof render>, text: string) {
  await view.findAll('button').find(button => button.text() === text)!.trigger('click'); await flushPromises()
}
beforeEach(() => {
  vi.resetAllMocks(); route.params.workspace = 'personal'; route.params.itemId = itemId
  rows = [{ id: assignmentId, itemId, planRunId: runId, reviewRunId: secondRun, implementationRunId: null, instruction: secret }]
  runResponse = snapshot(); eventPage = { items: [event(1)], nextSequence: 1 }
  vi.mocked(http.get).mockImplementation(async (url) => {
    if (url.endsWith('/development')) return { data: { items: rows } }
    if (url.endsWith('/events')) return { data: eventPage }
    return { data: runResponse }
  })
})
afterEach(() => { views.splice(0).forEach(view => view.unmount()) })

it('expands independent call details and preserves expansion on refreshed records', async () => {
  const view = render()
  const details = view.get('details.plugin-call')
  ;(details.element as HTMLDetailsElement).open = true; await details.trigger('toggle')
  expect(view.text()).toContain('调用固定插件版本1')
  expect(view.text()).toContain(digest)
  expect(view.text()).toContain('ctxv-1234567890abcdef')
  expect(view.text()).toContain('c'.repeat(40))
  expect(view.text()).toContain('服务端调用边界')
  expect(view.text()).toContain('2026-09-26T16:36:36Z')
  await view.setProps({ process: process({ calls: [call({ state: 'failed', finished_at: null, has_error: true, error_code: 'authentication_failed' })] }) })
  expect((view.get('details.plugin-call').element as HTMLDetailsElement).open).toBe(true)
  expect(view.text()).toContain('认证失败')
  expect(view.text()).toContain('尚未记录结束；不据此推断仍在运行')
  expect(http.get).not.toHaveBeenCalled()
})

it('matches item, assignment, plan and step, keeping unmatched calls readable', () => {
  const secondPlan = plan({ id: 'pplan-aaaaaaaaaaaaaaaa' })
  const view = render(process({ plans: [plan(), secondPlan, plan({ id: 'pplan-bbbbbbbbbbbbbbbb', item_id: 'item-ffffffffffffffff' })], calls: [
    call(), call({ id: 'pcall-aaaaaaaaaaaaaaaaaaaaaaaa', plan_id: secondPlan.id, state: 'failed' }),
    call({ id: 'pcall-bbbbbbbbbbbbbbbbbbbbbbbb', plan_id: null, step_id: null }),
    call({ id: 'pcall-cccccccccccccccccccccccc', item_id: 'item-ffffffffffffffff' }),
    call({ id: 'pcall-dddddddddddddddddddddddd', assignment_id: 'dev-ffffffffffffffff' }),
  ] }))
  const groups = view.findAll('.plugin-step')
  expect(groups).toHaveLength(3)
  expect(groups[0]!.findAll('.plugin-call')).toHaveLength(1)
  expect(groups[1]!.text()).toContain('pcall-aaaaaaaaaaaaaaaaaaaaaaaa')
  expect(groups[0]!.text()).not.toContain('pcall-aaaaaaaaaaaaaaaaaaaaaaaa')
  expect(groups[2]!.text()).toContain('未匹配固定步骤的调用')
  expect(view.text()).toContain('本次已返回 3 次')
})

it('separates loading, failed loading, no plan, conditional steps and truncation', async () => {
  const view = render(null)
  expect(view.text()).toContain('正在读取插件过程')
  expect(view.text()).not.toContain('创建年代')
  await view.setProps({ error: secret })
  expect(view.text()).toContain('暂不可读取')
  expect(view.html()).not.toContain(secret)
  await view.setProps({ error: '', process: process({ plans: [], calls: [] }) })
  expect(view.text()).toContain('无法仅据此判断创建年代')
  const conditional = plan(); conditional.steps[0]!.required = false
  await view.setProps({ process: process({ plans: [conditional], calls: [], truncated: true }) })
  expect(view.text()).toContain('尚无实际调用记录（条件步骤）')
  expect(view.text()).toContain('已达到返回上限，记录可能不完整')
  expect(view.text()).not.toContain('请缩小')
})

it('shows full drift evidence, distinguishes absent bindings, and keeps orphan history', async () => {
  const view = render(process({ calls: [call({ plugin_version: '2', implementation_digest: otherDigest })] }))
  expect(view.text()).toContain('插件版本不同、实现摘要不同')
  expect(view.text()).toContain(digest); expect(view.text()).toContain(otherDigest)
  expect(view.text()).toContain('未检查当前安装版本')
  await view.setProps({ process: process({ plans: [plan({ bindings: {} })] }) })
  expect(view.text()).toContain('缺少固定绑定，无法比较')
  expect(view.text()).not.toContain('计划固定插件版本')
  await view.setProps({ process: process({ plans: [] }) })
  expect(view.findAll('.plugin-call')).toHaveLength(1)
})

it('reads output-only Run links, derives stage from assignment and uses GET only', async () => {
  const view = render(process({ calls: [call({ run_id: null })] }))
  await clickRun(view)
  expect(view.text()).toContain('开发阶段：方案')
  expect(view.text()).toContain(nativeId)
  expect(view.text()).toContain('命令执行')
  expect(view.text()).toContain('item.completed')
  expect(view.html()).not.toContain(secret)
  expect(http.get).toHaveBeenCalledWith(`/lifeweave/personal/runs/${runId}/events`, { params: { afterSequence: 0, limit: 200 } })
  expect(http.get).toHaveBeenCalledTimes(3)
  expect(http.post).not.toHaveBeenCalled(); expect(http.put).not.toHaveBeenCalled(); expect(http.delete).not.toHaveBeenCalled()
})

it('reads input-only Run links without inventing stage association', async () => {
  rows = []
  const view = render(process({ calls: [call({ run_id: null, input_ref: { runId }, output_ref: {} })] }))
  await clickRun(view)
  expect(view.text()).toContain('本委托没有记录此 Run 的阶段关联')
})

it('leaves calls without a Run readable and empty references explicit', () => {
  const view = render(process({ calls: [call({ run_id: null, input_ref: {}, output_ref: {}, finished_at: null })] }))
  expect(view.text()).toContain('输入引用未记录')
  expect(view.text()).toContain('未记录可安全读取的 Run 引用')
  expect(view.findAll('button')).toHaveLength(0)
})

it.each(['wrong-item', 'wrong-run'])('rejects %s before requesting events', async mismatch => {
  runResponse = { ...snapshot(), [mismatch === 'wrong-item' ? 'itemId' : 'id']: 'different' }
  const view = render(); await clickRun(view)
  expect(view.text()).toContain('运行归属不符')
  expect(view.text()).not.toContain(nativeId)
  expect(http.get).toHaveBeenCalledTimes(2)
})

it.each(['route-item', 'route-workspace'])('refuses invalid %s without fetching', async mismatch => {
  if (mismatch === 'route-item') route.params.itemId = 'item-ffffffffffffffff'
  else route.params.workspace = 'other'
  const view = render(); await clickRun(view)
  expect(view.text()).toContain('当前路由与事项不一致')
  expect(http.get).not.toHaveBeenCalled()
})

it('does not leak missing-run/API error bodies and preserves call details', async () => {
  vi.mocked(http.get).mockRejectedValue({ response: { status: 404, data: { detail: secret } }, message: secret })
  const view = render(); await clickRun(view)
  expect(view.text()).toContain('运行暂不可读取')
  expect(view.text()).toContain(digest)
  expect(view.html()).not.toContain(secret)
})

it('deduplicates paged events and stops when the cursor does not advance', async () => {
  eventPage = { items: Array.from({ length: 200 }, (_, index) => event(index + 1)), nextSequence: 200 }
  const view = render(); await clickRun(view)
  expect(view.text()).toContain('可能还有记录')
  eventPage = { items: [event(200), event(201)], nextSequence: 201 }
  await clickText(view, '加载后续事件')
  expect(view.findAll('.event-list > li')).toHaveLength(201)
  expect(http.get).toHaveBeenLastCalledWith(`/lifeweave/personal/runs/${runId}/events`, { params: { afterSequence: 200, limit: 200 } })
  expect(view.text()).not.toContain('加载后续事件')
  eventPage = { items: Array.from({ length: 200 }, () => event(1)), nextSequence: 0 }
  await clickRun(view)
  expect(view.text()).toContain('游标未推进或不一致')
  expect(view.findAll('.event-list > li')).toHaveLength(1)
  expect(view.text()).not.toContain('加载后续事件')
})

it('can retry event errors without discarding run or rendering raw failure text', async () => {
  vi.mocked(http.get).mockImplementation(async url => {
    if (url.endsWith('/development')) return { data: { items: rows } }
    if (url.endsWith('/events')) throw new Error(secret)
    return { data: snapshot() }
  })
  const view = render(); await clickRun(view)
  expect(view.text()).toContain(nativeId); expect(view.text()).toContain('重试读取事件')
  expect(view.html()).not.toContain(secret)
  vi.mocked(http.get).mockResolvedValue({ data: { items: [], nextSequence: 0 } })
  await clickText(view, '重试读取事件')
  expect(view.text()).toContain('尚无已返回的事件记录')
})

it.each(['workspace', 'item', 'assignment', 'unmount'])('ignores delayed run details after %s changes', async change => {
  let resolve!: (value: unknown) => void
  vi.mocked(http.get).mockImplementation(async url => {
    if (url.endsWith('/development')) return { data: { items: rows } }
    return new Promise(done => { resolve = done }) as never
  })
  const view = render(); await clickRun(view)
  if (change === 'workspace') route.params.workspace = 'team'
  if (change === 'item') route.params.itemId = 'item-ffffffffffffffff'
  if (change === 'assignment') await view.setProps({ assignmentId: 'dev-ffffffffffffffff' })
  if (change === 'unmount') view.unmount()
  await flushPromises(); resolve({ data: snapshot() }); await flushPromises()
  expect(http.get).toHaveBeenCalledTimes(2)
  if (change !== 'unmount') expect(view.find('.run-reader').exists()).toBe(false)
})

it('ignores late events when another Run is selected', async () => {
  let resolve!: (value: unknown) => void
  vi.mocked(http.get).mockImplementation(async url => {
    if (url.endsWith('/development')) return { data: { items: rows } }
    if (url.endsWith(`${runId}/events`)) return new Promise(done => { resolve = done }) as never
    if (url.endsWith('/events')) return { data: { items: [event(2)], nextSequence: 2 } }
    return { data: snapshot(url.endsWith(secondRun) ? secondRun : runId) }
  })
  const view = render(process({ calls: [call({ output_ref: { runId: secondRun } })] }))
  await clickRun(view); await clickRun(view, secondRun)
  resolve({ data: { items: [event(1)], nextSequence: 1 } }); await flushPromises()
  expect(view.text()).toContain('开发阶段：独立审阅')
  expect(view.findAll('.event-list > li')).toHaveLength(1)
  expect(view.get('.event-list').text()).toContain('#2')
})

it('filters nested reference fields, arbitrary event metadata, summaries and error text from the DOM', async () => {
  const sourceId = 'document-1234567890abcdef'
  eventPage = { items: [{ ...event(1), eventType: secret, source: secret, occurredAt: secret, payload: { item: { type: secret, status: secret }, exitCode: secret, outcome: secret } }], nextSequence: 1 }
  const view = render(process({ calls: [call({ has_error: true,
    input_ref: { prompt: secret, runId: secret, methodId: secret, contextVersionId: secret, repositoryRevision: secret, unknown: { secret }, knowledgeRefs: [secret] },
    output_ref: { sources: [{ id: sourceId, version: digest, sourcePath: secret, content: secret }, { id: secret, version: secret }], methodIds: [secret], nested: { runId: secret } },
  })] }))
  await clickRun(view)
  expect(view.text()).toContain(sourceId); expect(view.text()).toContain('知识引用：1 条（路径已隐藏）')
  expect(view.text()).toContain('自由文本原文已隐藏')
  expect(view.html()).not.toContain(secret)
  expect(view.html()).not.toContain('secret.example')
})

it('preserves the selected Run on polling refresh and clears it when its call disappears', async () => {
  const view = render(); await clickRun(view)
  await view.setProps({ process: process() })
  expect(view.text()).toContain(nativeId)
  expect(view.get('.run-reader').attributes('tabindex')).toBe('-1')
  expect(http.get).toHaveBeenCalledTimes(3)
  await view.setProps({ process: process({ calls: [] }) })
  expect(view.find('.run-reader').exists()).toBe(false)
})

it('renders known platform lifecycle types while dropping events with invalid sequence numbers', async () => {
  eventPage = { items: [{ ...event(1), source: 'platform', eventType: 'run.queued' }, { ...event(2), sequence: NaN }], nextSequence: 1 }
  const view = render(); await clickRun(view)
  expect(view.get('.event-list').text()).toContain('工作台 · run.queued')
  expect(view.findAll('.event-list > li')).toHaveLength(1)
  expect(view.text()).toContain('部分事件缺少有效序号')
})

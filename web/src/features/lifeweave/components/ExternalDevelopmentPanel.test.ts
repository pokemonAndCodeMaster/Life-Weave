import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { RouterLinkStub, enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import ExternalDevelopmentPanel from './ExternalDevelopmentPanel.vue'
import * as api from '../api/externalDevelopment'
import type { ExternalActivity } from '../api/externalDevelopment'

vi.mock('../api/externalDevelopment', () => ({ listExternalSessions: vi.fn(), getExternalDiff: vi.fn() }))
enableAutoUnmount(afterEach)
const start: ExternalActivity = {
  id: 'start', kind: 'external_development_start', body: 'Develop this item',
  createdAt: '2026-09-27T02:00:00+08:00',
  payload: { sessionId: 'external-one', phase: 'started', nativeSessionId: 'native-one',
    methodId: 'method-one', agentId: 'development', observedGit: { repositoryPath: '/repo', revision: 'a'.repeat(40),
      changedCount: 0, untrackedCount: 0, changedPaths: [], untrackedPaths: [] },
    declaredInputs: [{ id: 'input-one', title: 'Design', version: 'b'.repeat(40), sourcePath: 'docs/design.md' }] },
}
const report: ExternalActivity = {
  id: 'report', kind: 'external_development_event', body: 'Reviewed the design',
  createdAt: '2026-09-27T02:03:00+08:00',
  payload: { sessionId: 'external-one', phase: 'design', reportedChecks: ['source reviewed'] },
}
const hook: ExternalActivity = {
  id: 'hook', kind: 'external_development_hook', body: 'Codex tool event',
  createdAt: '2026-09-27T02:04:00+08:00',
  payload: { sessionId: 'external-one', phase: 'tool', source: 'codex_hook',
    toolName: 'exec_command', model: 'gpt-6', turnId: 'turn-one', inputHash: 'hash-one', exitCode: 0 },
}
const render = () => mount(ExternalDevelopmentPanel, { props: { workspace: 'personal', itemId: 'item-one' },
  global: { stubs: { RouterLink: RouterLinkStub } } })
beforeEach(() => { vi.clearAllMocks() })

it('shows one native session with explicit report and limited Hook provenance', async () => {
  vi.mocked(api.listExternalSessions).mockResolvedValue([hook, report, start])
  vi.mocked(api.getExternalDiff).mockResolvedValue({ patch: '+actual', fileCount: 1, truncated: false, scope: 'May include other sessions' })
  const view = render()
  await flushPromises()
  expect(view.text()).toContain('native-one')
  expect(view.text()).toContain('method-one')
  expect(view.text()).toContain('docs/design.md')
  expect(view.getComponent(RouterLinkStub).props('to')).toEqual({
    path: '/lifeweave/personal/maintenance', query: { tab: 'plugins', pluginId: 'lifeweave.development' },
  })
  expect(view.text()).toContain('已收到 1 条 Hook 元事件')
  expect(view.text()).toContain('Reviewed the design')
  expect(view.text()).toContain('Codex Hook 元事件')
  expect(view.text()).toContain('Turn turn-one')
  expect(view.text()).toContain('主动上报检查：source reviewed')
  await view.get('article button').trigger('click')
  await flushPromises()
  expect(api.getExternalDiff).toHaveBeenCalledWith('personal', 'item-one', 'external-one')
  expect(view.text()).toContain('May include other sessions')
})

it('clears stale item data and ignores late responses after switching items', async () => {
  let finish!: (rows: ExternalActivity[]) => void
  vi.mocked(api.listExternalSessions).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    .mockResolvedValueOnce([])
  const view = render()
  await view.setProps({ itemId: 'item-two' })
  await flushPromises()
  finish([start])
  await flushPromises()
  expect(view.text()).not.toContain('native-one')
  expect(view.text()).toContain('尚未登记本机 Codex 会话')
})

it('keeps external API failure local and allows refresh', async () => {
  vi.mocked(api.listExternalSessions).mockRejectedValueOnce(new Error('unavailable')).mockResolvedValueOnce([start])
  const view = render()
  await flushPromises()
  expect(view.get('[role="alert"]').text()).toContain('unavailable')
  await view.get('button').trigger('click')
  await flushPromises()
  expect(view.find('[role="alert"]').exists()).toBe(false)
  expect(view.text()).toContain('native-one')
  expect(view.text()).toContain('尚未观测到 Hook 事件')
})

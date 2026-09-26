// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import PluginCatalog from './PluginCatalog.vue'
import * as plugins from '../api/plugins'
import type { PluginCall, PluginDescriptor } from '../api/plugins'

vi.mock('../api/plugins', () => ({ pluginCatalog: vi.fn(), pluginDetail: vi.fn(), setPluginEnabled: vi.fn() }))
const descriptor: PluginDescriptor = {
  id: 'lifeweave.execution.codex', name: 'Codex 执行', description: '执行器', kind: 'executor',
  version: '1', operations: ['run'], requires: [], composed_of: [], implementationDigest: 'a'.repeat(64),
  runnable: true, verified: false, reason: '可启动', observation_boundary: '受管调用',
  configuration_link: null, enabled: true, configured: true, configVersion: 1,
}
const oldCall = { id: 'call-old', item_id: 'old-personal-item', state: 'succeeded', operation: 'run',
  started_at: '2026-09-26T00:00:00Z' } as PluginCall
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(plugins.pluginCatalog).mockResolvedValue({ items: [descriptor], total: 1 })
})

it('clears prior-space calls and ignores a late detail response after switching space', async () => {
  let resolveOld!: (value: PluginDescriptor & { recentCalls: PluginCall[] }) => void
  vi.mocked(plugins.pluginDetail).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
  const view = mount(PluginCatalog, {
    props: { workspace: 'personal' },
    global: { stubs: { RouterLink: { props: ['to'], template: '<a><slot /></a>' } } },
  })
  await flushPromises()
  await view.findAll('button').find(button => button.text() === '查看近期使用')!.trigger('click')
  await view.setProps({ workspace: 'team' })
  await flushPromises()
  resolveOld({ ...descriptor, recentCalls: [oldCall] })
  await flushPromises()
  expect(view.text()).not.toContain('old-personal-item')
  expect(view.text()).toContain('查看近期使用')
  view.unmount()
})

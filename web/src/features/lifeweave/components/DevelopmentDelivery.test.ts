import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import DevelopmentDelivery from './DevelopmentDelivery.vue'
import type { DevelopmentDelivery as Delivery } from '../api/development'
import * as api from '../api/development'

vi.mock('../api/development', () => ({
  checkDevelopmentIntegration: vi.fn(), decideDevelopmentDelivery: vi.fn(), downloadDevelopmentDelivery: vi.fn(),
}))
enableAutoUnmount(afterEach)
const delivery: Delivery = {
  id: 'delivery-one', assignmentId: 'assignment-one', implementationRunId: 'run-one',
  baseRevision: '047fe3857f0400dbd710d1735b5a1c17cc6cf2ec', artifactSha256: '1234567890abcdef'.repeat(4),
  manifest: { files: [], excludedGenerated: [], patchSha256: 'fedcba0987654321'.repeat(4), serviceChecks: [], verificationBoundary: '' },
  integrationCommit: 'f'.repeat(40), integrationCheckedAt: null, integrationCurrentHead: true,
  decision: null, decisionScope: null, decisionReason: null, decidedAt: null,
}
const writeText = vi.fn<(text: string) => Promise<void>>()
const render = () => mount(DevelopmentDelivery, { props: { workspace: 'personal', delivery: structuredClone(delivery) } })
const buttons = (view: ReturnType<typeof render>) => view.findAll('.delivery-version button')
function deferred() {
  let resolve!: () => void
  let reject!: (error: Error) => void
  const promise = new Promise<void>((ok, fail) => { resolve = ok; reject = fail })
  return { promise, resolve, reject }
}
beforeEach(() => {
  vi.clearAllMocks()
  writeText.mockReset().mockResolvedValue()
  vi.spyOn(navigator, 'clipboard', 'get').mockReturnValue({ writeText } as unknown as Clipboard)
})

it('shows and copies the complete baseline and ZIP hash without invoking delivery actions', async () => {
  const view = render()
  expect(view.findAll('dt').map(node => node.text())).toEqual(['Git 基线提交', '交付 ZIP SHA-256'])
  expect(view.findAll('code').map(node => node.text())).toEqual([delivery.baseRevision, delivery.artifactSha256])
  expect(view.text()).not.toContain(delivery.manifest.patchSha256)
  for (const [index, value, label] of [[0, delivery.baseRevision, 'Git 基线提交'], [1, delivery.artifactSha256, '交付 ZIP SHA-256']] as const) {
    await buttons(view)[index]!.trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenLastCalledWith(value)
    expect(view.get('[role="status"]').text()).toBe(`已复制${label}`)
  }
  expect(writeText).toHaveBeenCalledTimes(2)
  expect(api.downloadDevelopmentDelivery).not.toHaveBeenCalled()
  expect(api.checkDevelopmentIntegration).not.toHaveBeenCalled()
  expect(api.decideDevelopmentDelivery).not.toHaveBeenCalled()
  expect(view.emitted('updated')).toBeUndefined()
})

it('announces pending state and prevents concurrent writes to either field', async () => {
  const pending = deferred()
  writeText.mockReturnValueOnce(pending.promise)
  const view = render()
  await buttons(view)[0]!.trigger('click')
  expect(view.get('[role="status"]').text()).toBe('正在复制Git 基线提交…')
  expect(view.get('[role="status"]').attributes('aria-live')).toBe('polite')
  expect(buttons(view).every(button => button.attributes('disabled') !== undefined)).toBe(true)
  await buttons(view)[0]!.trigger('click')
  await buttons(view)[1]!.trigger('click')
  expect(writeText).toHaveBeenCalledTimes(1)
  pending.resolve()
  await flushPromises()
  expect(buttons(view).every(button => button.attributes('disabled') === undefined)).toBe(true)
  expect(view.get('[role="status"]').text()).toBe('已复制Git 基线提交')
})

it('reports browser rejection, retains the full value and permits retry', async () => {
  writeText.mockRejectedValueOnce(new DOMException('denied', 'NotAllowedError'))
  const view = render()
  await buttons(view)[1]!.trigger('click')
  await flushPromises()
  expect(view.get('[role="status"]').text()).toBe('交付 ZIP SHA-256：无法自动复制，请选中完整值手动复制')
  expect(view.findAll('code')[1]!.text()).toBe(delivery.artifactSha256)
  await buttons(view)[1]!.trigger('click')
  await flushPromises()
  expect(view.get('[role="status"]').text()).toBe('已复制交付 ZIP SHA-256')
})

it.each([undefined, {}])('offers manual copying when the clipboard API is incomplete: %s', async clipboard => {
  vi.spyOn(navigator, 'clipboard', 'get').mockReturnValue(clipboard as Clipboard)
  const view = render()
  await buttons(view)[0]!.trigger('click')
  await flushPromises()
  expect(view.get('[role="status"]').text()).toBe('Git 基线提交：无法自动复制，请选中完整值手动复制')
  expect(view.findAll('code')[0]!.text()).toBe(delivery.baseRevision)
  expect(writeText).not.toHaveBeenCalled()
  expect(buttons(view)[0]!.attributes('disabled')).toBeUndefined()
})

const changes = [
  { workspace: 'team' as const },
  ...[
    { id: 'delivery-two' }, { assignmentId: 'assignment-two' }, { implementationRunId: 'run-two' },
    { baseRevision: 'a'.repeat(40) }, { artifactSha256: 'b'.repeat(64) },
  ].map(change => ({ delivery: { ...delivery, ...change } })),
]
describe.each(['resolve', 'reject'] as const)('late clipboard %s', outcome => {
  it.each(changes)('ignores callbacks after identity changes: %j', async change => {
    const pending = deferred()
    writeText.mockReturnValueOnce(pending.promise)
    const view = render()
    await buttons(view)[0]!.trigger('click')
    await view.setProps(change)
    expect(view.get('[role="status"]').text()).toBe('')
    expect(buttons(view).every(button => button.attributes('disabled') !== undefined)).toBe(true)
    if (outcome === 'resolve') pending.resolve()
    else pending.reject(new Error('old request denied'))
    await flushPromises()
    expect(view.get('[role="status"]').text()).toBe('')
    await buttons(view)[0]!.trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenLastCalledWith(view.props('delivery').baseRevision)
    expect(view.get('[role="status"]').text()).toBe('已复制Git 基线提交')
  })

  it('does not update a remounted component after unmount', async () => {
    const pending = deferred()
    writeText.mockReturnValueOnce(pending.promise)
    const oldView = render()
    await buttons(oldView)[0]!.trigger('click')
    oldView.unmount()
    const newView = render()
    await buttons(newView)[1]!.trigger('click')
    await flushPromises()
    if (outcome === 'resolve') pending.resolve()
    else pending.reject(new Error('unmounted request denied'))
    await flushPromises()
    expect(newView.get('[role="status"]').text()).toBe('已复制交付 ZIP SHA-256')
    expect(newView.emitted('updated')).toBeUndefined()
  })
})

it('keeps feedback across a same-version refresh and clears it when the version changes', async () => {
  const view = render()
  await buttons(view)[1]!.trigger('click')
  await flushPromises()
  await view.setProps({ delivery: structuredClone(delivery) })
  expect(view.get('[role="status"]').text()).toBe('已复制交付 ZIP SHA-256')
  await view.setProps({ delivery: { ...delivery, artifactSha256: 'c'.repeat(64) } })
  expect(view.get('[role="status"]').text()).toBe('')
})

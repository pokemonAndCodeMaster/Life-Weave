// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceOutputs from './WorkspaceOutputs.vue'
import type { ItemWorkView } from '../../api/workView'
import type { WorkItem } from '../../types'
import * as lifeweave from '../../api/lifeweave'
import * as development from '../../api/development'

vi.mock('../../api/lifeweave', () => ({ getEntityDetail: vi.fn(), getRun: vi.fn(), apiError: (error: unknown) => ({ message: String(error) }) }))
vi.mock('../../api/development', () => ({ getDevelopmentDelivery: vi.fn(), getDevelopmentDiff: vi.fn() }))

const item = { id: 'item-1', state: 'in_progress', evidence: [], artifacts: [] } as unknown as WorkItem
const base: ItemWorkView = {
  itemId: 'item-1', itemVersion: 1, current: { state: 'in_progress', label: '进行中', summary: '已登记成果' },
  plan: { id: 'p', title: '步骤', provider: 'manual', source: 'declared', version: 1, editable: true, nodes: [] },
  outputs: [
    { id: 'artifact:one', title: '人工报告一', kind: 'artifact', summary: '人工摘要一', artifactId: 'one' },
    { id: 'artifact:two', title: '人工报告二', kind: 'artifact', summary: '人工摘要二', artifactId: 'two' },
  ], warnings: [],
}
const stubs = { ResearchOutputPanel: true, ResearchKnowledgeReview: true, ManualResultEditor: true, DevelopmentDelivery: true }
beforeEach(() => vi.clearAllMocks())

describe('统一成果阅读', () => {
  it('没有目录成果但已有验证证据时仍可审阅和接受', async () => {
    const evidenceOnly = { ...item, evidence: [{ id: 'evidence-one', name: '真实工作核验', result: '已证明' }] } as WorkItem
    const view = mount(WorkspaceOutputs, { props: { workspace: 'personal', item: evidenceOnly,
      view: { ...base, outputs: [] }, selectedId: null }, global: { stubs } })
    await flushPromises()
    expect(view.find('.acceptance').exists()).toBe(true)
    expect(view.find('.acceptance').text()).toContain('真实工作核验')
    expect(view.find('.acceptance').text()).toContain('接受本轮结果')
    view.unmount()
  })

  it('人工成果在同一阅读区呈现正文，切换时忽略迟到正文', async () => {
    let resolveOne!: (value: unknown) => void
    vi.mocked(lifeweave.getEntityDetail).mockImplementation((_workspace, id) => id === 'one'
      ? new Promise(done => { resolveOne = done })
      : Promise.resolve({ payload: { body: '# 第二份正文' } }))
    const view = mount(WorkspaceOutputs, { props: { workspace: 'personal', item, view: base, selectedId: 'artifact:one' }, global: { stubs } })
    await view.setProps({ selectedId: 'artifact:two' }); await flushPromises()
    resolveOne({ payload: { body: '# 第一份迟到正文' } }); await flushPromises()
    expect(view.find('.output-reader').text()).toContain('第二份正文')
    expect(view.find('.output-reader').text()).not.toContain('第一份迟到正文')
    expect(lifeweave.getEntityDetail).toHaveBeenCalledWith('personal', 'two')
    view.unmount()
  })

  it('开发交付即使带旧 artifactId，也走开发交付读取而不是实体接口', async () => {
    vi.mocked(development.getDevelopmentDelivery).mockResolvedValue({ id: 'delivery-1' } as never)
    vi.mocked(lifeweave.getRun).mockResolvedValue(null as never)
    const view = mount(WorkspaceOutputs, { props: {
      workspace: 'personal', item,
      view: { ...base, outputs: [{ id: 'delivery:assignment-1', title: '交付', kind: 'development', summary: '固定交付', assignmentId: 'assignment-1', artifactId: 'delivery-1' }] },
      selectedId: 'delivery:assignment-1',
    }, global: { stubs } })
    await flushPromises()
    expect(lifeweave.getEntityDetail).not.toHaveBeenCalled()
    expect(development.getDevelopmentDelivery).toHaveBeenCalledWith('personal', 'assignment-1')
    view.unmount()
  })
})

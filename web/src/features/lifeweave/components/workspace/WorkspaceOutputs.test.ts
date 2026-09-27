// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceOutputs from './WorkspaceOutputs.vue'
import type { ItemWorkView } from '../../api/workView'
import type { WorkItem } from '../../types'
import { getOutputCatalog } from '../../api/outputFiles'
import { getDevelopmentDelivery } from '../../api/development'
import { getEntityDetail } from '../../api/lifeweave'

vi.mock('../../api/outputFiles', () => ({ getOutputCatalog: vi.fn(), getOutputFile: vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ getEntityDetail: vi.fn(), getRun: vi.fn(), apiError: (error: unknown) => ({ message: String(error) }) }))
vi.mock('../../api/development', () => ({ getDevelopmentDelivery: vi.fn() }))

const item = { id: 'item-1', state: 'in_progress', evidence: [], artifacts: [] } as unknown as WorkItem
const base: ItemWorkView = {
  itemId: 'item-1', itemVersion: 1, current: { state: 'in_progress', label: '进行中', summary: '已登记成果' },
  plan: { id: 'p', title: '步骤', provider: 'manual', source: 'declared', version: 1, editable: true, nodes: [] },
  outputs: [{ id: 'delivery:dev-1', title: '代码交付', kind: 'development', summary: '改进阅读', assignmentId: 'dev-1', version: 'v1' }], warnings: [],
}
const stubs = { ResearchOutputPanel: true, ResearchKnowledgeReview: true, ManualResultEditor: true, DevelopmentDelivery: true }
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getOutputCatalog).mockResolvedValue({ outputId: 'delivery:dev-1', title: '代码交付', version: 'v1', files: [
    { path: 'src/read.ts', category: 'code', status: 'modified', additions: 3, deletions: 1, binary: false, size: 100, contentType: 'text/plain' },
  ] })
})

describe('统一成果阅读', () => {
  it('没有目录成果但已有验证证据时仍可审阅和接受', async () => {
    const evidenceOnly = { ...item, evidence: [{ id: 'evidence-one', name: '真实工作核验', result: '已证明' }] } as WorkItem
    const view = mount(WorkspaceOutputs, { props: { workspace: 'personal', item: evidenceOnly, view: { ...base, outputs: [] }, selectedId: null }, global: { stubs } })
    await flushPromises()
    expect(view.find('.acceptance').text()).toContain('真实工作核验')
    view.unmount()
  })

  it('默认先显示固定分类目录，执行正文与验收详情需要用户展开', async () => {
    const wrapper = mount(WorkspaceOutputs, { props: { workspace: 'personal', item, view: base, selectedId: 'delivery:dev-1' }, global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('代码变更')
    expect(wrapper.text()).toContain('1 文件 · +3 / −1')
    expect(getOutputCatalog).toHaveBeenCalledWith('personal', 'item-1', 'delivery:dev-1', 'v1')
    expect(getDevelopmentDelivery).not.toHaveBeenCalled()
    await wrapper.find('.extra-toggle').trigger('click')
    await flushPromises()
    expect(getDevelopmentDelivery).toHaveBeenCalledWith('personal', 'dev-1')
    expect(getEntityDetail).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('同一固定版本轮询不会清掉目录筛选或重取目录', async () => {
    const wrapper = mount(WorkspaceOutputs, { props: { workspace: 'personal', item, view: base, selectedId: 'delivery:dev-1' }, global: { stubs } })
    await flushPromises()
    await wrapper.find('input[type="search"]').setValue('read')
    await wrapper.setProps({ view: { ...base, outputs: [{ ...base.outputs[0]! }] } })
    await flushPromises()
    expect((wrapper.find('input[type="search"]').element as HTMLInputElement).value).toBe('read')
    expect(getOutputCatalog).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})

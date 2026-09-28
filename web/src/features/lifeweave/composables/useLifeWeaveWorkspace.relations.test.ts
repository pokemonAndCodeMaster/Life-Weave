// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getItemDetail, getWorkspaceState, mutateWorkspace } from '../api/lifeweave'
import { applyOrganizationProposal, createOrganizationProposal, getOrganizationCatalog, type OrganizationCatalog } from '../api/itemOrganization'
import type { WorkItem } from '../types'
import { useLifeWeaveWorkspace } from './useLifeWeaveWorkspace'

vi.mock('../api/lifeweave', () => ({
  apiError: (error: unknown) => ({ status: 0, message: String(error) }),
  getItemDetail: vi.fn(), getWorkspaceState: vi.fn(), mutateWorkspace: vi.fn(),
}))
vi.mock('../api/itemOrganization', () => ({
  applyOrganizationProposal: vi.fn(), createOrganizationProposal: vi.fn(), getOrganizationCatalog: vi.fn(),
}))

const item = { id: 'item-1', version: 3, payload: { parentId: 'parent-1', owner: '旧负责人', topics: ['旧专题'], domains: ['旧领域'] }, relations: [] } as unknown as WorkItem
const catalog: OrganizationCatalog = {
  workspace: 'personal',
  topics: [{ id: 'topic-old', title: '旧专题', entityType: 'topic' }, { id: 'topic-new', title: '新专题', entityType: 'topic' }],
  domains: [{ id: 'domain-old', title: '旧领域', entityType: 'domain' }, { id: 'domain-new', title: '新领域', entityType: 'domain' }],
  items: [{ id: item.id, title: '事项', status: 'open', version: 7, topicIds: ['topic-old'], domainIds: ['domain-old'], parentId: 'parent-1' }],
  unorganizedItems: [], rules: [], rulesVersion: null, proposals: [],
}
const latest = { ...item, version: 8, payload: { ...item.payload, parentId: 'parent-1', organizationReason: '保留批次字段' }, relations: [{ id: 'resource-old-relation', fromKind: 'item', fromId: item.id, toKind: 'entity', toId: 'resource-old', relationType: 'impacts' }] }
beforeEach(() => {
  vi.clearAllMocks()
  useLifeWeaveWorkspace().activeWorkspace.value = 'personal'
  vi.mocked(getOrganizationCatalog).mockResolvedValue(catalog)
  vi.mocked(createOrganizationProposal).mockResolvedValue({ id: 'proposal-1', status: 'proposed', reason: '分类', changes: [], groups: [], warnings: [], createdAt: '' })
  vi.mocked(applyOrganizationProposal).mockResolvedValue({ id: 'proposal-1', status: 'applied', reason: '分类', changes: [], groups: [], warnings: [], createdAt: '' })
  vi.mocked(getItemDetail).mockResolvedValue(latest)
  vi.mocked(getWorkspaceState).mockResolvedValue({ workspace: 'personal', items: [], ideas: [], topics: [], domains: [], resources: [], relations: [] } as never)
  vi.mocked(mutateWorkspace).mockResolvedValue({} as never)
})

describe('旧关系入口遵守事项整理批次', () => {
  it('专题和领域经建议应用，属性使用应用后的版本，资源仍走普通关系接口', async () => {
    const { saveRelations } = useLifeWeaveWorkspace()
    await saveRelations(item, { owner: '新负责人', due: null, assets: ['新资源'] }, [
      { entityId: 'topic-new', relationType: 'serves' },
      { entityId: 'domain-new', relationType: 'references' },
      { entityId: 'resource-new', relationType: 'impacts' },
    ])
    expect(createOrganizationProposal).toHaveBeenCalledWith('personal', expect.objectContaining({ changes: [expect.objectContaining({
      itemId: item.id, itemVersion: 7, topicIds: ['topic-new'], domainIds: ['domain-new'], reason: expect.stringContaining('用户在关系编辑中明确调整'),
    })] }))
    expect(applyOrganizationProposal).toHaveBeenCalledWith('personal', 'proposal-1')
    expect(mutateWorkspace).toHaveBeenCalledWith('personal', '/items/item-1', 'patch', {
      version: 8,
      payload: expect.objectContaining({ parentId: 'parent-1', organizationReason: '保留批次字段', owner: '新负责人', topics: ['新专题'], domains: ['新领域'] }),
    })
    expect(mutateWorkspace).toHaveBeenCalledWith('personal', '/relations', 'post', expect.objectContaining({ toId: 'resource-new', relationType: 'impacts' }))
    expect(mutateWorkspace).toHaveBeenCalledWith('personal', '/relations/resource-old-relation', 'delete')
    expect(vi.mocked(mutateWorkspace).mock.calls.filter((call) => call[1] === '/relations' && (call[3] as {relationType?:string})?.relationType !== 'impacts')).toHaveLength(0)
  })

  it('新建并关联专题复用同一批次，不直写专题关系', async () => {
    vi.mocked(mutateWorkspace).mockImplementation(async (_workspace, path) => path === '/entities' ? { id: 'topic-new' } as never : {} as never)
    const { createEntity } = useLifeWeaveWorkspace()
    await createEntity('topic', '新专题', {}, item)
    expect(createOrganizationProposal).toHaveBeenCalledWith('personal', expect.objectContaining({ changes: [expect.objectContaining({ itemId: item.id, itemVersion: 7, topicIds: ['topic-old', 'topic-new'] })] }))
    expect(mutateWorkspace).toHaveBeenCalledWith('personal', '/items/item-1', 'patch', { version: 8, payload: expect.objectContaining({ parentId: 'parent-1', topics: ['旧专题', '新专题'] }) })
    expect(vi.mocked(mutateWorkspace).mock.calls.some((call) => call[1] === '/relations')).toBe(false)
  })

  it('新建并关联领域只改变领域轴，保留原专题和父事项', async () => {
    vi.mocked(mutateWorkspace).mockImplementation(async (_workspace, path) => path === '/entities' ? { id: 'domain-new' } as never : {} as never)
    await useLifeWeaveWorkspace().createEntity('domain', '新领域', {}, item)
    expect(createOrganizationProposal).toHaveBeenCalledWith('personal', expect.objectContaining({ changes: [expect.objectContaining({
      itemId: item.id, itemVersion: 7, domainIds: ['domain-old', 'domain-new'],
    })] }))
    expect(vi.mocked(createOrganizationProposal).mock.calls[0]?.[1].changes?.[0]).not.toHaveProperty('topicIds')
    expect(mutateWorkspace).toHaveBeenCalledWith('personal', '/items/item-1', 'patch', { version: 8, payload: expect.objectContaining({ parentId: 'parent-1', topics: ['旧专题'], domains: ['旧领域', '新领域'] }) })
    expect(vi.mocked(mutateWorkspace).mock.calls.some((call) => call[1] === '/relations')).toBe(false)
  })
})

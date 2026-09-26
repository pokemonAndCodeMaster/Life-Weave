import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import KnowledgeRelations from './KnowledgeRelations.vue'

vi.mock('../api/library', () => ({
  links: vi.fn().mockResolvedValue({
    sourceId: 'local', path: '研究/GSSM.md', version: 'v1', scannedDocuments: 3,
    outgoing: [
      { sourceId: 'local', path: '研究/Drive1.0.md', label: 'Drive1.0', href: 'Drive1.0.md', status: 'valid', count: 2 },
      { sourceId: 'local', path: '研究/缺失.md', label: '旧笔记', href: '缺失.md', status: 'missing', count: 1 },
      { sourceId: 'local', path: null, label: '越界', href: '../../私有.md', status: 'blocked', count: 1 },
    ],
    backlinks: [{ sourceId: 'local', path: '研究/索引.md', title: '研究索引', label: 'GSSM', count: 1 }],
    unavailableSources: [], unavailableDocuments: [],
  }),
}))

describe('KnowledgeRelations', () => {
  it('lets readers follow current Markdown relations while marking broken and blocked targets', async () => {
    const wrapper = mount(KnowledgeRelations, {
      props: { workspace: 'personal', sourceId: 'local', path: '研究/GSSM.md', version: 'v1' },
      global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="JSON.stringify(to)"><slot /></a>' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('从 3 篇当前可读文档生成')
    expect(wrapper.text()).toContain('目标文件不存在')
    expect(wrapper.text()).toContain('超出知识目录或不可读取')
    const links = wrapper.findAll('a')
    expect(links.map(link => link.text())).toEqual(['Drive1.0', '研究索引'])
    expect(links[0]?.attributes('href')).toContain('Drive1.0.md')
    expect(links[1]?.attributes('href')).toContain('索引.md')
  })
})

// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkOutputCatalog from './WorkOutputCatalog.vue'
import { getOutputCatalog, getOutputFile, type OutputCatalogFile } from '../../api/outputFiles'

vi.mock('../../api/outputFiles', () => ({ getOutputCatalog: vi.fn(), getOutputFile: vi.fn() }))
vi.mock('../../api/lifeweave', () => ({ apiError: (error: unknown) => ({ message: String(error) }) }))

const code = (path: string): OutputCatalogFile => ({
  path, category: 'code', status: 'modified', additions: 2, deletions: 1,
  binary: false, size: 120, contentType: 'text/plain',
})
const files: OutputCatalogFile[] = Array.from({ length: 320 }, (_, index) => code(`src/dir${Math.floor(index / 10)}/file${index}.ts`))
files.push({ ...code('src/新目录/新文件.ts'), previousPath: 'old/旧文件.ts', status: 'renamed', additions: 1, deletions: 0 })
files.push({ path: 'images/plot.png', category: 'attachment', status: 'added', additions: null, deletions: null, binary: true, size: 4900, contentType: 'image/png' })
files.push({ path: 'docs/report.md', category: 'document', status: 'added', additions: 24, deletions: 0, binary: false, size: 400, contentType: 'text/markdown', documentRef: { itemId: 'item-1', outputId: 'delivery:dev-1', path: 'docs/report.md', version: 'v1' } })

beforeEach(() => {
  sessionStorage.clear()
  vi.clearAllMocks()
  vi.mocked(getOutputCatalog).mockResolvedValue({ outputId: 'delivery:dev-1', title: '交付', version: 'v1', files })
  vi.mocked(getOutputFile).mockResolvedValue({ path: 'src/dir0/file0.ts', version: 'v1', binary: false, contentType: 'text/plain', before: 'a', after: 'b', content: 'b', diff: '-a\n+b' })
})

describe('固定产物目录', () => {
  it('完整统计数百文件，默认折叠；目录展开后才生成文件行', async () => {
    const wrapper = mount(WorkOutputCatalog, { props: { workspace: 'personal', itemId: 'item-1', outputId: 'delivery:dev-1', version: 'v1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('323 个文件')
    expect(wrapper.text()).toContain('代码变更')
    expect(wrapper.findAll('.file-button')).toHaveLength(0)
    await wrapper.findAll('.category-button')[1]!.trigger('click')
    expect(wrapper.findAll('.file-button')).toHaveLength(0)
    await wrapper.findAll('.folder-button').find(button => button.text().includes('src'))!.trigger('click')
    expect(wrapper.findAll('.file-button')).toHaveLength(0)
    await wrapper.findAll('.folder-button').find(button => button.text().includes('dir0'))!.trigger('click')
    expect(wrapper.findAll('.file-button')).toHaveLength(10)
    await wrapper.findAll('.file-button')[0]!.trigger('click')
    expect(wrapper.emitted('selectFile')?.[0]).toEqual(['src/dir0/file0.ts'])
    expect(getOutputFile).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('按路径和状态找重命名，保留旧路径、行数与固定版本，二进制不捏造行数', async () => {
    const wrapper = mount(WorkOutputCatalog, { props: { workspace: 'personal', itemId: 'item-1', outputId: 'delivery:dev-1', version: 'v1' } })
    await flushPromises()
    await wrapper.find('input[type="search"]').setValue('旧文件')
    await wrapper.find('select').setValue('renamed')
    await wrapper.findAll('.category-button')[1]!.trigger('click')
    expect(wrapper.text()).toContain('找到 1 / 323 个文件')
    expect(wrapper.find('.file-button').text()).toContain('原 old/旧文件.ts')
    expect(wrapper.find('.file-button').text()).toContain('+1 / −0')
    await wrapper.find('input[type="search"]').setValue('')
    await wrapper.find('select').setValue('added')
    await wrapper.findAll('.category-button')[2]!.trigger('click')
    await wrapper.find('.folder-button').trigger('click')
    expect(wrapper.text()).toContain('二进制 · 4900 字节')
    expect(wrapper.find('.file-button').text()).not.toContain('+0 / −0')
    wrapper.unmount()
  })

  it('文档发出固定版本引用；同版本轮询不重取目录或清除筛选', async () => {
    const props = { workspace: 'personal' as const, itemId: 'item-1', outputId: 'delivery:dev-1', version: 'v1' }
    const wrapper = mount(WorkOutputCatalog, { props })
    await flushPromises()
    await wrapper.find('input[type="search"]').setValue('report')
    await wrapper.find('.category-button').trigger('click')
    await wrapper.find('.folder-button').trigger('click')
    await wrapper.find('.file-button').trigger('click')
    expect(wrapper.emitted('readDocument')?.[0]?.[0]).toEqual(files.at(-1)!.documentRef)
    await wrapper.setProps({ ...props })
    await flushPromises()
    expect(wrapper.find('input[type="search"]').element).toHaveProperty('value', 'report')
    expect(getOutputCatalog).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    const returned = mount(WorkOutputCatalog, { props: { ...props, selectedPath: 'docs/report.md' } })
    await flushPromises()
    expect((returned.find('input[type="search"]').element as HTMLInputElement).value).toBe('report')
    expect(returned.find('.file-button.selected').text()).toContain('report.md')
    returned.unmount()
  })
})

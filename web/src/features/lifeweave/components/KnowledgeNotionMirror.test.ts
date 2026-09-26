// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { http } from '@/shared/api/http'
import KnowledgeNotionMirror from './KnowledgeNotionMirror.vue'
import type { Document } from '../api/library'

vi.mock('@/shared/api/http', () => ({ http: { get: vi.fn(), post: vi.fn() } }))
const document: Document = { path: 'docs/plugin-system.md', sourceId: 'lifeweave-project',
  title: '插件说明', content: '# 插件', version: 'a'.repeat(64), writable: false, sourceTitle: 'LifeWeave 项目' }
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(http.get).mockImplementation(async url => ({ data: url.endsWith('/settings')
    ? { configured: true } : { 'project:docs/plugin-system.md': { status: 'confirmed', version: 'b'.repeat(64), url: 'https://notion.so/page' } } }) as never)
  vi.mocked(http.post).mockResolvedValue({ data: { status: 'confirmed', version: document.version, url: 'https://notion.so/page' } })
})

it('shows source drift and publishes only the fixed selected version', async () => {
  const view = mount(KnowledgeNotionMirror, { props: { workspace: 'personal', document },
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  expect(view.text()).toContain('当前原文已变化')
  await view.find('button').trigger('click')
  await flushPromises()
  expect(http.post).toHaveBeenCalledWith('/lifeweave/personal/notion-mirror/document', {
    sourceId: 'lifeweave-project', path: 'docs/plugin-system.md', expectedVersion: document.version,
  })
  expect(view.text()).toContain('与当前原文相同')
  expect(view.text()).toContain('已发布并回读确认')
})

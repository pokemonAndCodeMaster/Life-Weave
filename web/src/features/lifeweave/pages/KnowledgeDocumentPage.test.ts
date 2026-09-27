// @vitest-environment jsdom
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import KnowledgePage from './KnowledgePage.vue'
import * as library from '../api/library'
vi.mock('../api/library',()=>({workOutputDocument:vi.fn(),document:vi.fn(),documents:vi.fn(),sources:vi.fn(),revisions:vi.fn(),propose:vi.fn(),decide:vi.fn()}))
vi.mock('../composables/useLifeWeaveWorkspace',async()=>{const {ref}=await import('vue');return {useLifeWeaveWorkspace:()=>({activeWorkspace:ref('personal')})}})
const document:library.Document={kind:'artifact',sourceId:'work-output',sourceTitle:'固定交付',title:'方案',path:'docs/plan.md',content:'# 第一次交付正文',version:'v1',writable:false,itemId:'i',outputId:'o',references:{links:{},images:{},warnings:[]},currentSource:{sourceId:'project',path:'docs/plan.md'}}
async function page(query:Record<string,string>) {
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/lifeweave/personal/knowledge',component:KnowledgePage},{path:'/lifeweave/personal/items/:id/overview',component:{template:'<div>步骤</div>'}}]})
 await router.push({path:'/lifeweave/personal/knowledge',query});await router.isReady()
 const wrapper=mount(KnowledgePage,{global:{plugins:[router],stubs:{PageHeader:{props:['title'],template:'<header><h1>{{title}}</h1><slot/></header>'},MarkdownBody:{props:['content'],template:'<div class="document-test-body">{{content}}</div>'},KnowledgeRelations:true,KnowledgeSemanticRelations:true,KnowledgeNotionMirror:true}}})
 await flushPromises();return {wrapper,router}
}
beforeEach(()=>{vi.resetAllMocks();vi.mocked(library.workOutputDocument).mockResolvedValue(document);vi.mocked(library.document).mockResolvedValue({...document,kind:'knowledge',sourceId:'project',content:'# 当前原文'});vi.mocked(library.documents).mockResolvedValue({items:[],unavailableSources:[]});vi.mocked(library.sources).mockResolvedValue([]);vi.mocked(library.revisions).mockResolvedValue([])})
describe('versioned work output reading in knowledge route',()=>{
 it('reads the requested fixed identity, keeps return and bundle links, and separates current source',async()=>{
  const back='/lifeweave/personal/items/i/overview?step=design&output=o&file=docs%2Fplan.md'
  const {wrapper,router}=await page({item:'i',output:'o',path:'docs/plan.md',version:'v1',returnTo:back})
  expect(library.workOutputDocument).toHaveBeenCalledWith('personal','i','o','docs/plan.md','v1')
  expect(library.documents).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('第一次交付正文')
  expect(wrapper.text()).not.toContain('提出修订')
  expect(wrapper.findAll('a').find(a=>a.text()==='返回原步骤')?.attributes('href')).toBe(back)
  const bundle=wrapper.findAll('a').find(a=>a.text()==='下载完整包（含资源）')!
  expect(bundle.attributes('href')).toContain('/items/i/outputs/bundle?outputId=o&version=v1')
  await wrapper.findAll('button').find(b=>b.text()==='查看当前原文')!.trigger('click');await flushPromises()
  expect(router.currentRoute.value.query).toEqual({source:'project',path:'docs/plan.md',returnTo:back})
  expect(wrapper.text()).toContain('当前原文')
  wrapper.unmount()
 })
 it('ignores an old document response after selecting another fixed version',async()=>{
  let resolve!:(value:library.Document)=>void
  vi.mocked(library.workOutputDocument).mockImplementationOnce(()=>new Promise(done=>{resolve=done})).mockResolvedValueOnce({...document,version:'v2',content:'# 第二次正文'})
  const {wrapper,router}=await page({item:'i',output:'o',path:'docs/plan.md',version:'v1'})
  await router.push({query:{item:'i',output:'o',path:'docs/plan.md',version:'v2'}});await flushPromises()
  resolve(document);await flushPromises()
  expect(wrapper.text()).toContain('第二次正文');expect(wrapper.text()).not.toContain('第一次交付正文');wrapper.unmount()
 })
 it('explains version mismatch and does not silently read current knowledge',async()=>{
  vi.mocked(library.workOutputDocument).mockRejectedValue({status:409,message:'Request failed with status code 409',response:{status:409,data:{detail:'指定版本不匹配，请返回产物目录'}}})
  const {wrapper}=await page({item:'i',output:'o',path:'docs/plan.md',version:'missing'})
  expect(wrapper.find('[role="alert"]').text()).toBe('指定版本不匹配，请返回产物目录')
  expect(library.document).not.toHaveBeenCalled();expect(wrapper.find('.document-test-body').exists()).toBe(false);wrapper.unmount()
 })
 it('does not show a delayed current-source warning in a fixed artifact',async()=>{
  let resolve!:(value:{items:library.Document[];unavailableSources:string[]})=>void
  vi.mocked(library.documents).mockImplementationOnce(()=>new Promise(done=>{resolve=done}))
  const {wrapper,router}=await page({source:'project',path:'docs/plan.md'})
  await router.push({query:{item:'i',output:'o',path:'docs/plan.md',version:'v1'}});await flushPromises()
  resolve({items:[],unavailableSources:['迟到来源']});await flushPromises()
  expect(wrapper.text()).toContain('第一次交付正文');expect(wrapper.text()).not.toContain('迟到来源');wrapper.unmount()
 })
})

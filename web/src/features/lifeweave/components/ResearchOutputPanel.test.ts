// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ResearchOutputPanel from './ResearchOutputPanel.vue'
import ResearchKnowledgeReview from './ResearchKnowledgeReview.vue'
import * as research from '../api/research'
import * as library from '../api/library'
vi.mock('../api/research',()=>({getResearchOutput:vi.fn(),getResearchOutputVersions:vi.fn(),getResearchOutputVersion:vi.fn(),getKnowledgeCandidates:vi.fn(),saveOutputFeedback:vi.fn(),proposeKnowledge:vi.fn()}))
vi.mock('../api/library',()=>({document:vi.fn(),decide:vi.fn()}))
vi.mock('@/shared/api/http',()=>({http:{get:vi.fn().mockResolvedValue({data:{}})}}))
const output:research.ResearchOutput={id:'run-1',kind:'run',runId:'run-1',title:'成果',content:'# 成果\n\n正文',version:'v1',state:'succeeded',createdAt:'2026-09-19T00:00:00Z',sourceBase:null,assetBase:null,downloadUrl:null}
const candidate:research.KnowledgeCandidate={id:'revision-1',itemId:'item-1',runId:'run-1',runVersion:'v1',sourceUrl:'/source',source_id:'local',path:'note.md',content:'建议',before_content:'旧文',diff:'-旧文\n+建议',reason:'说明',status:'draft',created_at:'2026-09-19',base_version:'base1'}
beforeEach(()=>{vi.resetAllMocks();vi.mocked(research.getResearchOutput).mockResolvedValue({current:output,versions:[output]});vi.mocked(research.getKnowledgeCandidates).mockResolvedValue([candidate]);vi.mocked(library.document).mockResolvedValue({sourceId:'local',sourceTitle:'本地',path:'note.md',title:'正文',content:'原文',version:'base2',writable:true})})
function button(wrapper:ReturnType<typeof mount>,text:string){return wrapper.findAll('button').find(b=>b.text()===text)!}
describe('研究操作的结果不确定和切换事项',()=>{
 it('反馈重试复用请求标识，修改反馈后产生新标识',async()=>{
  vi.mocked(research.saveOutputFeedback).mockRejectedValue(new Error('响应丢失'))
  const view=mount(ResearchOutputPanel,{props:{workspace:'personal',itemId:'item-1'}});await flushPromises()
  await view.find('textarea').setValue('训练数据解释不足')
  await view.find('form').trigger('submit');await flushPromises()
  await view.find('form').trigger('submit');await flushPromises()
  const calls=vi.mocked(research.saveOutputFeedback).mock.calls
  expect(calls[0]![2].requestId).toBe(calls[1]![2].requestId)
  await view.find('textarea').setValue('修改后的反馈');await view.find('form').trigger('submit');await flushPromises()
  expect(calls[2]![2].requestId).not.toBe(calls[1]![2].requestId);view.unmount()
 })
 it('候选重试复用请求标识，不确定时保留表单',async()=>{
  vi.mocked(research.proposeKnowledge).mockRejectedValue(new Error('响应丢失'))
  const view=mount(ResearchOutputPanel,{props:{workspace:'personal',itemId:'item-1'}});await flushPromises()
  await button(view,'从当前成果提出知识修订').trigger('click')
  await view.findAll('form')[1]!.trigger('submit');await flushPromises()
  await view.findAll('form')[1]!.trigger('submit');await flushPromises()
  const calls=vi.mocked(research.proposeKnowledge).mock.calls
  expect(calls[0]![2].requestId).toBe(calls[1]![2].requestId)
  expect(view.findAll('form')).toHaveLength(2);view.unmount()
 })
 it('旧事项反馈完成后不清空新事项草稿或冒出成功回执',async()=>{
  let resolve!:(value:unknown)=>void
  vi.mocked(research.saveOutputFeedback).mockReturnValue(new Promise(done=>{resolve=done}))
  const view=mount(ResearchOutputPanel,{props:{workspace:'personal',itemId:'item-1'}});await flushPromises()
  await view.find('textarea').setValue('旧反馈');await view.find('form').trigger('submit')
  await view.setProps({itemId:'item-2'});await flushPromises();await view.find('textarea').setValue('新事项草稿')
  resolve({});await flushPromises()
  expect((view.find('textarea').element as HTMLTextAreaElement).value).toBe('新事项草稿')
  expect(view.emitted('feedback-saved')).toBeUndefined();expect(view.text()).not.toContain('反馈已保存');view.unmount()
 })
 it('冲突合并重试也保留请求标识',async()=>{
  vi.mocked(research.proposeKnowledge).mockRejectedValue(new Error('响应丢失'))
  const view=mount(ResearchKnowledgeReview,{props:{workspace:'personal',itemId:'item-1'}});await flushPromises()
  await button(view,'读取最新原文并重新合并').trigger('click');await flushPromises()
  await view.find('form').trigger('submit');await flushPromises();await view.find('form').trigger('submit');await flushPromises()
  const calls=vi.mocked(research.proposeKnowledge).mock.calls
  expect(calls[0]![2].requestId).toBe(calls[1]![2].requestId)
  expect(calls[0]![2].baseVersion).toBe('base2');view.unmount()
 })
 it('受控成果可展开历史版本，反馈绑定当前选中的历史运行；切换外层成果后重置选择',async()=>{
  const old={...output,id:'run-old',runId:'run-old',content:'# 旧版正文',version:'v0',createdAt:'2026-09-18T00:00:00Z'}
  vi.mocked(research.getResearchOutputVersions).mockResolvedValue({versions:[output,old]})
  vi.mocked(research.getResearchOutputVersion).mockImplementation(async (_workspace,_item,id)=>id==='run-old'?old:output)
  vi.mocked(research.saveOutputFeedback).mockResolvedValue({} as never)
  const view=mount(ResearchOutputPanel,{props:{workspace:'personal',itemId:'item-1',selectedRunId:'run-1',compact:true}});await flushPromises()
  expect(research.getResearchOutputVersion).toHaveBeenCalledWith('personal','item-1','run-1')
  expect(research.getResearchOutput).not.toHaveBeenCalled()
  expect(research.getResearchOutputVersions).not.toHaveBeenCalled()
  expect(view.text()).toContain('正文')
  expect(view.text()).not.toContain('旧版正文')
  const history=view.find('details.research-history')
  expect(history.exists()).toBe(true)
  ;(history.element as HTMLDetailsElement).open=true
  await history.trigger('toggle');await flushPromises()
  expect(research.getResearchOutputVersions).toHaveBeenCalledOnce()
  await history.findAll('button')[1]!.trigger('click')
  await flushPromises()
  expect(view.text()).toContain('旧版正文')
  await view.find('textarea').setValue('旧版反馈')
  await view.find('form').trigger('submit');await flushPromises()
  expect(vi.mocked(research.saveOutputFeedback).mock.calls[0]![2].runId).toBe('run-old')
  await view.setProps({selectedRunId:'run-old'});await flushPromises()
  await view.setProps({selectedRunId:'run-1'});await flushPromises()
  expect(view.text()).toContain('正文')
  expect(view.text()).not.toContain('旧版正文')
  expect(research.getResearchOutputVersion).toHaveBeenLastCalledWith('personal','item-1','run-1')
  view.unmount()
 })
 it('快速切换历史版本时忽略迟到正文',async()=>{
  const oldA={...output,id:'run-a',runId:'run-a',content:'# A 正文'}
  const oldB={...output,id:'run-b',runId:'run-b',content:'# B 正文'}
  let resolveA!:(value:research.ResearchOutput)=>void
  vi.mocked(research.getResearchOutputVersion).mockImplementation((_workspace,_item,id)=>id==='run-a'?new Promise(done=>{resolveA=done}):Promise.resolve(id==='run-b'?oldB:output))
  vi.mocked(research.getResearchOutputVersions).mockResolvedValue({versions:[output,oldA,oldB]})
  const view=mount(ResearchOutputPanel,{props:{workspace:'personal',itemId:'item-1',selectedRunId:'run-1',compact:true}});await flushPromises()
  const history=view.find('details.research-history');(history.element as HTMLDetailsElement).open=true
  await history.trigger('toggle');await flushPromises()
  await history.findAll('button')[1]!.trigger('click')
  await history.findAll('button')[2]!.trigger('click');await flushPromises()
  resolveA(oldA);await flushPromises()
  expect(view.text()).toContain('B 正文')
  expect(view.text()).not.toContain('A 正文')
  view.unmount()
 })
})

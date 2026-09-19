<script setup lang="ts">
import ResearchArchiveStatus from './ResearchArchiveStatus.vue'
import { computed, reactive, shallowRef, watch } from 'vue'
import MarkdownBody from './MarkdownBody.vue'
import * as research from '../api/research'
import * as library from '../api/library'
import { apiError } from '../api/lifeweave'
import { downloadText } from '../utils/download'
import type { WorkspaceKind } from '../types'
const props=defineProps<{workspace:WorkspaceKind;itemId:string;refreshKey?:number}>()
const emit=defineEmits<{'feedback-saved':[];'candidate-created':[];quote:[value:{text:string;runId:string|null;anchor:string} ]}>()
const outputs=shallowRef<research.ResearchOutputs>({current:null,versions:[]})
const selectedId=shallowRef('');const error=shallowRef('');const message=shallowRef('');const busy=shallowRef(false)
const quote=shallowRef('');const anchor=shallowRef('');const feedback=shallowRef('');const editing=shallowRef(false)
const form=reactive({path:'',content:'',reason:'从研究成果提炼可复用知识',baseVersion:'new'})
const selected=computed(()=>outputs.value.versions.find(out=>out.id===selectedId.value)??outputs.value.current)
let generation=0
let scopeGeneration=0
let loadedScope=''
const pendingRequests=new Map<string,{signature:string;id:string}>()
function requestId(kind:string,payload:unknown){const signature=JSON.stringify([props.workspace,props.itemId,payload]);const existing=pendingRequests.get(kind);if(existing?.signature===signature)return existing.id;const id=crypto.randomUUID();pendingRequests.set(kind,{signature,id});return id}
watch([()=>props.workspace,()=>props.itemId,()=>props.refreshKey],async()=>{
 const token=++generation;error.value=''
 const scope=props.workspace,id=props.itemId
 if(loadedScope!==scope+':'+id){
  loadedScope=scope+':'+id;message.value='';quote.value='';anchor.value='';editing.value=false
  outputs.value={current:null,versions:[]};selectedId.value='';pendingRequests.clear()
 }
 try{const result=await research.getResearchOutput(scope,id);if(token===generation)outputs.value=result}
 catch(e){if(token===generation)error.value=apiError(e).message}
},{immediate:true})
function scopeKey(){return `${props.workspace}:${props.itemId}:${selected.value?.id}:${selected.value?.version}`}
watch(scopeKey,()=>{scopeGeneration++;quote.value='';anchor.value='';feedback.value='';editing.value=false;busy.value=false;pendingRequests.clear()},{flush:'sync'})
async function action(fn:(current:()=>boolean)=>Promise<void>){
 const key=scopeKey(),token=scopeGeneration;const current=()=>key===scopeKey()&&token===scopeGeneration
 busy.value=true;error.value='';message.value=''
 try{await fn(current)}catch(e){if(current())error.value=apiError(e).message}finally{if(current())busy.value=false}
}
function capture(event:Event){
 const selection=window.getSelection();const host=event.currentTarget as HTMLElement
 if(!selection?.rangeCount||!host.contains(selection.anchorNode)||!host.contains(selection.focusNode))return
 const fragment=selection.getRangeAt(0).cloneContents()
 for(const formula of fragment.querySelectorAll('.katex')){
  const latex=formula.querySelector('annotation[encoding="application/x-tex"]')?.textContent
  if(latex)formula.replaceWith(document.createTextNode('$'+latex+'$'))
 }
 const text=(fragment.textContent||selection.toString()).trim();if(!text)return
 quote.value=text.slice(0,4000);anchor.value=`${selected.value?.id}:${selected.value?.version.slice(0,12)}:${text.slice(0,150)}`.slice(0,256)
}
function startKnowledge(){if(!selected.value)return;form.path=`研究/${props.itemId}.md`;form.content=quote.value||selected.value.content;form.baseVersion='new';editing.value=true}
async function saveKnowledge(){await action(async(current)=>{
 const runId=selected.value?.runId;if(!runId)return
 const payload={...form,runId}
 await research.proposeKnowledge(props.workspace,props.itemId,{...payload,requestId:requestId('candidate',payload)})
 if(!current())return
 pendingRequests.delete('candidate');editing.value=false;message.value='知识候选已保存，请在下方比较差异后决定是否接受。';emit('candidate-created')
})}
async function loadBase(){await action(async(current)=>{
 const path=form.path;const doc=await library.document(props.workspace,path)
 if(!current()||path!==form.path)return
 form.baseVersion=doc.version
 message.value='已读取当前知识版本；请保留需要的原文后再提交。';form.content=doc.content+'\n\n'+(quote.value||selected.value?.content||'')
})}
async function sendFeedback(){await action(async(current)=>{
 const payload={body:(quote.value?`引用成果：\n> ${quote.value.replaceAll('\n','\n> ')}\n\n`:'')+feedback.value,runId:selected.value?.runId??null,anchor:anchor.value||`${selected.value?.id}:${selected.value?.version}`}
 await research.saveOutputFeedback(props.workspace,props.itemId,{...payload,requestId:requestId('feedback',payload)})
 if(!current())return
 pendingRequests.delete('feedback');feedback.value='';message.value='反馈已保存，下一轮委托会读取这条反馈。';emit('feedback-saved')
})}
</script>
<template>
 <section class="research-output lw-stack" aria-label="研究成果">
  <div class="lw-between"><h2>当前成果</h2><select v-if="outputs.versions.length" v-model="selectedId" aria-label="成果版本"><option value="">当前成果</option><option v-for="out in outputs.versions" :key="out.id" :value="out.id">{{ out.kind==='manual'?'人工成果':out.state==='succeeded'?'完成的运行':'未完成的运行' }} · {{ new Date(out.createdAt).toLocaleString() }}</option></select></div>
  <p v-if="error" role="alert" class="lw-notice warning">{{ error }}</p><p v-if="message" role="status" class="lw-notice">{{ message }}</p>
  <template v-if="selected">
   <p v-if="selected.storageNote" class="lw-notice warning">{{ selected.storageNote }} <a v-if="selected.rawDownloadUrl" :href="selected.rawDownloadUrl" download="原始执行文本.txt">下载原始执行文本</a></p>
   <div class="lw-between"><span class="lw-small lw-muted">{{ selected.kind==='manual'?'人工提交':'运行成果' }} · 版本 {{ selected.version.slice(0,12) }}<template v-if="selected.state!=='succeeded'&&selected.kind==='run'"> · {{ selected.state }}，保留的部分结果</template></span><button class="lw-btn sm" @click="downloadText(selected!.content,'研究成果.md','text/markdown;charset=utf-8')">仅下载 Markdown</button><a v-if="selected.bundleUrl&&selected.state==='succeeded'" class="lw-btn sm" :href="selected.bundleUrl" download>下载完整包（含图片）</a></div>
   <ResearchArchiveStatus v-if="selected.runId&&selected.state==='succeeded'" :workspace="workspace" :run-id="selected.runId" />
   <article @mouseup="capture" @keyup="capture"><MarkdownBody :content="selected.content" :source-base="selected.sourceBase??undefined" :asset-base="selected.assetBase??undefined"/></article>
   <div class="lw-stack research-feedback"><p class="lw-small lw-muted">选中正文中的一段文字，留下定位反馈或引用到讨论。</p><blockquote v-if="quote">{{ quote }}</blockquote>
    <button v-if="quote" class="lw-btn sm" @click="emit('quote',{text:quote,runId:selected.runId,anchor})">引用到讨论</button>
    <form class="lw-stack" @submit.prevent="sendFeedback"><label class="lw-label">对这份成果的反馈<textarea v-model="feedback" :disabled="busy" class="lw-field" required maxlength="80000" rows="3" placeholder="指出需要补充或修正的内容"></textarea></label><button class="lw-btn" :disabled="busy||!feedback.trim()">保存反馈，供下一轮使用</button></form>
    <button v-if="selected.runId&&selected.state==='succeeded'" class="lw-btn" :disabled="busy" @click="startKnowledge">从当前成果提出知识修订</button>
   </div>
   <form v-if="editing" class="lw-stack research-feedback" @submit.prevent="saveKnowledge"><h3>整理为知识候选</h3><label class="lw-label">知识文件路径<input v-model="form.path" :disabled="busy" class="lw-field" required maxlength="1000"/></label><button type="button" class="lw-btn sm" :disabled="busy" @click="loadBase">读取已有知识并准备合并</button><p class="lw-small lw-muted">新文件可直接提交；修订已有知识时，先读取当前版本。来源随候选保存，接受前不会改动知识原文。</p><label class="lw-label">建议正文<textarea v-model="form.content" :disabled="busy" class="lw-field" required maxlength="1000000" rows="12"></textarea></label><label class="lw-label">修改说明<input v-model="form.reason" :disabled="busy" class="lw-field" required maxlength="2000"/></label><div class="lw-inline"><button class="lw-btn primary" :disabled="busy">保存候选，查看差异</button><button type="button" class="lw-btn" @click="editing=false">取消</button></div></form>
  </template>
  <p v-else class="lw-muted">尚无已完成成果。运行结束或提交人工成果后，可在这里阅读；已有部分结果可从版本列表查看。</p>
 </section>
</template>
<style scoped>
.research-output{min-width:0}.research-output article{min-width:0;line-height:1.8}.research-feedback{border-top:1px solid var(--lw-border,#e4e7ec);padding-top:1rem}.research-feedback blockquote{white-space:pre-wrap;border-left:3px solid #aac3b3;padding-left:1rem;margin:0;max-height:12rem;overflow:auto}
</style>

<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import MarkdownBody from './MarkdownBody.vue'
import { getKnowledgeCandidates, proposeKnowledge, type KnowledgeCandidate } from '../api/research'
import * as library from '../api/library'
import { apiError } from '../api/lifeweave'
import type { WorkspaceKind } from '../types'
const props=defineProps<{workspace:WorkspaceKind;itemId:string;refreshKey?:number}>()
const emit=defineEmits<{changed:[]}>()
const candidates=shallowRef<KnowledgeCandidate[]>([]);const error=shallowRef('');const busy=shallowRef(false)
const rebasing=shallowRef<KnowledgeCandidate|null>(null);const base=shallowRef('');const draft=shallowRef('')
let generation=0
let scopeGeneration=0
let loadedScope=''
let pending:{signature:string;id:string}|null=null
function scopeKey(){return `${props.workspace}:${props.itemId}`}
async function refresh(){const token=++generation,key=scopeKey();const result=await getKnowledgeCandidates(props.workspace,props.itemId);if(token===generation&&key===scopeKey())candidates.value=result}
watch([()=>props.workspace,()=>props.itemId,()=>props.refreshKey],()=>{
 if(loadedScope!==scopeKey()){scopeGeneration++;loadedScope=scopeKey();candidates.value=[];error.value='';rebasing.value=null;pending=null;busy.value=false}
 void action(async()=>refresh())
},{immediate:true})
async function action(fn:(current:()=>boolean)=>Promise<void>){
 const key=scopeKey(),token=scopeGeneration,current=()=>key===scopeKey()&&token===scopeGeneration
 busy.value=true;error.value=''
 try{await fn(current)}catch(e){if(current())error.value=apiError(e).message}finally{if(current())busy.value=false}
}
async function decide(candidate:KnowledgeCandidate,accept:boolean){await action(async(current)=>{
 await library.decide(props.workspace,candidate.id,accept)
 if(!current())return
 await refresh();if(current())emit('changed')
})}
async function prepare(candidate:KnowledgeCandidate){await action(async(current)=>{
 const doc=await library.document(props.workspace,candidate.path)
 if(!current())return
 base.value=doc.version;draft.value=doc.content+'\n\n'+candidate.content;rebasing.value=candidate;pending=null
})}
async function resubmit(){await action(async(current)=>{
 const c=rebasing.value;if(!c)return
 const payload={runId:c.runId,path:c.path,content:draft.value,baseVersion:base.value,reason:('在当前知识版本上重新合并：'+c.reason).slice(0,2000)}
 const signature=JSON.stringify([scopeKey(),payload])
 if(pending?.signature!==signature)pending={signature,id:crypto.randomUUID()}
 await proposeKnowledge(props.workspace,props.itemId,{...payload,requestId:pending.id})
 if(!current()||rebasing.value?.id!==c.id)return
 pending=null;rebasing.value=null;await refresh();if(current())emit('changed')
})}
</script>
<template>
 <section class="lw-stack research-knowledge" aria-label="知识候选审阅"><h2>知识候选与修订</h2><p v-if="error" role="alert" class="lw-notice warning">{{ error }}</p><p v-if="!candidates.length" class="lw-muted">还没有知识候选。可从成功运行的成果中提出修订。</p>
  <details v-for="candidate in candidates" :key="candidate.id" class="candidate"><summary>{{ candidate.path }} · {{ {draft:'等待审阅',accepted:'已接受',rejected:'已拒绝'}[candidate.status] }}</summary><div class="lw-stack"><p>{{ candidate.reason }}</p><a :href="candidate.sourceUrl">下载来源成果 · {{ candidate.runVersion.slice(0,12) }}</a><pre class="lw-diff">{{ candidate.diff||'正文没有变化' }}</pre><details><summary>阅读建议全文</summary><MarkdownBody :content="candidate.content"/></details><div v-if="candidate.status==='draft'" class="lw-inline"><button class="lw-btn primary" :disabled="busy" @click="decide(candidate,true)">接受并更新知识原文</button><button class="lw-btn" :disabled="busy" @click="decide(candidate,false)">拒绝修订</button><button class="lw-btn" :disabled="busy" @click="prepare(candidate)">读取最新原文并重新合并</button></div><a v-if="candidate.status==='accepted'" :href="`/lifeweave/${workspace}/knowledge?path=${encodeURIComponent(candidate.path)}&source=local`">阅读已接受知识</a></div></details>
  <form v-if="rebasing" class="lw-stack" @submit.prevent="resubmit"><h3>在最新原文上合并 {{ rebasing.path }}</h3><p class="lw-small lw-muted">下面保留最新原文并附上旧建议，请编辑成一份连贯正文后重新提交。原候选仍保留审阅记录。</p><textarea v-model="draft" :disabled="busy" class="lw-field" rows="14" required maxlength="1000000" aria-label="重新合并的知识正文"></textarea><div class="lw-inline"><button class="lw-btn primary" :disabled="busy">提交新的知识候选</button><button type="button" class="lw-btn" @click="rebasing=null">取消</button></div></form>
 </section>
</template>
<style scoped>
.research-knowledge{min-width:0}.candidate{border-top:1px solid var(--lw-border,#e4e7ec);padding:1rem 0}.candidate summary{cursor:pointer;padding:.3rem 0}.candidate pre{overflow:auto;max-height:30rem;white-space:pre-wrap;overflow-wrap:anywhere}
</style>

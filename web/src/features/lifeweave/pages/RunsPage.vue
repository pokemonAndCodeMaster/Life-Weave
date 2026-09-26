<script setup lang="ts">
import {computed,onBeforeUnmount,shallowRef,watch} from 'vue'
import {http} from '@/shared/api/http'
import {apiError,getRun,getRunEventsPage} from '../api/lifeweave'
import {useLifeWeaveWorkspace} from '../composables/useLifeWeaveWorkspace'
import type {LifeWeaveRun,RunEvent} from '../types'
import PageHeader from '../components/PageHeader.vue'
import MarkdownBody from '../components/MarkdownBody.vue'
import RunTrace from '../components/RunTrace.vue'
import {downloadText} from '../utils/download'
import {useRoute} from 'vue-router'
const route=useRoute()
const {activeWorkspace,state}=useLifeWeaveWorkspace()
const runs=shallowRef<LifeWeaveRun[]>([]);const selected=shallowRef<LifeWeaveRun|null>(null)
const result=shallowRef('');const events=shallowRef<RunEvent[]>([]);const error=shallowRef('');const busy=shallowRef(false)
const eventCursor=shallowRef(0);const eventsHaveMore=shallowRef(false);const loadingEvents=shallowRef(false)
const total=shallowRef(0);const filter=shallowRef('');let timer:ReturnType<typeof setTimeout>|undefined;let active=true
const labels:Record<string,string>={queued:'等待执行',claimed:'正在准备',running:'执行中',pause_requested:'正在暂停',paused:'已暂停',cancelling:'正在取消',cancelled:'已取消',succeeded:'待审阅结果',failed:'执行失败',unavailable:'环境不可用'}
const title=(run:LifeWeaveRun)=>state.value?.items.find(i=>i.id===run.itemId)?.title??'工作事项'
const visible=computed(()=>runs.value.filter(r=>!filter.value||r.state===filter.value))
function applyEvents(page:{items:RunEvent[];nextSequence:number},replace=false){
 const rows=replace?[]:events.value
 const unique=new Map([...rows,...page.items].map(event=>[event.sequence??event.id,event]))
 events.value=[...unique.values()].sort((a,b)=>(a.sequence??0)-(b.sequence??0))
 eventCursor.value=Math.max(eventCursor.value,page.nextSequence)
 eventsHaveMore.value=page.items.length===200
}
let generation=0
async function refresh(more=false){
 const scope=activeWorkspace.value;const ticket=generation
 try{
  const count=more?1:Math.max(1,Math.ceil(runs.value.length/100));const rows:LifeWeaveRun[]=[];let found=0
  for(let page=0;page<count;page++){
   const response=(await http.get<{items:LifeWeaveRun[];total:number}>(`/lifeweave/${scope}/runs`,{params:{limit:100,offset:more?runs.value.length:page*100,state:filter.value||undefined}})).data
   rows.push(...response.items);found=response.total
   if(response.items.length<100)break
  }
  if(ticket!==generation||!active)return
  runs.value=more?[...runs.value,...rows]:rows;total.value=found
  const selectedId=selected.value?.id
  if(selectedId){
   const [current,log]=await Promise.all([getRun(scope,selectedId),getRunEventsPage(scope,selectedId,eventCursor.value)])
   if(ticket!==generation||selected.value?.id!==selectedId)return
   selected.value=current;applyEvents(log);result.value=current.result??''
  } else if (typeof route.query.runId === 'string' && route.query.runId) {
   const requested=route.query.runId
   const [current,log]=await Promise.all([getRun(scope,requested),getRunEventsPage(scope,requested)])
   if(ticket!==generation||!active)return
   selected.value=current;eventCursor.value=0;applyEvents(log,true);result.value=current.result??''
  }
  error.value=''
 }catch(e){if(ticket===generation)error.value=apiError(e).message}
}
async function read(run:LifeWeaveRun){
 busy.value=true;result.value='';events.value=[];eventCursor.value=0;selected.value=run;const scope=activeWorkspace.value;const ticket=generation
 try{const [current,log]=await Promise.all([getRun(scope,run.id),getRunEventsPage(scope,run.id)]);if(ticket!==generation||selected.value?.id!==run.id)return;selected.value=current;result.value=current.result??'';applyEvents(log,true)}
 catch(e){if(ticket===generation)error.value=apiError(e).message}finally{busy.value=false}
}
async function act(action:string){if(!selected.value)return;busy.value=true;try{const response=await http.post<LifeWeaveRun>(`/lifeweave/${activeWorkspace.value}/runs/${selected.value.id}/${action}`,action==='retry'?{syncContext:true}:{});selected.value=response.data;result.value='';await refresh()}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
async function loadMoreEvents(){
 if(!selected.value||loadingEvents.value)return
 loadingEvents.value=true
 const id=selected.value.id;const scope=activeWorkspace.value;const ticket=generation
 try{const page=await getRunEventsPage(scope,id,eventCursor.value);if(ticket===generation&&selected.value?.id===id)applyEvents(page)}
 catch(e){if(ticket===generation)error.value=apiError(e).message}
 finally{loadingEvents.value=false}
}
async function poll(ticket:number){await refresh();if(active&&ticket===generation)timer=setTimeout(()=>void poll(ticket),4000)}
watch([activeWorkspace,filter],()=>{generation++;clearTimeout(timer);selected.value=null;result.value='';events.value=[];eventCursor.value=0;runs.value=[];void poll(generation)},{immediate:true})
watch(()=>route.query.runId,async id=>{if(typeof id==='string'&&id&&id!==selected.value?.id){try{await read(await getRun(activeWorkspace.value,id))}catch(e){error.value=apiError(e).message}}})
onBeforeUnmount(()=>{active=false;generation++;clearTimeout(timer)})
</script>
<template>
<PageHeader title="AI 委托" subtitle="执行过程、实际结果和每次尝试都留在这里。"><button class="lw-btn" @click="refresh()">刷新</button></PageHeader><p v-if="error" class="lw-notice warning" role="alert">{{error}}</p>
<div class="lw-toolbar"><select v-model="filter" aria-label="筛选运行状态"><option value="">全部状态</option><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select><span class="lw-small lw-muted">{{total}} 次委托</span></div>
<div class="lw-knowledge-grid"><aside class="lw-panel lw-knowledge-nav"><button v-for="run in visible" :key="run.id" class="lw-knowledge-link" :class="{active:selected?.id===run.id}" @click="read(run)"><span>{{title(run)}}<small>{{labels[run.state]||run.state}} · {{run.engine}} · 第 {{run.attempt}} 次</small></span></button><button v-if="runs.length<total" class="lw-btn" @click="refresh(true)">加载更多</button><div v-if="!runs.length" class="lw-empty"><h3>还没有委托</h3><p>先打开一件工作，写清目标和背景，再点“委托 AI”。</p><RouterLink class="lw-btn" :to="`/lifeweave/${activeWorkspace}/items`">打开工作事项</RouterLink></div></aside>
<article class="lw-panel lw-article"><template v-if="selected"><div class="lw-between"><span class="lw-small lw-muted">{{labels[selected.state]||selected.state}} · {{selected.engine}}</span><RouterLink class="lw-text-btn" :to="`/lifeweave/${activeWorkspace}/items/${selected.itemId}/outputs`">审阅与接受成果 →</RouterLink></div><h2>{{title(selected)}}</h2><p>{{selected.instruction}}</p><p v-if="selected.error" class="lw-notice warning">{{selected.error}}</p><div class="lw-inline"><button v-if="['queued','claimed','running','paused','pause_requested'].includes(selected.state)" class="lw-btn" :disabled="busy" @click="act('cancel')">取消委托</button><button v-if="['failed','unavailable','cancelled','paused','succeeded'].includes(selected.state)" class="lw-btn" :disabled="busy" @click="act('retry')">按当前背景再试</button><button v-if="result" class="lw-btn" @click="downloadText(result,'委托结果.md')">下载结果</button></div><hr class="lw-rule"/><MarkdownBody v-if="result" :content="result" :source-base="`/api/lifeweave/${activeWorkspace}/runs/${selected.id}/source`"/><div v-else class="lw-empty">{{['failed','unavailable'].includes(selected.state)?'执行没有产出结果，请检查失败原因后重试。':'结果尚未返回，页面会自动更新。'}}</div><details class="lw-mt-20"><summary>运行依据与过程</summary><dl class="lw-runtime-facts"><dt>工作目录</dt><dd>{{selected.directory}}</dd><dt>上下文版本</dt><dd>v{{selected.rev}}</dd><dt>会话</dt><dd>{{selected.session||'尚未建立'}}</dd></dl><RunTrace :events="events" /><button v-if="eventsHaveMore" class="lw-btn sm" type="button" :disabled="loadingEvents" @click="loadMoreEvents">{{ loadingEvents ? '正在加载…' : '加载后续事件' }}</button></details></template><div v-else class="lw-empty">选择一轮委托，查看实际结果。</div></article></div>
</template>

<script setup lang="ts">
import {computed,onBeforeUnmount,shallowRef,watch} from 'vue'
import {http} from '@/shared/api/http'
import {apiError,getRun,getRunEvents,getRunArtifactResult} from '../api/gongzuo'
import {useGongzuoWorkspace} from '../composables/useGongzuoWorkspace'
import type {GongzuoRun} from '../types'
import PageHeader from '../components/PageHeader.vue'
import MarkdownBody from '../components/MarkdownBody.vue'
import {downloadText} from '../utils/download'
const {activeWorkspace,state}=useGongzuoWorkspace()
const runs=shallowRef<GongzuoRun[]>([]);const selected=shallowRef<GongzuoRun|null>(null)
const result=shallowRef('');const events=shallowRef<unknown[]>([]);const error=shallowRef('');const busy=shallowRef(false)
const total=shallowRef(0);const filter=shallowRef('');let timer:ReturnType<typeof setTimeout>|undefined;let active=true
const labels:Record<string,string>={queued:'等待执行',claimed:'正在准备',running:'执行中',pause_requested:'正在暂停',paused:'已暂停',cancelling:'正在取消',cancelled:'已取消',succeeded:'待审阅结果',failed:'执行失败',unavailable:'环境不可用'}
const title=(run:GongzuoRun)=>state.value?.items.find(i=>i.id===run.itemId)?.title??'工作事项'
const visible=computed(()=>runs.value.filter(r=>!filter.value||r.state===filter.value))
async function refresh(more=false){try{const response=(await http.get<{items:GongzuoRun[];total:number}>(`/gongzuo/${activeWorkspace.value}/runs`,{params:{limit:100,offset:more?runs.value.length:0}})).data;runs.value=more?[...runs.value,...response.items]:response.items;total.value=response.total;if(selected.value){selected.value=await getRun(activeWorkspace.value,selected.value.id);if(!result.value&&selected.value.result)result.value=selected.value.result}error.value=''}catch(e){error.value=apiError(e).message}}
async function read(run:GongzuoRun){busy.value=true;result.value='';events.value=[];try{selected.value=await getRun(activeWorkspace.value,run.id);if(selected.value.result)result.value=(await getRunArtifactResult(activeWorkspace.value,run.id)).content;events.value=(await getRunEvents(activeWorkspace.value,run.id))??[]}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
async function act(action:string){if(!selected.value)return;busy.value=true;try{const response=await http.post<GongzuoRun>(`/gongzuo/${activeWorkspace.value}/runs/${selected.value.id}/${action}`,action==='retry'?{syncContext:true}:{});selected.value=response.data;result.value='';await refresh()}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
async function poll(){await refresh();if(active)timer=setTimeout(poll,4000)}
watch(activeWorkspace,()=>{clearTimeout(timer);selected.value=null;result.value='';void poll()},{immediate:true})
onBeforeUnmount(()=>{active=false;clearTimeout(timer)})
</script>
<template>
<PageHeader title="AI 委托" subtitle="执行过程、实际结果和每次尝试都留在这里。"><button class="gz-btn" @click="refresh()">刷新</button></PageHeader><p v-if="error" class="gz-notice warning" role="alert">{{error}}</p>
<div class="gz-toolbar"><select v-model="filter" aria-label="筛选运行状态"><option value="">全部状态</option><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select><span class="gz-small gz-muted">{{total}} 次委托</span></div>
<div class="gz-knowledge-grid"><aside class="gz-panel gz-knowledge-nav"><button v-for="run in visible" :key="run.id" class="gz-knowledge-link" :class="{active:selected?.id===run.id}" @click="read(run)"><span>{{title(run)}}<small>{{labels[run.state]||run.state}} · {{run.engine}} · 第 {{run.attempt}} 次</small></span></button><button v-if="runs.length<total" class="gz-btn" @click="refresh(true)">加载更多</button><div v-if="!runs.length" class="gz-empty"><h3>还没有委托</h3><p>先打开一件工作，写清目标和背景，再点“委托 AI”。</p><RouterLink class="gz-btn" :to="`/gongzuo/${activeWorkspace}/items`">打开工作事项</RouterLink></div></aside>
<article class="gz-panel gz-article"><template v-if="selected"><div class="gz-between"><span class="gz-small gz-muted">{{labels[selected.state]||selected.state}} · {{selected.engine}}</span><RouterLink class="gz-text-btn" :to="`/gongzuo/${activeWorkspace}/items/${selected.itemId}/outputs`">审阅与接受成果 →</RouterLink></div><h2>{{title(selected)}}</h2><p>{{selected.instruction}}</p><p v-if="selected.error" class="gz-notice warning">{{selected.error}}</p><div class="gz-inline"><button v-if="['queued','claimed','running','paused','pause_requested'].includes(selected.state)" class="gz-btn" :disabled="busy" @click="act('cancel')">取消委托</button><button v-if="['failed','unavailable','cancelled','paused','succeeded'].includes(selected.state)" class="gz-btn" :disabled="busy" @click="act('retry')">按当前背景再试</button><button v-if="result" class="gz-btn" @click="downloadText(result,'委托结果.md')">下载结果</button></div><hr class="gz-rule"/><MarkdownBody v-if="result" :content="result"/><div v-else class="gz-empty">{{['failed','unavailable'].includes(selected.state)?'执行没有产出结果，请检查失败原因后重试。':'结果尚未返回，页面会自动更新。'}}</div><details class="gz-mt-20"><summary>运行依据与过程</summary><dl class="gz-runtime-facts"><dt>工作目录</dt><dd>{{selected.directory}}</dd><dt>上下文版本</dt><dd>v{{selected.rev}}</dd><dt>会话</dt><dd>{{selected.session||'尚未建立'}}</dd></dl><pre class="gz-diff">{{JSON.stringify(events,null,2)}}</pre></details></template><div v-else class="gz-empty">选择一轮委托，查看实际结果。</div></article></div>
</template>

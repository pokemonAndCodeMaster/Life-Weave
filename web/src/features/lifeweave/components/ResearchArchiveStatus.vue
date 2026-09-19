<script setup lang="ts">
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
const props=defineProps<{workspace:string;runId:string}>()
interface Target {status:string;url?:string;error?:string;warnings?:string[]}
const state=shallowRef<Record<string,Target>>({});const error=shallowRef('');const busy=shallowRef(false)
const labels:Record<string,string>={confirmed:'已归档并回读',pending:'等待归档',sending:'正在归档',failed:'归档失败',unconfigured:'未配置'}
let generation=0;let timer:ReturnType<typeof setTimeout>|undefined
async function load(ticket:number){
 try{const r=await http.get(`/lifeweave/${props.workspace}/runs/${props.runId}/archive`);if(ticket===generation)state.value=r.data}
 catch(e){if(ticket===generation)error.value=apiError(e).message}
 if(ticket===generation)timer=setTimeout(()=>void load(ticket),10000)
}
watch(()=>[props.workspace,props.runId],()=>{generation++;clearTimeout(timer);state.value={};error.value='';busy.value=false;void load(generation)},{immediate:true})
onBeforeUnmount(()=>{generation++;clearTimeout(timer)})
async function retry(){const ticket=generation;busy.value=true;error.value='';try{await http.post(`/lifeweave/${props.workspace}/runs/${props.runId}/archive`,{},{timeout:600000});if(ticket===generation){clearTimeout(timer);await load(ticket)}}catch(e){if(ticket===generation)error.value=apiError(e).message}finally{if(ticket===generation)busy.value=false}}
</script>
<template>
 <section class="archive-state lw-notice neutral" aria-label="归档状态">
  <div class="lw-between"><strong>此版本的异地归档</strong><button class="lw-btn sm" :disabled="busy" @click="retry">{{busy?'正在核对归档…':'立即归档 / 重试'}}</button></div>
  <p class="lw-small">成功生成后按设置自动归档；电脑关机期间暂停，已上传版本仍可在远端阅读。<RouterLink :to="`/lifeweave/${workspace}/settings`">归档设置</RouterLink></p>
  <p v-for="key in ['local','github','linear']" :key="key" class="lw-small"><strong>{{key==='local'?'本机完整包':key==='github'?'GitHub':'Linear'}}：</strong>{{labels[state[key]?.status||'pending']}} <a v-if="state[key]?.url" :href="state[key]!.url" target="_blank" rel="noopener noreferrer">打开归档</a><span v-if="state[key]?.error"> · {{state[key]!.error}}</span></p>
  <p v-if="state.local?.warnings?.length" role="status">包内存在未收录的引用，请查看 manifest.json 的缺失清单。</p>
  <p v-if="error" role="alert">{{error}}</p>
 </section>
</template>
<style scoped>
.archive-state { display: block; }
.archive-state p { margin: 8px 0 0; overflow-wrap: anywhere; }
</style>

<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { http } from '@/shared/api/http'
const props=defineProps<{workspace:string;itemId?:string;disabled?:boolean}>()
const selected=defineModel<string[]>({default:()=>[]})
const rows=shallowRef<{itemId:string;title:string;version:string}[]>([]);const error=shallowRef('')
const options=computed(()=>rows.value.filter(row=>row.itemId!==props.itemId))
watch(()=>props.workspace,async(_value,_old,cleanup)=>{let active=true;cleanup(()=>active=false);rows.value=[];error.value='';try{const r=await http.get(`/lifeweave/${props.workspace}/research-catalog`);if(active)rows.value=r.data.items}catch{if(active)error.value='无法读取研究目录，请稍后重试。'}},{immediate:true})
</script>
<template>
 <details class="lw-mt-12"><summary>附带其他研究成果（已选 {{selected.length}} / 5）</summary>
  <p class="lw-small">当前事项的成果会自动读取。需要跨文章讨论时在这里选择；这些是研究成果，不代表已接受的正式知识。已有知识另按问题匹配读取。</p>
  <label class="lw-label">选择其他研究（最多5篇）<select v-model="selected" class="lw-field" multiple size="4" :disabled="disabled"><option v-for="row in options" :key="row.itemId" :value="row.itemId" :disabled="selected.length>=5&&!selected.includes(row.itemId)">{{row.title}} · {{row.version.slice(0,8)}}</option></select></label>
  <p v-if="error" role="alert">{{error}}</p>
 </details>
</template>

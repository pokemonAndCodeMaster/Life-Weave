<script setup lang="ts">
import { reactive, shallowRef } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import LifeWeaveModal from './LifeWeaveModal.vue'
import type { WorkItem } from '../types'
const props=defineProps<{item:WorkItem}>();const emit=defineEmits<{close:[];saved:[]}>()
const {activeWorkspace,load}=useLifeWeaveWorkspace()
const statuses:Record<string,string>={'待确认':'open','已计划':'planned','进行中':'in_progress','已阻塞':'blocked','待验收':'awaiting_acceptance','已完成':'completed','已取消':'cancelled'}
const form=reactive({title:props.item.title,status:statuses[props.item.state]??'open',priority:Number(props.item.payload.priority??0),due:props.item.due??'',update:props.item.update})
const busy=shallowRef(false);const error=shallowRef('')
async function save(){busy.value=true;error.value='';try{await http.patch(`/lifeweave/${activeWorkspace.value}/items/${props.item.id}`,{version:props.item.version,title:form.title,...(form.status!==statuses[props.item.state]?{status:form.status}:{}),payload:{...props.item.payload,priority:form.priority,due:form.due||null,update:form.update}});await load(activeWorkspace.value,true);emit('saved')}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
</script>
<template><LifeWeaveModal title="安排这件工作" @close="emit('close')"><form id="work-plan-form" class="lw-stack" @submit.prevent="save"><p v-if="error" class="lw-notice warning" role="alert">{{error}}</p><label class="lw-label">标题<input v-model="form.title" class="lw-field" required/></label><div class="lw-form-grid"><label class="lw-label">工作阶段<select v-model="form.status" class="lw-field"><option value="open">待确认</option><option value="planned">已计划</option><option value="in_progress">进行中</option><option value="blocked">已阻塞</option><option value="awaiting_acceptance">待验收</option><option v-if="form.status==='completed'" value="completed">已完成</option><option value="cancelled">已取消</option></select></label><label class="lw-label">优先级<select v-model="form.priority" class="lw-field"><option :value="0">未设置</option><option :value="1">紧急</option><option :value="2">高</option><option :value="3">普通</option><option :value="4">低</option></select></label></div><label class="lw-label">目标日期<input v-model="form.due" class="lw-field" type="date"/></label><label class="lw-label">最新进展<textarea v-model="form.update" class="lw-field" rows="3"></textarea></label><p class="lw-tiny lw-muted">有实际成果后，在事项的“成果与验证”中接受结果。</p></form><template #footer><button class="lw-btn" @click="emit('close')">取消</button><button class="lw-btn primary" form="work-plan-form" :disabled="busy">保存安排</button></template></LifeWeaveModal></template>

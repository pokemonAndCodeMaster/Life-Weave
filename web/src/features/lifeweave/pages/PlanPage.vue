<script setup lang="ts">
import {computed,shallowRef} from 'vue'
import {useLifeWeaveWorkspace} from '../composables/useLifeWeaveWorkspace'
import PageHeader from '../components/PageHeader.vue'
import WorkPlanEditor from '../components/WorkPlanEditor.vue'
import type {WorkItem} from '../types'
const {state,activeWorkspace,openModal}=useLifeWeaveWorkspace()
const selected=shallowRef<WorkItem|null>(null);const query=shallowRef('');const mode=shallowRef<'stage'|'priority'>('stage');const showClosed=shallowRef(false)
const labels=['待确认','已计划','进行中','已阻塞','待验收','已完成','已取消']
const priorities=['未设置','紧急','高','普通','低']
const filtered=computed(()=>(state.value?.items??[]).filter(item=>(showClosed.value||!['已完成','已取消'].includes(item.state))&&`${item.title} ${item.goal}`.toLowerCase().includes(query.value.toLowerCase())))
const groups=computed(()=>{const result=new Map<string,WorkItem[]>();for(const label of mode.value==='stage'?labels:(['紧急','高','普通','低','未设置'])){if(!showClosed.value&&['已完成','已取消'].includes(label))continue;result.set(label,[])}for(const item of filtered.value){const key=mode.value==='stage'?item.state:(priorities[Number(item.payload.priority??0)]??'未设置');result.set(key,[...(result.get(key)??[]),item])}return [...result].map(([label,items])=>({label,items:items.sort((a,b)=>(a.due??'9999').localeCompare(b.due??'9999'))}))})
function overdue(item:WorkItem){return !!item.due&&item.due<new Date().toLocaleDateString('sv-SE')&&!['已完成','已取消'].includes(item.state)}
</script>
<template><PageHeader title="计划与优先级" subtitle="先看正在推进的工作，再决定下一件值得做的事。"><button class="lw-btn primary" @click="openModal('item-create')">新建事项</button></PageHeader><div class="lw-toolbar"><div class="lw-segmented"><button :class="{active:mode==='stage'}" @click="mode='stage'">按工作阶段</button><button :class="{active:mode==='priority'}" @click="mode='priority'">按优先级</button></div><input v-model="query" placeholder="查找工作" aria-label="查找工作"/><label class="lw-small"><input v-model="showClosed" type="checkbox"/> 显示已结束</label><span class="lw-spacer"></span><span class="lw-small lw-muted">{{filtered.length}} 件工作</span></div><div class="lw-board"><section v-for="group in groups" :key="group.label" class="lw-board-column"><header><h2>{{group.label}}</h2><span>{{group.items.length}}</span></header><article v-for="item in group.items" :key="item.id" class="lw-plan-card"><RouterLink :to="`/lifeweave/${activeWorkspace}/items/${item.id}/overview`">{{item.title}}</RouterLink><p>{{item.update||item.goal}}</p><div class="lw-between lw-small"><span :class="{'lw-overdue':overdue(item)}">{{item.due||'未安排日期'}}{{overdue(item)?' · 已逾期':''}}</span><button class="lw-text-btn" @click="selected=item">安排</button></div><span v-if="item.parentId" class="lw-tiny lw-muted">子工作 · {{item.owner}}</span></article><p v-if="!group.items.length" class="lw-board-empty">暂无事项</p></section></div><WorkPlanEditor v-if="selected" :key="selected.id" :item="selected" @close="selected=null" @saved="selected=null"/></template>

<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import ManualResultEditor from './ManualResultEditor.vue'
import LifeWeaveIcon from './LifeWeaveIcon.vue'
import StatusBadge from './StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkItem,LifeWeaveRun } from '../types'

const props = defineProps<{ item: WorkItem; runs?:LifeWeaveRun[] }>()
const { openModal, runs } = useLifeWeaveWorkspace()
const results = computed(()=>(props.runs??runs.value).filter(run=>run.itemId===props.item.id && run.result))
const manualResult = shallowRef(false)
const proven = computed(() => props.item.evidence.filter((entry) => entry.result === '已证明').length)
</script>

<template>
<ManualResultEditor v-if="manualResult" :item="item" @close="manualResult=false" @saved="manualResult=false"/><div class="lw-between lw-mb-18"><p class="lw-small lw-sub">人工工作和 AI 委托的实际成果，都可以在这里审阅。</p><button class="lw-btn primary" @click="manualResult=true">登记工作成果</button></div>
  <div class="lw-artifact-grid">
    <article v-for="artifact in item.artifacts" :key="artifact.id" class="lw-artifact-card"><div class="lw-inline lw-muted lw-mb-10"><LifeWeaveIcon name="file" />{{ artifact.kind || '可阅读成果' }}</div><h3>{{ artifact.name }}</h3><p>{{ artifact.summary || '打开查看实际产物与固定版本。' }}</p><button class="lw-btn" type="button" @click="openModal('artifact', { artifact, item })">打开成果</button></article>
    <article v-for="run in results" :key="run.id" class="lw-artifact-card"><div class="lw-inline lw-muted lw-mb-10"><LifeWeaveIcon name="file"/>AI 交付</div><h3>第 {{run.attempt}} 次委托结果</h3><p>{{run.instruction}}</p><button class="lw-btn" @click="openModal('run-detail',{runId:run.id})">阅读结果</button></article><article v-if="!item.artifacts.length && !results.length" class="lw-artifact-card"><div class="lw-inline lw-muted lw-mb-10"><LifeWeaveIcon name="file" />成果</div><h3>尚无成果回传</h3><p>委托运行或手工工作可以把真实产物关联到这里。</p><button class="lw-btn" type="button" @click="openModal('delegate', { item })">委托补充</button></article>
  </div>
  <div class="lw-section-title"><h2>要求与验证证据</h2><StatusBadge value="实际证据" tone="blue" /></div>
  <div class="lw-panel"><div class="lw-table-wrap"><table class="lw-data-table"><thead><tr><th>要证明什么</th><th>为什么要验证</th><th>对应证据</th><th>结论</th></tr></thead><tbody><tr v-for="evidence in item.evidence" :key="evidence.id ?? evidence.name"><td>{{ evidence.name }}</td><td>{{ evidence.purpose }}</td><td><button class="lw-text-btn" type="button" @click="openModal('evidence', { evidence, item })">{{ evidence.source }}</button></td><td><StatusBadge :value="evidence.result" /></td></tr></tbody></table></div><div v-if="!item.evidence.length" class="lw-empty">尚未登记验证证据。</div><div class="lw-panel-body"><div class="lw-between"><span class="lw-small lw-sub">{{ proven }}/{{ item.evidence.length }} 类要求已有证明；数量不代替覆盖说明。</span><button class="lw-btn" type="button" @click="openModal('delegate', { item })"><LifeWeaveIcon name="spark" />委托补充验证</button></div></div></div>
  <div class="lw-section-title"><h2>接受的是结果，不是一次运行</h2></div>
  <div class="lw-panel pad"><p class="lw-small lw-sub">运行结束不会自动完成事项。责任人确认范围、成果与证据后再接受结果。</p><div class="lw-inline"><button class="lw-btn primary" type="button" :disabled="item.state === '已完成' || item.state === 'accepted'" @click="openModal('accept-result', { item })">接受本轮结果</button><button class="lw-btn" type="button" @click="openModal('feedback', { item, anchor: '成果与验证' })">提出结果反馈</button><StatusBadge v-if="item.state === '已完成' || item.state === 'accepted'" value="已完成" /></div></div>
</template>

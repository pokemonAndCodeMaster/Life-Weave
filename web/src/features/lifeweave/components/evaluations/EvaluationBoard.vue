<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { apiError, assessEvaluation, createEvaluation, createEvaluationImprovement, listEvaluations, startEvaluation } from '../../api/lifeweave'
import type { EvaluationTask } from '../../api/lifeweave'
import type { WorkspaceKind } from '../../types'
import { documents } from '../../api/library'
import EvaluationCreateForm from './EvaluationCreateForm.vue'
import EvaluationEntry from './EvaluationEntry.vue'

interface Candidate { id: string; title: string; status: string; version?: string }
interface Item { id: string; title: string }
interface Method { id: string; title: string; description: string }
const props = defineProps<{ workspace: WorkspaceKind; candidates: Candidate[]; items: Item[]; methods: Method[] }>()
const emit = defineEmits<{ changed: [] }>()
const entries = shallowRef<EvaluationTask[]>([])
const total = shallowRef(0)
const offset = shallowRef(0)
const busy = shallowRef('')
const template = shallowRef<EvaluationTask | null>(null)
const error = shallowRef('')
const knowledge = shallowRef<Array<{ ref: string; title: string }>>([])
const knowledgeError = shallowRef('')
const pageSize = 20
let generation = 0
async function load() {
  const current = ++generation
  try {
    const result = await listEvaluations(props.workspace, pageSize, offset.value)
    if (current !== generation) return
    entries.value = result.items; total.value = result.total; error.value = ''
  } catch (caught) { if (current === generation) error.value = apiError(caught).message }
}
watch(() => props.workspace, () => {
  offset.value = 0; template.value = null; knowledge.value = []; knowledgeError.value = ''
  void load()
  const workspace = props.workspace
  void documents(workspace).then(result => {
    if (workspace === props.workspace) knowledge.value = result.items.map(entry => ({ ref: `${entry.sourceId}:${entry.path}`, title: `${entry.sourceTitle} / ${entry.title}` }))
  }).catch(caught => { if (workspace === props.workspace) knowledgeError.value = apiError(caught).message })
}, { immediate: true })
async function action(id: string, run: () => Promise<unknown>) {
  busy.value = id; error.value = ''
  try { await run(); if (id === 'create') template.value = null; await load(); emit('changed') }
  catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = '' }
}
function nextPage(delta: number) { offset.value = Math.max(0, offset.value + delta * pageSize); void load() }
function reuse(entry: EvaluationTask) { template.value = entry; window.scrollTo({ top: 0, behavior: 'smooth' }) }
</script>

<template>
  <div class="evaluation-board">
    <section class="lw-panel pad"><h2>建立评测任务</h2><p class="lw-small lw-sub">先写任务和通过标准。创建只保存计划；点击“开始真实评测”才会委托 AI。</p>
      <EvaluationCreateForm :candidates="candidates" :items="items" :busy="Boolean(busy)" :template="template" @clear-template="template = null" @create="payload => action('create', () => createEvaluation(workspace, payload))" />
    </section>
    <section class="lw-panel pad"><div class="evaluation-top"><div><h2>评测记录</h2><p class="lw-small lw-sub">结果、过程与原目标分开核对；失败记录保留用于下一版比较。</p></div><button class="lw-btn sm" type="button" @click="load">刷新状态</button></div>
      <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
      <p v-if="knowledgeError" class="lw-small lw-sub" role="status">知识目录暂不可用：{{ knowledgeError }}。仍可启动不附带知识的评测。</p>
      <div class="evaluation-list"><EvaluationEntry v-for="entry in entries" :key="entry.id" :entry="entry" :workspace="workspace" :busy="Boolean(busy)" :methods="methods" :knowledge="knowledge" @start="(id, payload) => action(id, () => startEvaluation(workspace, id, payload))" @assess="(id, payload) => action(id, () => assessEvaluation(workspace, id, payload))" @improve="(id, payload) => action(id, () => createEvaluationImprovement(workspace, id, payload))" @reuse="reuse" /></div>
      <p v-if="!entries.length && !error" class="lw-empty">还没有评测任务。可先用现有事项定义一条整件事评测。</p>
      <div v-if="total > pageSize" class="evaluation-pages"><button class="lw-btn sm" type="button" :disabled="offset === 0" @click="nextPage(-1)">上一页</button><span>{{ offset + 1 }}–{{ Math.min(offset + pageSize, total) }} / {{ total }}</span><button class="lw-btn sm" type="button" :disabled="offset + pageSize >= total" @click="nextPage(1)">下一页</button></div>
    </section>
  </div>
</template>

<style scoped>
.evaluation-board, .evaluation-list { display: grid; gap: 16px; }
.evaluation-top, .evaluation-pages { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.evaluation-top h2 { margin-bottom: 4px; }
.evaluation-pages { justify-content: flex-end; font-size: 12px; }
</style>

<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { apiError, listCandidateEvaluations, listCandidateRuns } from '../../api/lifeweave'
import type { EvaluationTask } from '../../api/lifeweave'
import type { LifeWeaveRun, WorkspaceKind } from '../../types'
import StatusBadge from '../StatusBadge.vue'

const props = defineProps<{ workspace: WorkspaceKind; candidateId: string }>()
const emit = defineEmits<{ navigate: [] }>()
const entries = shallowRef<EvaluationTask[]>([])
const total = shallowRef(0)
const lineage = shallowRef<Array<{ id: string; title: string; version: string }>>([])
const offset = shallowRef(0)
const error = shallowRef('')
const runs = shallowRef<LifeWeaveRun[]>([])
const runTotal = shallowRef(0)
const runOffset = shallowRef(0)
const runError = shallowRef('')
const limit = 10
let generation = 0
let runGeneration = 0

async function load() {
  const current = ++generation
  try {
    const result = await listCandidateEvaluations(props.workspace, props.candidateId, limit, offset.value)
    if (current !== generation) return
    entries.value = result.items
    total.value = result.total
    lineage.value = result.lineage
    error.value = ''
  } catch (caught) {
    if (current === generation) error.value = apiError(caught).message
  }
}

async function loadRuns() {
  const current = ++runGeneration
  try {
    const result = await listCandidateRuns(props.workspace, props.candidateId, limit, runOffset.value)
    if (current !== runGeneration) return
    if (result.total > 0 && runOffset.value >= result.total) {
      runOffset.value = Math.floor((result.total - 1) / limit) * limit
      void loadRuns()
      return
    }
    runs.value = result.items
    runTotal.value = result.total
    runError.value = ''
  } catch (caught) {
    if (current === runGeneration) runError.value = apiError(caught).message
  }
}

function reload() { void load(); void loadRuns() }

watch(() => [props.workspace, props.candidateId], () => {
  offset.value = 0
  entries.value = []
  total.value = 0
  lineage.value = []
  error.value = ''
  runOffset.value = 0
  runs.value = []
  runTotal.value = 0
  runError.value = ''
  reload()
}, { immediate: true })

function page(delta: number) {
  offset.value = Math.max(0, offset.value + delta * limit)
  void load()
}

function pageRuns(delta: number) {
  runOffset.value = Math.max(0, runOffset.value + delta * limit)
  void loadRuns()
}
</script>

<template>
  <section class="cap-history">
    <div class="cap-history-head"><h3>工作样例与评测历史</h3><button class="lw-btn sm" type="button" @click="reload">刷新</button></div>
    <p class="lw-small lw-sub">这里列当前候选及显式前任的评测。“通过”只代表该任务按记录的标准、运行和已接受证据完成了评估。</p>
    <p v-if="lineage.length > 1" class="lw-small lw-sub">此候选明确继承 {{ lineage.length - 1 }} 个前任；它们的失败评测也在下方，发布前要沿原标准复测。</p>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <article v-for="entry in entries" :key="entry.id" class="cap-history-entry">
      <div class="cap-history-head"><strong>{{ entry.title }}</strong><StatusBadge :value="entry.outcome ?? entry.state" /></div>
      <p class="lw-small">{{ entry.criteria }}</p>
      <p v-if="entry.assessment" class="lw-small lw-sub">评估：{{ entry.assessment }}</p>
      <p class="lw-tiny lw-muted">{{ entry.candidateId === candidateId ? '当前候选' : '前任候选' }} {{ entry.candidateId }} · 版本 {{ entry.candidateVersion }}</p>
      <div class="cap-history-links">
        <RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(entry.itemId)}/outputs`" @click="emit('navigate')">打开事项与证据</RouterLink>
        <RouterLink v-if="entry.runId" :to="{ path: `/lifeweave/${workspace}/runs`, query: { runId: entry.runId } }" @click="emit('navigate')">查看运行过程</RouterLink>
      </div>
    </article>
    <p v-if="!entries.length && !error" class="lw-small lw-sub">此能力尚无评测任务。请从“评测任务”建立可追溯的工作样例。</p>
    <div v-if="total > limit" class="cap-history-pages">
      <button class="lw-btn sm" type="button" :disabled="offset === 0" @click="page(-1)">上一页</button>
      <span class="lw-tiny">{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} / {{ total }}</span>
      <button class="lw-btn sm" type="button" :disabled="offset + limit >= total" @click="page(1)">下一页</button>
    </div>
    <h3 class="cap-history-subtitle">关联委托历史</h3>
    <p class="lw-small lw-sub">以下是当前候选实际参与过的运行，也包括普通委托；运行成功不等于结果已接受。</p>
    <p v-if="runError" class="lw-notice warning" role="alert">{{ runError }}</p>
    <article v-for="run in runs" :key="run.id" class="cap-history-entry">
      <div class="cap-history-head"><strong class="lw-mono">{{ run.id }}</strong><StatusBadge :value="run.state" /></div>
      <p class="lw-small">{{ (run.instruction ?? '').slice(0, 180) }}</p>
      <p class="lw-tiny lw-muted">{{ run.engine }} · 第 {{ run.attempt }} 次</p>
      <div class="cap-history-links">
        <RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(run.itemId)}/outputs`" @click="emit('navigate')">打开所属事项</RouterLink>
        <RouterLink :to="{ path: `/lifeweave/${workspace}/runs`, query: { runId: run.id } }" @click="emit('navigate')">查看运行过程</RouterLink>
      </div>
    </article>
    <p v-if="!runs.length && !runError" class="lw-small lw-sub">此候选还没有关联的运行。</p>
    <div v-if="runTotal > limit || runOffset > 0" class="cap-history-pages">
      <button class="lw-btn sm" type="button" :disabled="runOffset === 0" @click="pageRuns(-1)">上一页</button>
      <span class="lw-tiny">{{ runOffset + 1 }}–{{ Math.min(runOffset + limit, runTotal) }} / {{ runTotal }}</span>
      <button class="lw-btn sm" type="button" :disabled="runOffset + limit >= runTotal" @click="pageRuns(1)">下一页</button>
    </div>
  </section>
</template>

<style scoped>
.cap-history { display: grid; gap: 12px; margin-top: 22px; }
.cap-history-head, .cap-history-pages, .cap-history-links { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.cap-history-entry { padding: 12px 14px; border: 1px solid var(--lw-line); border-radius: 7px; }
.cap-history-entry p { margin: 7px 0 0; }
.cap-history-links { justify-content: flex-start; margin-top: 10px; font-size: 13px; }
.cap-history-subtitle { margin-top: 18px; }
</style>

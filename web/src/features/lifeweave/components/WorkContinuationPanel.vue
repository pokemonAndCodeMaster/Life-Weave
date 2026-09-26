<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { getContinuation, getRecommendations, saveFeedback } from '../api/continuation'
import type { Continuation, InputRecommendations } from '../api/continuation'
import { apiError } from '../api/lifeweave'
import { downloadText } from '../utils/download'
import RecommendedInputs from './RecommendedInputs.vue'

const props = defineProps<{ workspace: string; itemId: string }>()
const emit = defineEmits<{ saved: [] }>()
const data = ref<Continuation | null>(null)
const materials = ref<InputRecommendations | null>(null)
const body = ref(''); const runId = ref(''); const error = ref(''); const saved = ref(false)
const loading = ref(false); const saving = ref(false)
let generation = 0
let pending: { body: string; runId: string; id: string } | null = null

async function refresh() {
  const ticket = ++generation
  loading.value = true; error.value = ''
  try {
    const [current, recommended] = await Promise.all([getContinuation(props.workspace, props.itemId), getRecommendations(props.workspace, props.itemId)])
    if (ticket !== generation) return
    data.value = current; materials.value = recommended
  } catch (e) { if (ticket === generation) error.value = apiError(e).message }
  finally { if (ticket === generation) loading.value = false }
}

async function submit() {
  if (!body.value.trim() || saving.value) return
  const ticket = generation; const workspace = props.workspace; const item = props.itemId
  if (!pending || pending.body !== body.value || pending.runId !== runId.value) pending = { body: body.value, runId: runId.value, id: crypto.randomUUID() }
  saving.value = true; error.value = ''; saved.value = false
  try {
    await saveFeedback(workspace, item, pending.body, pending.runId || null, pending.id)
    if (ticket !== generation) return
    pending = null; body.value = ''; saved.value = true; emit('saved'); await refresh()
  } catch (e) { if (ticket === generation) error.value = apiError(e).message }
  finally { if (workspace === props.workspace && item === props.itemId) saving.value = false }
}

function download() {
  if (data.value) downloadText(JSON.stringify(data.value, null, 2), `lifeweave-${props.itemId}-continuation.json`)
}

watch(() => [props.workspace, props.itemId], () => {
  data.value = null; materials.value = null; body.value = ''; runId.value = ''; pending = null; saving.value = false; saved.value = false
  void refresh()
}, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>

<template>
  <section class="lw-panel pad lw-mt-18" aria-label="接着推进">
    <div class="lw-between"><h2>接着推进</h2><button class="lw-btn ghost sm" type="button" :disabled="loading || saving" @click="refresh">刷新当前记录</button></div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">正在读取当前背景与材料……</p>
    <template v-if="data">
      <p class="lw-small">已读取背景 v{{ data.context.revisionNo }} · {{ data.runs.length }} 次运行 · {{ data.externalDevelopment?.length ?? 0 }} 条外部开发记录 · {{ data.feedback.length }} 条纠偏 · {{ data.nextStep.openProposalCount }} 项待审背景修改</p>
      <p v-if="data.nextStep.declared">下一步：{{ data.nextStep.declared }}</p>
      <details v-if="data.externalDevelopment?.length" class="lw-mb-10"><summary>已登记的外部开发进展</summary>
        <p class="lw-small lw-muted">阶段和检查由外部会话上报；Git 状态由服务在上报时读取。完整记录可下载，也可在推进记录中查看。</p>
        <div v-for="entry in data.externalDevelopment?.slice(0, 10) ?? []" :key="entry.id" class="lw-mb-10">
          <strong>{{ entry.payload.phase }}</strong> · {{ entry.body }}<br />
          <span v-if="entry.payload.observedGit" class="lw-small lw-muted">Git {{ entry.payload.observedGit.revision.slice(0, 12) }} · 修改 {{ entry.payload.observedGit.changedCount }} · 未跟踪 {{ entry.payload.observedGit.untrackedCount }}</span>
        </div>
      </details>
      <p class="lw-small lw-muted">读取当前记录不会启动执行。纠偏在新建或重试运行时自动加入输入；目标变更仍通过共享上下文审阅。</p>
      <RecommendedInputs v-if="materials" :workspace="workspace" :materials="materials" />
      <details v-if="data.feedback.length" class="lw-mb-10"><summary>已保存的纠偏反馈</summary><p v-for="entry in data.feedback" :key="entry.id" class="lw-preline">{{ entry.body }}<span v-if="entry.runId" class="lw-muted"> · {{ entry.runId }}</span></p></details>
      <form @submit.prevent="submit">
        <label class="lw-label">需要怎样调整<textarea v-model="body" class="lw-field" placeholder="例如：先弄清适用范围，暂时不要写代码。" required :disabled="saving"></textarea></label>
        <label class="lw-label">反馈针对<select v-model="runId" class="lw-field" :disabled="saving"><option value="">本事项后续工作</option><option v-for="run in data.runs" :key="run.id" :value="run.id">{{ run.id }} · {{ run.state }}</option></select></label>
        <div class="lw-between"><button class="lw-btn primary sm" type="submit" :disabled="saving || !body.trim()">保存纠偏</button><button class="lw-btn ghost sm" type="button" @click="download">下载接续记录</button></div>
        <p v-if="saved" role="status">已保存，下一轮运行会自动读取这条反馈。</p>
      </form>
    </template>
  </section>
</template>

<style scoped>
.lw-panel { margin-top: 18px; }
</style>

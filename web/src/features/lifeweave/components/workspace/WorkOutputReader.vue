<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError, getEntityDetail, getRun } from '../../api/lifeweave'
import { getDevelopmentDelivery, getDevelopmentDiff } from '../../api/development'
import type { DevelopmentDelivery as Delivery, DevelopmentDiff } from '../../api/development'
import type { WorkOutputRef } from '../../api/workView'
import type { LifeWeaveRun, WorkspaceKind } from '../../types'
import ResearchOutputPanel from '../ResearchOutputPanel.vue'
import DevelopmentDelivery from '../DevelopmentDelivery.vue'
import MarkdownBody from '../MarkdownBody.vue'
import { safeWorkLink } from './safeWorkLink'
import { kindLabel, stateLabel } from './workOutputLabels'

const props = withDefaults(defineProps<{ workspace: WorkspaceKind; itemId: string; output: WorkOutputRef; allowHistory?: boolean }>(), { allowHistory: true })
const emit = defineEmits<{ updated: []; quote: [value: { text: string; runId: string | null; anchor: string }] }>()
const delivery = shallowRef<Delivery | null>(null)
const implementation = shallowRef<LifeWeaveRun | null>(null)
const diff = shallowRef<DevelopmentDiff | null>(null)
const artifactContent = shallowRef<string | null>(null)
const artifactLoading = shallowRef(false)
const developmentLoading = shallowRef(false)
const error = shallowRef('')
const key = computed(() => `${props.workspace}:${props.itemId}:${props.output?.id || ''}`)
let generation = 0

async function load() {
  const ticket = ++generation
  delivery.value = null; implementation.value = null; diff.value = null; artifactContent.value = null; artifactLoading.value = false; developmentLoading.value = false; error.value = ''
  const output = props.output
  if (output?.kind === 'artifact' && output.artifactId) {
    artifactLoading.value = true
    try {
      const entity = await getEntityDetail(props.workspace, output.artifactId) as { payload?: { body?: unknown } }
      if (ticket === generation) artifactContent.value = typeof entity.payload?.body === 'string' ? entity.payload.body : null
    } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
    finally { if (ticket === generation) artifactLoading.value = false }
    return
  }
  if (output?.kind !== 'development') return
  developmentLoading.value = true
  try {
    const finalDelivery = output.id.startsWith('delivery:') && !!output.assignmentId
    const [fixed, run] = await Promise.allSettled([
      finalDelivery ? getDevelopmentDelivery(props.workspace, output.assignmentId!) : Promise.resolve(null),
      output.runId ? getRun(props.workspace, output.runId) : Promise.resolve(null),
    ])
    if (ticket !== generation) return
    delivery.value = fixed.status === 'fulfilled' ? fixed.value : null
    implementation.value = run.status === 'fulfilled' ? run.value : null
    error.value = [fixed, run].filter(result => result.status === 'rejected').map(result => apiError((result as PromiseRejectedResult).reason).message).join('；')
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) developmentLoading.value = false }
}
// Polling returns new objects, but must not erase the reader's open diff or reload images.
watch([() => props.workspace, () => props.itemId, () => props.output.id, () => props.output.kind,
  () => props.output.version, () => props.output.runId, () => props.output.assignmentId,
  () => props.output.artifactId, () => props.output.state], load, { immediate: true })
onBeforeUnmount(() => { generation += 1 })

async function refreshDelivery() { await load(); emit('updated') }

async function showDiff() {
  const output = props.output
  if (!output?.assignmentId) return
  const ticket = generation
  try { const result = await getDevelopmentDiff(props.workspace, output.assignmentId); if (ticket === generation) { diff.value = result; error.value = '' } }
  catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
}
</script>
<template>
      <article class="output-reader"><div class="reader-header"><div><span class="entry-kind">{{ kindLabel(output) }}{{ output.version ? ` · ${output.version.slice(0, 12)}` : '' }}</span><h3>{{ output.title }}</h3><p v-if="output.createdAt">形成于 {{ new Date(output.createdAt).toLocaleString('zh-CN') }}</p></div><span v-if="output.state" class="output-state">{{ stateLabel(output.state) }}</span></div>
        <p v-if="error" class="lw-notice warning" role="alert">{{ error }} <button type="button" class="lw-btn sm" @click="load">重新读取</button></p>
        <ResearchOutputPanel v-if="output.kind === 'research' || (output.kind === 'note' && !output.artifactId)" :key="key" :workspace="workspace" :item-id="itemId" :selected-run-id="output.runId" :selected-output-id="output.id" :allow-history="allowHistory" compact @quote="emit('quote', $event)" @feedback-saved="emit('updated')" @candidate-created="emit('updated')" />
        <template v-else-if="output.kind === 'development'"><p v-if="developmentLoading" role="status" class="reader-muted">正在读取开发成果…</p><MarkdownBody v-if="implementation?.result" :content="implementation.result" /><p v-else-if="!delivery && !developmentLoading && !error" class="reader-muted">{{ output.id.startsWith('delivery:') ? '尚无可读的固定交付。' : '此阶段尚无可读的 Run 正文。' }}</p><DevelopmentDelivery v-if="delivery" :key="delivery.id" :workspace="workspace" :delivery="delivery" @updated="refreshDelivery" /><button v-if="output.id.startsWith('delivery:') && output.assignmentId" type="button" class="lw-btn sm" @click="showDiff">查看实际 Git 差异</button><details v-if="diff" open><summary>差异预览 · {{ diff.fileCount }} 个文件{{ diff.truncated ? '（已截断）' : '' }}</summary><pre class="diff-preview">{{ diff.patch || '没有代码差异' }}</pre></details></template>
        <template v-else><p v-if="artifactLoading" role="status" class="reader-muted">正在读取成果正文…</p><MarkdownBody v-else-if="artifactContent" :content="artifactContent" /><p v-else-if="output.artifactId && !error" class="reader-muted">这份人工成果尚无可读正文。</p><a v-if="safeWorkLink(output.uri) && !output.artifactId" class="lw-btn sm" :href="safeWorkLink(output.uri)!" target="_blank" rel="noopener noreferrer">打开成果来源</a><p v-else-if="!output.artifactId && !artifactContent" class="reader-muted">{{ output.summary || '此成果没有可安全打开的地址。' }}</p></template>
      </article>
</template>
<style scoped>
.reader-header { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.reader-header p { margin: 5px 0 0; font-size: 12px; color: #667b90; }
.reader-header h3 { margin: 4px 0 0; font-size: 18px; overflow-wrap: anywhere; }
.entry-kind { color: #507394; font-size: 11px; }
.output-reader { min-width: 0; display: grid; gap: 15px; padding: 22px; border: 1px solid #e1e8f0; background: #fff; border-radius: 12px; }
.output-state { white-space: nowrap; font-size: 11px; color: #597189; }
.reader-muted { color: #6b7f91; font-size: 13px; }
.diff-preview { overflow: auto; max-height: 500px; padding: 12px; background: #f5f7fa; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; }
@media(max-width:790px){ .output-reader { padding: 16px; } }
</style>

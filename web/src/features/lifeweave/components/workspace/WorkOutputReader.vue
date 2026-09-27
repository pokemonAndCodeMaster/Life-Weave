<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError, getEntityDetail, getRun } from '../../api/lifeweave'
import { getDevelopmentDelivery } from '../../api/development'
import type { DevelopmentDelivery as Delivery } from '../../api/development'
import type { WorkOutputRef } from '../../api/workView'
import type { OutputDocumentRef } from '../../api/outputFiles'
import type { LifeWeaveRun, WorkspaceKind } from '../../types'
import ResearchOutputPanel from '../ResearchOutputPanel.vue'
import DevelopmentDelivery from '../DevelopmentDelivery.vue'
import MarkdownBody from '../MarkdownBody.vue'
import WorkOutputCatalog from './WorkOutputCatalog.vue'
import { safeWorkLink } from './safeWorkLink'
import { kindLabel, stateLabel } from './workOutputLabels'

const props = withDefaults(defineProps<{ workspace: WorkspaceKind; itemId: string; output: WorkOutputRef; selectedPath?: string | null; allowHistory?: boolean }>(), { allowHistory: true })
const emit = defineEmits<{ updated: []; selectFile: [path: string]; readDocument: [document: OutputDocumentRef]; quote: [value: { text: string; runId: string | null; anchor: string }] }>()
const delivery = shallowRef<Delivery | null>(null)
const implementation = shallowRef<LifeWeaveRun | null>(null)
const artifactContent = shallowRef<string | null>(null)
const expanded = shallowRef(false)
const detailLoading = shallowRef(false)
const error = shallowRef('')
const key = computed(() => `${props.workspace}:${props.itemId}:${props.output.id}`)
let generation = 0

async function loadDetails() {
  if (!expanded.value) return
  const ticket = ++generation
  delivery.value = null
  implementation.value = null
  artifactContent.value = null
  detailLoading.value = true
  error.value = ''
  const output = props.output
  try {
    if (output.artifactId && output.kind !== 'development') {
      const entity = await getEntityDetail(props.workspace, output.artifactId) as { payload?: { body?: unknown } }
      if (ticket === generation) artifactContent.value = typeof entity.payload?.body === 'string' ? entity.payload.body : null
    } else if (output.kind === 'development') {
      const finalDelivery = output.id.startsWith('delivery:') && !!output.assignmentId
      const [fixed, run] = await Promise.allSettled([
        finalDelivery ? getDevelopmentDelivery(props.workspace, output.assignmentId!) : Promise.resolve(null),
        output.runId ? getRun(props.workspace, output.runId) : Promise.resolve(null),
      ])
      if (ticket !== generation) return
      delivery.value = fixed.status === 'fulfilled' ? fixed.value : null
      implementation.value = run.status === 'fulfilled' ? run.value : null
      error.value = [fixed, run].filter(result => result.status === 'rejected').map(result => apiError((result as PromiseRejectedResult).reason).message).join('；')
    }
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) detailLoading.value = false }
}

watch([() => props.workspace, () => props.itemId, () => props.output.id, () => props.output.version,
  () => props.output.runId, () => props.output.assignmentId, () => props.output.artifactId], () => {
  generation += 1
  expanded.value = false
  delivery.value = null
  implementation.value = null
  artifactContent.value = null
  error.value = ''
})
onBeforeUnmount(() => { generation += 1 })
function toggleDetails() { expanded.value = !expanded.value; if (expanded.value) void loadDetails() }
async function refreshDelivery() { await loadDetails(); emit('updated') }
</script>

<template>
  <article class="output-reader">
    <div class="reader-header"><div><span class="entry-kind">{{ kindLabel(output) }}{{ output.version ? ` · ${output.version.slice(0, 12)}` : '' }}</span><h3>{{ output.title }}</h3><p v-if="output.createdAt">形成于 {{ new Date(output.createdAt).toLocaleString('zh-CN') }}</p></div><span v-if="output.state" class="output-state">{{ stateLabel(output.state) }}</span></div>
    <p v-if="output.summary" class="output-summary">{{ output.summary }}</p>
    <WorkOutputCatalog :workspace="workspace" :item-id="itemId" :output-id="output.id" :version="output.version" :selected-path="selectedPath" @select-file="emit('selectFile', $event)" @read-document="emit('readDocument', $event)" />
    <div v-if="output.kind === 'research' || output.kind === 'development' || output.artifactId || output.uri" class="reader-extra">
      <button type="button" class="extra-toggle" :aria-expanded="expanded" @click="toggleDetails">{{ expanded ? '收起执行与验收详情' : '查看执行与验收详情' }}</button>
      <div v-if="expanded" class="extra-content">
        <p v-if="detailLoading" role="status" class="reader-muted">正在读取详情…</p>
        <p v-if="error" class="lw-notice warning" role="alert">{{ error }} <button type="button" class="lw-btn sm" @click="loadDetails">重新读取</button></p>
        <ResearchOutputPanel v-if="output.kind === 'research' || (output.kind === 'note' && !output.artifactId)" :key="key" :workspace="workspace" :item-id="itemId" :selected-run-id="output.runId" :selected-output-id="output.id" :allow-history="allowHistory" compact @quote="emit('quote', $event)" @feedback-saved="emit('updated')" @candidate-created="emit('updated')" />
        <template v-else-if="output.kind === 'development'"><MarkdownBody v-if="implementation?.result" :content="implementation.result" /><DevelopmentDelivery v-if="delivery" :key="delivery.id" :workspace="workspace" :delivery="delivery" @updated="refreshDelivery" /><p v-else-if="!detailLoading && !error" class="reader-muted">这份成果暂无更多执行详情。</p></template>
        <template v-else><MarkdownBody v-if="artifactContent" :content="artifactContent" /><a v-else-if="safeWorkLink(output.uri) && !output.artifactId" class="lw-btn sm" :href="safeWorkLink(output.uri)!" target="_blank" rel="noopener noreferrer">打开成果来源</a><p v-else-if="!detailLoading && !error" class="reader-muted">暂无更多正文。</p></template>
      </div>
    </div>
  </article>
</template>

<style scoped>
.reader-header { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.reader-header p { margin: 5px 0 0; font-size: 12px; color: #667b90; }
.reader-header h3 { margin: 4px 0 0; font-size: 18px; overflow-wrap: anywhere; }
.entry-kind { color: #507394; font-size: 11px; }
.output-reader { min-width: 0; display: grid; gap: 15px; padding: 22px; border: 1px solid #e1e8f0; background: #fff; border-radius: 12px; }
.output-state { white-space: nowrap; font-size: 11px; color: #597189; }
.output-summary { margin: 0; color: #3b566c; font-size: 13px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }
.reader-extra { border-top: 1px solid #e4ebf1; padding-top: 12px; }
.extra-toggle { border: 0; background: none; color: #37668d; padding: 4px 0; text-decoration: underline; cursor: pointer; font-size: 12px; }
.extra-content { display: grid; gap: 13px; margin-top: 12px; min-width: 0; }
.reader-muted { color: #6b7f91; font-size: 13px; }
@media(max-width:790px){ .output-reader { padding: 16px; } }
</style>

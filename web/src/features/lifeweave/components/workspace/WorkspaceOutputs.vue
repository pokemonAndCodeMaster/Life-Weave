<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { apiError, getEntityDetail, getRun } from '../../api/lifeweave'
import { getDevelopmentDelivery, getDevelopmentDiff } from '../../api/development'
import type { DevelopmentDelivery as Delivery, DevelopmentDiff } from '../../api/development'
import type { ItemWorkView, WorkOutputRef } from '../../api/workView'
import type { LifeWeaveRun, WorkItem, WorkspaceKind } from '../../types'
import { useLifeWeaveWorkspace } from '../../composables/useLifeWeaveWorkspace'
import ResearchOutputPanel from '../ResearchOutputPanel.vue'
import ResearchKnowledgeReview from '../ResearchKnowledgeReview.vue'
import ManualResultEditor from '../ManualResultEditor.vue'
import DevelopmentDelivery from '../DevelopmentDelivery.vue'
import MarkdownBody from '../MarkdownBody.vue'
import { safeWorkLink } from './safeWorkLink'

const props = defineProps<{ workspace: WorkspaceKind; item: WorkItem; view: ItemWorkView; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: string]; updated: []; quote: [value: { text: string; runId: string | null; anchor: string }] }>()
const { openModal } = useLifeWeaveWorkspace()
const selected = computed(() => props.view.outputs.find(output => output.id === props.selectedId) || props.view.outputs[0] || null)
const delivery = shallowRef<Delivery | null>(null)
const implementation = shallowRef<LifeWeaveRun | null>(null)
const diff = shallowRef<DevelopmentDiff | null>(null)
const artifactContent = shallowRef<string | null>(null)
const artifactLoading = shallowRef(false)
const error = shallowRef('')
const showManualEditor = shallowRef(false)
const showKnowledge = shallowRef(false)
const key = computed(() => `${props.workspace}:${props.item.id}:${selected.value?.id || ''}`)
const accepted = computed(() => ['已完成', 'accepted', 'completed'].includes(props.item.state))
const proven = computed(() => props.item.evidence.filter(entry => entry.result === '已证明' || entry.result === 'accepted').length)
let generation = 0

watch(key, async () => {
  const ticket = ++generation
  delivery.value = null; implementation.value = null; diff.value = null; artifactContent.value = null; artifactLoading.value = false; error.value = ''; showKnowledge.value = false
  const output = selected.value
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
}, { immediate: true })

async function showDiff() {
  const output = selected.value
  if (!output?.assignmentId) return
  const ticket = generation
  try { const result = await getDevelopmentDiff(props.workspace, output.assignmentId); if (ticket === generation) { diff.value = result; error.value = '' } }
  catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
}
function kindLabel(output: WorkOutputRef): string {
  if (output.kind === 'research') return '研究成果'
  if (output.kind === 'development') return output.id.startsWith('delivery:') ? '代码交付' : '开发记录'
  if (output.kind === 'artifact') return '人工成果'
  return '记录'
}
function stateLabel(state: string): string {
  return ({ succeeded: '已完成', failed: '失败', running: '进行中', waiting: '等待中', planned: '待开始', cancelled: '已取消', manual: '人工登记', partial: '部分结果' } as Record<string, string>)[state] || state
}
function shortSummary(value: string): string {
  const plain = value.replace(/\s+/g, ' ').trim()
  return plain.length > 120 ? `${plain.slice(0, 120)}…` : plain
}
</script>

<template>
  <section class="workspace-outputs" aria-label="事项成果目录">
    <div class="outputs-heading"><div><h2>成果</h2><p>选一份成果阅读；历史版本和执行过程仅在需要时展开。</p></div><button type="button" class="lw-btn sm" @click="showManualEditor=true">登记人工成果</button></div>
    <ManualResultEditor v-if="showManualEditor" :item="item" @close="showManualEditor=false" @saved="showManualEditor=false; emit('updated')" />
    <div v-if="view.outputs.length" class="outputs-layout">
      <nav class="outputs-index" aria-label="成果列表"><button v-for="output in view.outputs" :key="output.id" type="button" class="index-entry" :class="{ active: selected?.id === output.id }" :aria-current="selected?.id === output.id ? 'true' : undefined" @click="emit('select', output.id)"><span class="entry-kind">{{ kindLabel(output) }}</span><strong>{{ output.title }}</strong></button></nav>
      <article v-if="selected" class="output-reader"><div class="reader-header"><div><span class="entry-kind">{{ kindLabel(selected) }}{{ selected.version ? ` · ${selected.version.slice(0, 12)}` : '' }}</span><h3>{{ selected.title }}</h3><p v-if="selected.summary">{{ shortSummary(selected.summary) }}</p></div><span v-if="selected.state" class="output-state">{{ stateLabel(selected.state) }}</span></div>
        <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
        <ResearchOutputPanel v-if="selected.kind === 'research' || (selected.kind === 'note' && !selected.artifactId)" :key="key" :workspace="workspace" :item-id="item.id" :selected-run-id="selected.runId" :selected-output-id="selected.id" compact @quote="emit('quote', $event)" @feedback-saved="emit('updated')" @candidate-created="emit('updated')" />
        <template v-else-if="selected.kind === 'development'"><MarkdownBody v-if="implementation?.result" :content="implementation.result" /><p v-else-if="!delivery" class="reader-muted">{{ selected.id.startsWith('delivery:') ? '固定交付正在准备或尚不可读。' : '此阶段尚无可读的 Run 正文。' }}</p><DevelopmentDelivery v-if="delivery" :key="delivery.id" :workspace="workspace" :delivery="delivery" @updated="emit('updated')" /><button v-if="selected.id.startsWith('delivery:') && selected.assignmentId" type="button" class="lw-btn sm" @click="showDiff">查看实际 Git 差异</button><details v-if="diff" open><summary>差异预览 · {{ diff.fileCount }} 个文件{{ diff.truncated ? '（已截断）' : '' }}</summary><pre class="diff-preview">{{ diff.patch || '没有代码差异' }}</pre></details></template>
        <template v-else><p v-if="artifactLoading" role="status" class="reader-muted">正在读取成果正文…</p><MarkdownBody v-else-if="artifactContent" :content="artifactContent" /><p v-else-if="selected.artifactId && !error" class="reader-muted">这份人工成果尚无可读正文。</p><a v-if="safeWorkLink(selected.uri) && !selected.artifactId" class="lw-btn sm" :href="safeWorkLink(selected.uri)!" target="_blank" rel="noopener noreferrer">打开成果来源</a><p v-else-if="!selected.artifactId && !artifactContent" class="reader-muted">{{ selected.summary || '此成果没有可安全打开的地址。' }}</p></template>
      </article>
    </div>
    <p v-else class="output-empty">尚无成果。可以先登记人工成果，也可以在工作步骤中继续推进。</p>
    <details v-if="selected?.kind === 'research'" class="secondary"><summary @click="showKnowledge = !showKnowledge">研究知识修订</summary><ResearchKnowledgeReview v-if="showKnowledge" :workspace="workspace" :item-id="item.id" @changed="emit('updated')" /></details>
    <details v-if="view.outputs.length || item.evidence.length" class="secondary acceptance"><summary>验收与证据 · {{ proven }}/{{ item.evidence.length }} 条已证明</summary><p>运行完成不代表事项已被接受。请核对成果范围和固定证据后，再确认结果。</p><ul v-if="item.evidence.length"><li v-for="evidence in item.evidence" :key="evidence.id || evidence.name"><button type="button" class="evidence-link" @click="openModal('evidence', { evidence, item })">{{ evidence.name }}</button><span> · {{ evidence.result || '待审阅' }}</span><small v-if="evidence.purpose">{{ evidence.purpose }}</small></li></ul><p v-else>尚未登记验证证据。</p><div class="acceptance-actions"><button type="button" class="lw-btn sm primary" :disabled="accepted" @click="openModal('accept-result', { item })">{{ accepted ? '事项已完成' : '接受本轮结果' }}</button><button type="button" class="lw-btn sm" @click="openModal('feedback', { item, anchor: '成果与验证' })">提出结果反馈</button></div></details>
  </section>
</template>

<style scoped>
.workspace-outputs { display: grid; gap: 18px; min-width: 0; }
.outputs-heading,.reader-header { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.outputs-heading h2 { margin: 0; font-size: 20px; }
.outputs-heading p,.reader-header p { margin: 5px 0 0; font-size: 12px; color: #667b90; }
.outputs-layout { display: grid; grid-template-columns: minmax(210px,260px) minmax(0,1fr); align-items: start; gap: 18px; min-width: 0; }
.outputs-index { display: grid; gap: 7px; max-height: 74vh; overflow-y: auto; }
.index-entry { text-align: left; display: grid; gap: 4px; border: 1px solid #e3e9f0; background: #fff; border-radius: 9px; padding: 11px 12px; cursor: pointer; }
.index-entry:hover,.index-entry:focus-visible { outline: 2px solid #83a9cd; outline-offset: 1px; }
.index-entry.active { border-color: #6894bd; background: #f4f8fc; }
.index-entry strong { color: #2d4359; font-size: 13px; }
.index-entry small { color: #708398; line-height: 1.4; }
.entry-kind { color: #507394; font-size: 11px; }
.output-reader { min-width: 0; display: grid; gap: 15px; padding: 22px; border: 1px solid #e1e8f0; background: #fff; border-radius: 12px; }
.reader-header h3 { margin: 4px 0 0; font-size: 18px; }
.output-state { white-space: nowrap; font-size: 11px; color: #597189; }
.reader-muted,.output-empty { color: #6b7f91; font-size: 13px; }
.output-empty { padding: 32px; border: 1px dashed #cddbe8; border-radius: 10px; background: #fbfcfe; }
.diff-preview { overflow: auto; max-height: 500px; padding: 12px; background: #f5f7fa; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; }
.secondary summary { cursor: pointer; color: #517294; }
.acceptance { padding: 14px 17px; border: 1px solid #e2e9f0; border-radius: 9px; background: #fff; font-size: 12px; color: #60758b; }
.acceptance ul { display: grid; gap: 8px; padding-left: 20px; }
.acceptance li small { display: block; margin-top: 3px; }
.evidence-link { padding: 0; border: 0; background: none; color: #315f8c; cursor: pointer; text-decoration: underline; }
.acceptance-actions { display: flex; gap: 9px; flex-wrap: wrap; margin-top: 12px; }
@media(max-width:790px){ .outputs-layout { grid-template-columns: 1fr; } .outputs-index { display: flex; overflow-x: auto; max-height: none; } .index-entry { flex: 0 0 210px; } .output-reader { padding: 16px; } }
</style>

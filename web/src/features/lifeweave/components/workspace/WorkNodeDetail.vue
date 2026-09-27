<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import type { WorkOutputRef, WorkStep } from '../../api/workView'
import type { WorkspaceKind } from '../../types'
import MarkdownBody from '../MarkdownBody.vue'
import WorkOutputReader from './WorkOutputReader.vue'
import { stepStateLabel } from './workGraphLayout'
import { safeWorkLink } from './safeWorkLink'
import { kindLabel } from './workOutputLabels'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string; node: WorkStep; nodes: WorkStep[]; outputs: WorkOutputRef[]; observed: boolean }>()
const emit = defineEmits<{
  output: [id: string]; run: [id: string]; edit: []; close: []; select: [id: string]; context: []; updated: []
  quote: [value: { text: string; runId: string | null; anchor: string }]
}>()
const heading = shallowRef<HTMLElement | null>(null)
const selectedId = shallowRef<string | null>(null)
const linked = computed(() => props.node.outputIds.map(id => props.outputs.find(output => output.id === id)).filter((output): output is WorkOutputRef => !!output))
const selected = computed(() => linked.value.find(output => output.id === selectedId.value) || linked.value[0] || null)
const missingOutputs = computed(() => props.node.outputIds.length - linked.value.length)
const previous = computed(() => props.nodes.filter(node => props.node.dependsOn.includes(node.id)))
const following = computed(() => props.nodes.filter(node => node.dependsOn.includes(props.node.id)))
const provenanceLabel = computed(() => props.node.provenance === 'declared' ? '计划记录' : props.node.provenance === 'observed' ? '实际记录' : props.node.provenance || '步骤记录')
const description = computed(() => props.node.description.trim() !== props.node.summary.trim() ? props.node.description : '')
const emptyReason = computed(() => {
  if (missingOutputs.value) return '已关联的成果目前不可读取。可以刷新重试，或检查计划中的成果关联。'
  if (props.node.state === 'running') return '这一步正在进行，尚未关联可读成果。'
  if (props.node.state === 'failed') return '这一步执行失败，尚未关联可读成果。可在下方查看运行记录，或讨论如何继续。'
  if (props.node.state === 'succeeded') return '这一步标记为已完成，但没有关联成果。完成状态本身不代表已有可读产物。'
  return '这一步尚未关联成果。已有的报告、方案或代码交付，需要关联到这一步后才会显示。'
})
watch(() => `${props.workspace}:${props.itemId}:${props.node.id}`, () => { selectedId.value = null })
function discuss() {
  const node = props.node
  // Keep the full description/conclusion and leave room for a question in the 20k composer.
  const title = (value: string) => value.length > 120 ? `${value.slice(0, 120)}…` : value
  const references = selected.value ? [selected.value, ...linked.value.filter(output => output.id !== selected.value?.id)] : linked.value
  const text = [
    `步骤：${node.title}`, `状态：${stepStateLabel[node.state]}`,
    node.description && `步骤说明：${node.description}`, node.summary && `当前记录：${node.summary}`,
    previous.value.length && `前置步骤：${previous.value.slice(0, 8).map(step => title(step.title)).join('、')}${previous.value.length > 8 ? `；另有 ${previous.value.length - 8} 个，见事项步骤图` : ''}`,
    references.length && `本步成果引用（当前阅读的在前）：\n${references.slice(0, 8).map(output => `- ${title(output.title)}（${output.id}）`).join('\n')}`,
    references.length > 8 && `另有 ${references.length - 8} 份关联产物，见本步产物目录。`,
  ].filter(Boolean).join('\n\n')
  emit('quote', { text, runId: node.runId || null, anchor: `步骤：${node.title} [${node.id}]` })
}
function focus() {
  heading.value?.focus({ preventScroll: true })
  heading.value?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
}
defineExpose({ focus })
</script>

<template>
  <section id="work-step-detail" class="node-detail" aria-label="所选步骤">
    <header class="detail-top">
      <div><p class="eyebrow">{{ provenanceLabel }} · {{ stepStateLabel[node.state] }}</p><h3 ref="heading" tabindex="-1">{{ node.title }}</h3></div>
      <button class="lw-btn ghost sm" type="button" @click="emit('close')">收起详情</button>
    </header>
    <p v-if="description" class="step-description">{{ description }}</p>
    <div v-if="node.summary" class="step-summary"><span class="field-label">{{ node.state === 'succeeded' ? '本步结论' : '当前进展' }}</span><MarkdownBody :content="node.summary" /></div>
    <div class="step-actions">
      <button class="lw-btn sm" type="button" @click="discuss">讨论这一步</button>
      <button class="text-action" type="button" @click="emit('edit')">{{ observed ? '另存计划并补充关联' : '编辑本步与成果关联' }}</button>
    </div>
    <div v-if="previous.length || following.length" class="step-neighbors">
      <div v-if="previous.length"><span class="field-label">前置步骤</span><div class="neighbor-links"><button v-for="step in previous" :key="step.id" type="button" @click="emit('select', step.id)">{{ step.title }} <small>{{ stepStateLabel[step.state] }}</small></button></div></div>
      <div v-if="following.length"><span class="field-label">后续步骤</span><div class="neighbor-links"><button v-for="step in following" :key="step.id" type="button" @click="emit('select', step.id)">{{ step.title }} <small>{{ stepStateLabel[step.state] }}</small></button></div></div>
    </div>
    <section class="step-outputs" aria-label="本步产物">
      <div class="outputs-heading"><h4>本步产物 <span v-if="linked.length">{{ linked.length }}</span></h4><button v-if="selected" class="text-action" type="button" @click="emit('output', selected.id)">在成果页阅读 ↗</button></div>
      <nav v-if="linked.length > 1" class="output-choices" aria-label="选择本步产物"><button v-for="output in linked" :key="output.id" type="button" :aria-current="selected?.id === output.id ? 'true' : undefined" @click="selectedId = output.id"><small>{{ kindLabel(output) }}</small>{{ output.title }}</button></nav>
      <p v-if="missingOutputs && linked.length" class="muted" role="status">另有 {{ missingOutputs }} 份关联成果目前不可读取。</p>
      <WorkOutputReader v-if="selected" :workspace="workspace" :item-id="itemId" :output="selected" :allow-history="false" @updated="emit('updated')" @quote="emit('quote', $event)" />
      <p v-else class="output-empty">{{ emptyReason }}</p>
    </section>
    <details class="step-background">
      <summary>背景与执行依据</summary>
      <div class="background-content">
        <div v-if="node.contextRefs?.length"><span class="field-label">本步引用</span><ul><li v-for="(ref, index) in node.contextRefs" :key="index"><a v-if="safeWorkLink(ref.uri)" :href="safeWorkLink(ref.uri)!" target="_blank" rel="noopener noreferrer">{{ ref.title }}</a><span v-else>{{ ref.title }}</span></li></ul></div>
        <p v-else class="muted">尚未登记独立的步骤背景引用。</p>
        <div class="step-actions"><button class="text-action" type="button" @click="emit('context')">查看事项共享背景</button><button v-if="node.runId" class="text-action" type="button" @click="emit('run', node.runId)">查看本步运行记录</button></div>
        <p v-if="node.assignmentId" class="technical-ref">开发委托：{{ node.assignmentId }}</p>
      </div>
    </details>
  </section>
</template>

<style scoped>
.node-detail { min-width: 0; border: 1px solid #b9cfe1; border-radius: 12px; background: #fff; padding: 24px; }
.detail-top,.outputs-heading { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
.eyebrow { margin: 0 0 6px; color: #597895; font-size: 12px; }
h3 { margin: 0; font-size: 21px; color: #273e53; overflow-wrap: anywhere; scroll-margin-top: 28px; }
h3:focus { outline: none; }
h4 { margin: 0; font-size: 15px; } h4 span { color: #617990; font-size: 12px; margin-left: 6px; }
.step-description,.step-summary p { margin: 12px 0 0; color: #3a5064; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.75; font-size: 14px; }
.step-summary { margin-top: 18px; } .step-summary :deep(.lw-markdown) { margin-top: 5px; font-size: 14px; line-height: 1.75; color: #3a5064; }
.field-label { font-size: 12px; font-weight: 650; color: #61768b; }
.step-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 15px; margin-top: 16px; }
.text-action { border: 0; padding: 3px 0; color: #38688e; background: none; cursor: pointer; font-size: 12px; text-align: left; }
.text-action:hover { text-decoration: underline; }
.step-neighbors { display: grid; gap: 12px; margin-top: 20px; padding-top: 16px; border-top: 1px solid #e6edf2; }
.neighbor-links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 7px; }
.neighbor-links button { padding: 7px 10px; border: 1px solid #dfe7ef; border-radius: 7px; background: #fafcfe; color: #37516a; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
.neighbor-links small { margin-left: 7px; color: #6e8295; }
.step-outputs { display: grid; gap: 12px; min-width: 0; margin-top: 22px; padding-top: 20px; border-top: 1px solid #e6edf2; }
.step-outputs :deep(.output-reader) { padding: 0; border: 0; border-radius: 0; }
.output-choices { display: flex; gap: 8px; overflow-x: auto; padding: 2px; }
.output-choices button { display: grid; flex: 0 0 min(250px,85%); gap: 4px; padding: 10px 12px; border: 1px solid #dde6ee; border-radius: 8px; background: #fff; color: #324d66; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.output-choices button[aria-current] { border-color: #6c97ba; background: #f2f7fb; }
.output-choices small { color: #6e8295; }
.output-empty,.muted { color: #6b7d8e; font-size: 13px; line-height: 1.7; margin: 0; }
.output-empty { padding: 18px; background: #f7f9fb; border-radius: 8px; }
.step-background { margin-top: 20px; border-top: 1px solid #e6edf2; padding-top: 15px; }
.step-background summary { cursor: pointer; color: #59728b; font-size: 12px; }
.background-content { margin-top: 12px; font-size: 13px; } .background-content li { margin-top: 6px; overflow-wrap: anywhere; }
.technical-ref { color: #8594a2; font-size: 11px; overflow-wrap: anywhere; }
@media(max-width:720px){ .node-detail { padding: 16px; } .detail-top { flex-wrap: wrap; } .outputs-heading { align-items: center; } }
</style>

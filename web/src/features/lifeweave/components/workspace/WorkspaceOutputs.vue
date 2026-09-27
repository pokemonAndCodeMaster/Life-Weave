<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import type { ItemWorkView } from '../../api/workView'
import type { OutputDocumentRef } from '../../api/outputFiles'
import type { WorkItem, WorkspaceKind } from '../../types'
import { useLifeWeaveWorkspace } from '../../composables/useLifeWeaveWorkspace'
import ResearchKnowledgeReview from '../ResearchKnowledgeReview.vue'
import WorkOutputReader from './WorkOutputReader.vue'
import { kindLabel } from './workOutputLabels'
import ManualResultEditor from '../ManualResultEditor.vue'

const props = defineProps<{ workspace: WorkspaceKind; item: WorkItem; view: ItemWorkView; selectedId: string | null; selectedPath?: string | null }>()
const emit = defineEmits<{ select: [id: string]; selectFile: [path: string]; readDocument: [document: OutputDocumentRef]; updated: []; quote: [value: { text: string; runId: string | null; anchor: string }] }>()
const { openModal } = useLifeWeaveWorkspace()
const selected = computed(() => props.view.outputs.find(output => output.id === props.selectedId) || props.view.outputs[0] || null)
const showManualEditor = shallowRef(false)
const showKnowledge = shallowRef(false)
const accepted = computed(() => ['已完成', 'accepted', 'completed'].includes(props.item.state))
const proven = computed(() => props.item.evidence.filter(entry => entry.result === '已证明' || entry.result === 'accepted').length)
watch(() => selected.value?.id, () => { showKnowledge.value = false })
</script>

<template>
  <section class="workspace-outputs" aria-label="事项成果目录">
    <div class="outputs-heading"><div><h2>成果</h2><p>选一份成果阅读；历史版本和执行过程仅在需要时展开。</p></div><button type="button" class="lw-btn sm" @click="showManualEditor=true">登记人工成果</button></div>
    <ManualResultEditor v-if="showManualEditor" :item="item" @close="showManualEditor=false" @saved="showManualEditor=false; emit('updated')" />
    <div v-if="view.outputs.length" class="outputs-layout">
      <nav class="outputs-index" aria-label="成果列表"><button v-for="output in view.outputs" :key="output.id" type="button" class="index-entry" :class="{ active: selected?.id === output.id }" :aria-current="selected?.id === output.id ? 'true' : undefined" @click="emit('select', output.id)"><span class="entry-kind">{{ kindLabel(output) }}</span><strong>{{ output.title }}</strong></button></nav>
      <WorkOutputReader v-if="selected" :workspace="workspace" :item-id="item.id" :output="selected" :selected-path="selectedPath" @updated="emit('updated')" @select-file="emit('selectFile', $event)" @read-document="emit('readDocument', $event)" @quote="emit('quote', $event)" />
    </div>
    <p v-else class="output-empty">尚无成果。可以先登记人工成果，也可以在工作步骤中继续推进。</p>
    <details v-if="selected?.kind === 'research'" class="secondary"><summary @click="showKnowledge = !showKnowledge">研究知识修订</summary><ResearchKnowledgeReview v-if="showKnowledge" :workspace="workspace" :item-id="item.id" @changed="emit('updated')" /></details>
    <details v-if="view.outputs.length || item.evidence.length" class="secondary acceptance"><summary>验收与证据 · {{ proven }}/{{ item.evidence.length }} 条已证明</summary><p>运行完成不代表事项已被接受。请核对成果范围和固定证据后，再确认结果。</p><ul v-if="item.evidence.length"><li v-for="evidence in item.evidence" :key="evidence.id || evidence.name"><button type="button" class="evidence-link" @click="openModal('evidence', { evidence, item })">{{ evidence.name }}</button><span> · {{ evidence.result || '待审阅' }}</span><small v-if="evidence.purpose">{{ evidence.purpose }}</small></li></ul><p v-else>尚未登记验证证据。</p><div class="acceptance-actions"><button type="button" class="lw-btn sm primary" :disabled="accepted" @click="openModal('accept-result', { item })">{{ accepted ? '事项已完成' : '接受本轮结果' }}</button><button type="button" class="lw-btn sm" @click="openModal('feedback', { item, anchor: '成果与验证' })">提出结果反馈</button></div></details>
  </section>
</template>

<style scoped>
.workspace-outputs { display: grid; gap: 18px; min-width: 0; }
.outputs-heading { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.outputs-heading h2 { margin: 0; font-size: 20px; }
.outputs-heading p { margin: 5px 0 0; font-size: 12px; color: #667b90; }
.outputs-layout { display: grid; grid-template-columns: minmax(210px,260px) minmax(0,1fr); align-items: start; gap: 18px; min-width: 0; }
.outputs-index { display: grid; gap: 7px; max-height: 74vh; overflow-y: auto; }
.index-entry { text-align: left; display: grid; gap: 4px; border: 1px solid #e3e9f0; background: #fff; border-radius: 9px; padding: 11px 12px; cursor: pointer; }
.index-entry:hover,.index-entry:focus-visible { outline: 2px solid #83a9cd; outline-offset: 1px; }
.index-entry.active { border-color: #6894bd; background: #f4f8fc; }
.index-entry strong { color: #2d4359; font-size: 13px; }
.index-entry small { color: #708398; line-height: 1.4; }
.entry-kind { color: #507394; font-size: 11px; }
.output-empty { color: #6b7f91; font-size: 13px; }
.output-empty { padding: 32px; border: 1px dashed #cddbe8; border-radius: 10px; background: #fbfcfe; }
.secondary summary { cursor: pointer; color: #517294; }
.acceptance { padding: 14px 17px; border: 1px solid #e2e9f0; border-radius: 9px; background: #fff; font-size: 12px; color: #60758b; }
.acceptance ul { display: grid; gap: 8px; padding-left: 20px; }
.acceptance li small { display: block; margin-top: 3px; }
.evidence-link { padding: 0; border: 0; background: none; color: #315f8c; cursor: pointer; text-decoration: underline; }
.acceptance-actions { display: flex; gap: 9px; flex-wrap: wrap; margin-top: 12px; }
@media(max-width:790px){ .outputs-layout { grid-template-columns: 1fr; } .outputs-index { display: flex; overflow-x: auto; max-height: none; } .index-entry { flex: 0 0 210px; } }
</style>

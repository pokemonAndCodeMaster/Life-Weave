<script setup lang="ts">
import { computed } from 'vue'
import type { WorkOutputRef, WorkStep } from '../../api/workView'
import { stepStateLabel } from './workGraphLayout'
import { safeWorkLink } from './safeWorkLink'

const props = defineProps<{ node: WorkStep; outputs: WorkOutputRef[] }>()
const emit = defineEmits<{ output: [id: string]; run: [id: string]; edit: []; close: [] }>()
const linked = computed(() => props.node.outputIds.map(id => props.outputs.find(output => output.id === id)).filter((output): output is WorkOutputRef => !!output))
const provenanceLabel = computed(() => props.node.provenance === 'declared' ? '用户声明' : props.node.provenance === 'observed' ? '实际记录' : props.node.provenance || '步骤记录')
</script>

<template>
  <section class="node-detail" aria-label="所选步骤">
    <div class="detail-top"><div><p class="eyebrow">{{ provenanceLabel }} · {{ stepStateLabel[node.state] }}</p><h3>{{ node.title }}</h3></div><div class="detail-actions"><button class="lw-btn ghost sm" type="button" @click="emit('edit')">编辑步骤</button><button class="lw-btn ghost sm" type="button" @click="emit('close')">收起详情</button></div></div>
    <div class="detail-grid"><div><span class="field-label">本步目标</span><p>{{ node.description || '尚未填写这一步的目标。' }}</p></div><div><span class="field-label">当前结论</span><p>{{ node.summary || '尚无本步结论；此处不推断工作已经完成。' }}</p></div></div>
    <div v-if="linked.length" class="linked-outputs"><span class="field-label">关联成果</span><div class="output-links"><button v-for="output in linked" :key="output.id" type="button" class="output-link" @click="emit('output', output.id)"><strong>{{ output.title }}</strong></button></div></div>
    <div class="detail-actions"><button v-if="node.runId" type="button" class="lw-btn sm" @click="emit('run', node.runId!)">查看本步运行依据</button><span v-if="node.assignmentId" class="detail-id">开发委托 {{ node.assignmentId }}</span></div>
    <details v-if="node.contextRefs?.length"><summary>背景与引用（{{ node.contextRefs.length }}）</summary><ul><li v-for="(ref,index) in node.contextRefs" :key="`${index}:${ref.title}`"><a v-if="safeWorkLink(ref.uri)" :href="safeWorkLink(ref.uri)!" target="_blank" rel="noopener noreferrer">{{ ref.title }}</a><template v-else>{{ ref.title }}<span v-if="ref.uri" class="detail-id"> · {{ ref.uri }}</span></template></li></ul></details>
  </section>
</template>

<style scoped>
.node-detail { display: grid; gap: 16px; padding: 20px 22px; border: 1px solid #e0e7ee; border-radius: 12px; background: #fff; min-width: 0; }
.detail-top { display: flex; justify-content: space-between; align-items: start; gap: 16px; }
.eyebrow,.field-label { color: #57728f; font-size: 11px; letter-spacing: .03em; }
.eyebrow { margin: 0 0 5px; }
.detail-top h3 { font-size: 18px; margin: 0; color: #203144; }
.detail-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 20px; }
.detail-grid p { margin: 6px 0 0; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.linked-outputs { display: grid; gap: 8px; }
.output-links { display: flex; flex-wrap: wrap; gap: 8px; }
.output-link { display: grid; gap: 3px; min-width: 180px; max-width: 320px; text-align: left; border: 1px solid #d9e5f0; background: #f7fafd; border-radius: 8px; padding: 9px 11px; cursor: pointer; }
.output-link:hover,.output-link:focus-visible { outline: 2px solid #7ba2c9; outline-offset: 2px; }
.output-link strong { font-size: 12px; color: #244b72; }
.output-link span,.detail-id { font-size: 11px; color: #6b7f93; overflow-wrap: anywhere; }
.detail-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.node-detail details { color: #52677d; font-size: 12px; }
.node-detail summary { cursor: pointer; }
.node-detail ul { padding-left: 19px; }
@media(max-width:720px){ .node-detail { padding: 16px; } .detail-grid { grid-template-columns: 1fr; gap: 14px; } }
</style>

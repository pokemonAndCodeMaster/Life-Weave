<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import { apiError } from '../../api/lifeweave'
import { saveItemOverview, type ItemWorkView } from '../../api/workView'
import type { WorkItem, WorkspaceKind } from '../../types'

const props = defineProps<{ workspace: WorkspaceKind; item: WorkItem; view: ItemWorkView }>()
const emit = defineEmits<{ saved: [view: ItemWorkView]; output: [id: string] }>()
const editing = shallowRef(false)
const saving = shallowRef(false)
const error = shallowRef('')
const expanded = shallowRef(false)
const form = reactive({ background: '', intent: '', expectedResult: '' })
const overview = computed(() => props.view.overview)
const outputs = computed(() => {
  const ids = overview.value?.outputIds ?? props.view.outputs.map(output => output.id)
  return ids.map(id => props.view.outputs.find(output => output.id === id)).filter((output): output is ItemWorkView['outputs'][number] => !!output)
})
const visibleOutputs = computed(() => expanded.value ? outputs.value : outputs.value.slice(0, 3))
function readingSummary(value: string | null | undefined, limit: number): string {
  if (!value) return ''
  const cleaned = value
    .replace(/```[^\n]*\n[\s\S]*?```/g, ' ')
    .replace(/```[\s\S]*$/g, ' ')
    .replace(/!?\[([^\]]+)\]\s*\([^)]*\)/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, '$1$2')
    .replace(/\/(?:[^/\s"'`()[\]<>]+\/)+([^/\s"'`()[\]<>]+)/g, '$1')
  const paragraphs = cleaned.split(/\n\s*\n/).map(part => part.replace(/\s+/g, ' ').trim()).filter(Boolean)
  const first = paragraphs.find(part => part.length >= 20) ?? paragraphs[0] ?? ''
  return first.length > limit ? `${first.slice(0, limit).trimEnd()}…` : first
}
const progressSummary = computed(() => readingSummary(overview.value?.progress.summary || props.view.current.summary, 180) || '暂无可确认的进展记录。')

watch(() => [props.item.id, props.view.itemVersion, props.view.overview], () => {
  if (editing.value) return
  form.background = overview.value?.background ?? ''
  form.intent = overview.value?.intent ?? props.item.goal ?? ''
  form.expectedResult = overview.value?.expectedResult ?? ''
}, { immediate: true })

async function save() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const result = await saveItemOverview(props.workspace, props.item.id, { version: props.view.itemVersion, ...form })
    editing.value = false
    emit('saved', result)
  } catch (caught) { error.value = apiError(caught).message }
  finally { saving.value = false }
}
</script>

<template>
  <section class="work-overview" aria-labelledby="overview-heading">
    <header class="overview-header"><div><span class="section-kicker">事项概览</span><h2 id="overview-heading">{{ item.title }}</h2></div><button type="button" class="lw-btn sm" @click="editing = !editing">{{ editing ? '取消编辑' : '编辑介绍' }}</button></header>
    <p v-if="error" role="alert" class="lw-notice warning">{{ error }}</p>
    <form v-if="editing" class="overview-form" @submit.prevent="save">
      <label class="lw-label">背景<textarea v-model="form.background" class="lw-field" rows="3" placeholder="这件事从何而来？" /></label>
      <label class="lw-label">要做什么<textarea v-model="form.intent" class="lw-field" rows="3" required placeholder="本次工作的目标" /></label>
      <label class="lw-label">预期结果<textarea v-model="form.expectedResult" class="lw-field" rows="3" placeholder="完成后应得到什么？" /></label>
      <p class="lw-tiny lw-muted">这里编辑的是事项介绍；步骤报告和实际成果仍以各自记录为准。</p>
      <button type="submit" class="lw-btn primary" :disabled="saving">{{ saving ? '保存中…' : '保存介绍' }}</button>
    </form>
    <div v-else class="overview-grid">
      <div class="overview-fact"><h3>背景</h3><p>{{ overview?.background || '尚未记录背景。' }}</p></div>
      <div class="overview-fact"><h3>要做什么</h3><p>{{ overview?.intent || item.goal || '尚未写明工作目标。' }}</p></div>
      <div class="overview-fact"><h3>预期结果</h3><p>{{ overview?.expectedResult || '尚未写明预期结果。' }}</p></div>
      <div class="overview-fact"><h3>真实进展</h3><p>{{ progressSummary }}</p><span v-if="overview?.progress.totalSteps" class="overview-meta">{{ overview.progress.completedSteps }} / {{ overview.progress.totalSteps }} 步完成</span></div>
      <div class="overview-fact outputs"><h3>实际产出</h3><p v-if="!outputs.length">目前尚无可阅读的实际产出。</p><ul v-else><li v-for="output in visibleOutputs" :key="output.id"><button type="button" class="lw-text-btn output-title" @click="emit('output', output.id)">{{ output.title }}</button><span v-if="output.summary" class="output-summary">{{ readingSummary(output.summary, 160) }}</span></li></ul><button v-if="outputs.length > 3" type="button" class="lw-text-btn" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '收起' : `查看全部 ${outputs.length} 项` }}</button></div>
    </div>
  </section>
</template>

<style scoped>
.work-overview{border:1px solid #e1e8ee;border-left:4px solid #648eb7;background:#fff;border-radius:12px;padding:21px 23px;min-width:0}.overview-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.section-kicker{color:#597b9d;font-size:11px;letter-spacing:.04em}.overview-header h2{margin:5px 0 0;font-size:19px;color:#263a4f}.overview-form{display:grid;gap:12px;margin-top:16px}.overview-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 28px;margin-top:18px}.overview-fact h3{font-size:12px;color:#58728b;margin:0 0 5px}.overview-fact p{font-size:13px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}.overview-fact.outputs{grid-column:1/-1}.overview-fact ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}.overview-fact li{display:flex;align-items:flex-start;gap:12px;min-width:0}.overview-fact li .output-title{flex:0 0 128px;min-width:92px;max-width:35%;text-align:left;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere}.overview-fact li .output-summary{flex:1 1 0;min-width:0;font-size:12px;color:#65788b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.overview-meta{font-size:11px;color:#65788b}@media(max-width:720px){.work-overview{padding:16px}.overview-grid{grid-template-columns:1fr}.overview-fact.outputs{grid-column:auto}.overview-header{flex-wrap:wrap}}
</style>

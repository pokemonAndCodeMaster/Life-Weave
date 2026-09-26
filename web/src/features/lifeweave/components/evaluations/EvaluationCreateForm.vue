<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { EvaluationTask } from '../../api/lifeweave'

interface Candidate { id: string; title: string; status: string; version?: string }
interface Item { id: string; title: string }
const props = defineProps<{ candidates: Candidate[]; items: Item[]; busy: boolean; template?: EvaluationTask | null; initialItemId?: string; initialPluginCallId?: string }>()
const emit = defineEmits<{ create: [payload: { itemId: string; targetKind: 'system' | 'capability' | 'plugin'; candidateId?: string; pluginCallId?: string; repeatOf?: string; title: string; instruction: string; criteria: string }]; clearTemplate: [] }>()
const form = reactive({ itemId: '', targetKind: 'system' as 'system' | 'capability' | 'plugin', candidateId: '', pluginCallId: '', title: '', instruction: '', criteria: '' })
const candidates = computed(() => props.candidates.filter(entry => ['candidate', 'verified'].includes(entry.status)))
watch(() => [props.initialItemId, props.initialPluginCallId], ([itemId, callId]) => {
  if (!itemId || !callId || props.template) return
  form.itemId = itemId; form.pluginCallId = callId; form.targetKind = 'plugin'
}, { immediate: true })
watch(() => props.template, (entry) => {
  if (!entry) return
  Object.assign(form, { itemId: entry.itemId, targetKind: entry.targetKind,
    candidateId: candidates.value.some(candidate => candidate.id === entry.candidateId) ? entry.candidateId ?? '' : '',
    pluginCallId: entry.targetKind === 'plugin' ? '' : entry.pluginCallId ?? '',
    title: `${entry.title} · 再评`, instruction: entry.instruction, criteria: entry.criteria })
})
const ready = computed(() => Boolean(form.itemId.trim() && form.title.trim() && form.instruction.trim() && form.criteria.trim()
  && (form.targetKind === 'system' || (form.targetKind === 'plugin' ? form.pluginCallId.trim() : form.candidateId))))
function submit() {
  if (!ready.value) return
  emit('create', { itemId: form.itemId.trim(), targetKind: form.targetKind,
    ...(props.template ? { repeatOf: props.template.id } : {}),
    ...(form.targetKind === 'capability' ? { candidateId: form.candidateId } : {}),
    ...(form.targetKind === 'plugin' ? { pluginCallId: form.pluginCallId.trim() } : {}),
    title: form.title.trim(), instruction: form.instruction.trim(), criteria: form.criteria.trim() })
}
</script>

<template>
  <form class="evaluation-form" @submit.prevent="submit">
    <p v-if="template" class="lw-notice neutral">沿用 {{ template.id }} 的同一任务与通过标准；{{ template.targetKind === 'plugin' ? '请填入同一插件的新调用 ID。' : '可选择新的候选版本进行对照。' }}<button class="lw-text-btn" type="button" @click="emit('clearTemplate')">改为新评测</button></p>
    <div class="evaluation-grid">
      <label class="lw-label">所属事项 ID
        <input v-model="form.itemId" class="lw-field" list="evaluation-items" required :disabled="Boolean(template)" placeholder="选择已有事项或输入 ID" />
        <datalist id="evaluation-items"><option v-for="item in items" :key="item.id" :value="item.id">{{ item.title }}</option></datalist>
      </label>
      <label class="lw-label">评测对象
        <select v-model="form.targetKind" class="lw-field" :disabled="Boolean(template)"><option value="system">整件事 / 平台能力</option><option value="capability">一项能力候选</option><option value="plugin">一次真实插件调用</option></select>
      </label>
    </div>
    <label v-if="form.targetKind === 'capability'" class="lw-label">候选版本
      <select v-model="form.candidateId" class="lw-field" required><option value="">请选择</option><option v-for="candidate in candidates" :key="candidate.id" :value="candidate.id">{{ candidate.title }} · {{ candidate.status }} · {{ candidate.version?.slice(0, 10) }}</option></select>
    </label>
    <label v-if="form.targetKind === 'plugin'" class="lw-label">插件调用 ID
      <input v-model="form.pluginCallId" class="lw-field" required placeholder="从事项的插件过程复制 pcall-…" />
    </label>
    <label class="lw-label">评测名称<input v-model="form.title" class="lw-field" required placeholder="例如：金铲铲攻略是否能解释阵容选择" /></label>
    <label class="lw-label">{{ form.targetKind === 'plugin' ? '本次调用要完成什么' : '交给 AI 的任务' }}<textarea v-model="form.instruction" class="lw-field" rows="3" required :disabled="Boolean(template)" placeholder="写清要完成什么；创建评测时不会启动 AI" /></label>
    <label class="lw-label">怎样判断通过<textarea v-model="form.criteria" class="lw-field" rows="3" required :disabled="Boolean(template)" placeholder="写可观察的成果和过程要求，例如引用版本、解释取舍、指出未知" /></label>
    <button class="lw-btn primary" type="submit" :disabled="busy || !ready">保存评测任务</button>
  </form>
</template>

<style scoped>
.evaluation-form { display: grid; gap: 12px; }
.evaluation-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
@media (max-width: 680px) { .evaluation-grid { grid-template-columns: 1fr; } }
</style>

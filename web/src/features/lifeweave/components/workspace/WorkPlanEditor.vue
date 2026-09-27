<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import type { ItemWorkView, WorkStep, WorkStepState } from '../../api/workView'

const props = defineProps<{ view: ItemWorkView; saving: boolean; error: string; conflict: boolean; outputs: Array<{ id: string; title: string }>; resetKey?: number }>()
const emit = defineEmits<{ save: [value: { version: number; title: string; provider: string; nodes: WorkStep[] }]; cancel: []; reload: [] }>()
const element = shallowRef<HTMLElement | null>(null)
function focusStep(id: string) {
  const step = Array.from(element.value?.querySelectorAll<HTMLElement>('[data-editor-step]') || []).find(el => el.dataset.editorStep === id)
  step?.scrollIntoView?.({ block: 'center' })
  step?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true })
}
defineExpose({ focusStep })
const form = reactive({ title: '', provider: '' })
const nodes = shallowRef<WorkStep[]>([])
const localError = shallowRef('')
const sourceVersion = shallowRef(0)
const observed = computed(() => props.view.plan.source === 'observed')
function reset() {
  sourceVersion.value = props.view.itemVersion
  form.title = props.view.plan.title || '我的工作计划'
  form.provider = props.view.plan.source === 'empty' ? 'manual' : props.view.plan.provider || 'manual'
  nodes.value = props.view.plan.nodes.map(node => ({ ...node, dependsOn: [...node.dependsOn], outputIds: [...node.outputIds] }))
  localError.value = ''
}
watch([() => props.view.itemId, () => props.resetKey], reset, { immediate: true })
function add() {
  if (nodes.value.length >= 80) { localError.value = '一份计划最多 80 个步骤'; return }
  nodes.value = [...nodes.value, { id: `step-${crypto.randomUUID()}`, title: '', description: '', state: 'planned', summary: '', dependsOn: [], outputIds: [] }]
}
function remove(id: string) {
  nodes.value = nodes.value.filter(node => node.id !== id).map(node => ({ ...node, dependsOn: node.dependsOn.filter(dep => dep !== id) }))
}
function update(id: string, patch: Partial<WorkStep>) {
  nodes.value = nodes.value.map(node => node.id === id ? { ...node, ...patch } : node)
}
function toggleDependency(id: string, dependency: string, checked: boolean) {
  const target = nodes.value.find(node => node.id === id)
  if (!target) return
  update(id, { dependsOn: checked ? [...target.dependsOn, dependency] : target.dependsOn.filter(dep => dep !== dependency) })
}
function toggleOutput(id: string, outputId: string, checked: boolean) {
  const target = nodes.value.find(node => node.id === id)
  if (!target) return
  update(id, { outputIds: checked ? [...target.outputIds, outputId] : target.outputIds.filter(value => value !== outputId) })
}
function submit() {
  localError.value = ''
  if (!form.title.trim() || !form.provider.trim()) { localError.value = '请填写计划名称和能力来源'; return }
  if (nodes.value.some(node => !node.title.trim())) { localError.value = '每个步骤都需要标题'; return }
  const ids = new Set(nodes.value.map(node => node.id))
  if (ids.size !== nodes.value.length || nodes.value.some(node => node.dependsOn.some(dep => dep === node.id || !ids.has(dep)))) {
    localError.value = '步骤依赖存在无效引用'; return
  }
  const done = new Set<string>()
  const active = new Set<string>()
  const byId = new Map(nodes.value.map(node => [node.id, node]))
  function cyclic(id: string): boolean {
    if (active.has(id)) return true
    if (done.has(id)) return false
    active.add(id)
    if (byId.get(id)?.dependsOn.some(cyclic)) return true
    active.delete(id); done.add(id); return false
  }
  if (nodes.value.some(node => cyclic(node.id))) { localError.value = '步骤依赖不能形成循环'; return }
  emit('save', { version: sourceVersion.value, title: form.title.trim(), provider: form.provider.trim(), nodes: nodes.value.map(node => ({ ...node, title: node.title.trim(), description: node.description.trim(), summary: node.summary.trim() })) })
}
const states: Array<{ value: WorkStepState; label: string }> = [
  { value: 'planned', label: '待开始' }, { value: 'running', label: '进行中' }, { value: 'waiting', label: '等待中' },
  { value: 'succeeded', label: '已完成（人工记录）' }, { value: 'failed', label: '失败' }, { value: 'cancelled', label: '已取消' },
  { value: 'unobserved', label: '尚无执行记录' },
]
</script>

<template>
  <form ref="element" class="plan-editor" @submit.prevent="submit">
    <div class="editor-heading"><div><h3>{{ observed ? '将观察记录另存为声明计划' : '编辑步骤计划' }}</h3><p v-if="observed" class="editor-note">会保留当前节点的运行与成果引用；原始执行记录不会被改写。</p></div><button type="button" class="lw-btn ghost sm" @click="emit('cancel')">关闭</button></div>
    <p v-if="error || localError" role="alert" class="lw-notice warning">{{ localError || error }}</p>
    <button v-if="conflict" type="button" class="lw-btn sm" @click="emit('reload')">刷新后重新编辑</button>
    <div class="plan-fields"><label class="lw-label">计划名称<input v-model="form.title" class="lw-field" maxlength="200" required /></label><label class="lw-label">能力来源<input v-model="form.provider" class="lw-field" maxlength="100" required placeholder="例如：人工、研究方法、开发 Agent" /></label></div>
    <ol class="editor-steps"><li v-for="node in nodes" :key="node.id" class="editor-step" :data-editor-step="node.id">
      <div class="editor-heading"><strong>{{ node.title || '新步骤' }}</strong><button type="button" class="lw-btn ghost sm" @click="remove(node.id)">删除步骤</button></div>
      <div class="plan-fields"><label class="lw-label">步骤名称<input :value="node.title" class="lw-field" maxlength="200" required @input="update(node.id, { title: ($event.target as HTMLInputElement).value })" /></label><label class="lw-label">记录状态<select :value="node.state" class="lw-field" aria-label="记录状态" @change="update(node.id, { state: ($event.target as HTMLSelectElement).value as WorkStepState })"><option v-for="state in states" :key="state.value" :value="state.value">{{ state.label }}</option></select></label></div>
      <label class="lw-label">这一步要做什么<textarea :value="node.description" class="lw-field" maxlength="5000" rows="2" @input="update(node.id, { description: ($event.target as HTMLTextAreaElement).value })"></textarea></label>
      <label class="lw-label">当前短结论<textarea :value="node.summary" class="lw-field" maxlength="2000" rows="2" @input="update(node.id, { summary: ($event.target as HTMLTextAreaElement).value })"></textarea></label>
      <details v-if="nodes.length > 1"><summary>依赖哪些步骤（{{ node.dependsOn.length }}）</summary><label v-for="candidate in nodes.filter(value => value.id !== node.id)" :key="candidate.id" class="check-row"><input type="checkbox" :checked="node.dependsOn.includes(candidate.id)" @change="toggleDependency(node.id, candidate.id, ($event.target as HTMLInputElement).checked)" />{{ candidate.title || '未命名步骤' }}</label></details>
      <details v-if="outputs.length"><summary>关联已有成果（{{ node.outputIds.length }}）</summary><label v-for="output in outputs" :key="output.id" class="check-row"><input type="checkbox" :checked="node.outputIds.includes(output.id)" @change="toggleOutput(node.id, output.id, ($event.target as HTMLInputElement).checked)" />{{ output.title }}</label></details>
      <p v-if="node.runId || node.assignmentId" class="editor-note">保留绑定：{{ node.runId || node.assignmentId }}</p>
    </li></ol>
    <div class="editor-actions"><button type="button" class="lw-btn" :disabled="nodes.length >= 80" @click="add">添加步骤</button><button type="submit" class="lw-btn primary" :disabled="saving">{{ saving ? '正在保存…' : observed ? '另存为声明计划' : '保存步骤计划' }}</button></div>
  </form>
</template>

<style scoped>
.plan-editor { display: grid; gap: 15px; padding: 20px; border: 1px solid #dce5ee; border-radius: 12px; background: #fff; }
.editor-heading,.editor-actions { display: flex; align-items: start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.editor-heading h3 { margin: 0; font-size: 16px; }
.editor-note { color: #64788e; font-size: 12px; margin: 3px 0 0; }
.plan-fields { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
.editor-steps { display: grid; gap: 12px; list-style: none; padding: 0; margin: 0; max-height: 600px; overflow-y: auto; }
.editor-step { display: grid; gap: 9px; padding: 15px; border: 1px solid #e5eaf0; border-radius: 10px; background: #fbfcfe; }
.editor-step details { font-size: 12px; color: #52677d; }
.editor-step summary { cursor: pointer; }
.check-row { display: flex; align-items: center; gap: 7px; margin-top: 7px; }
@media(max-width:700px){ .plan-fields { grid-template-columns: 1fr; } .plan-editor { padding: 14px; } }
</style>

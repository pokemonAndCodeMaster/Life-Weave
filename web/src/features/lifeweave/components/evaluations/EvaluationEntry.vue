<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'
import type { EvaluationTask } from '../../api/lifeweave'
import type { WorkspaceKind } from '../../types'
import StatusBadge from '../StatusBadge.vue'

const props = withDefaults(defineProps<{ entry: EvaluationTask; workspace: WorkspaceKind; busy: boolean;
  methods?: Array<{ id: string; title: string; description: string }>;
  knowledge?: Array<{ ref: string; title: string }> }>(), { methods: () => [], knowledge: () => [] })
const emit = defineEmits<{
  start: [id: string, payload: { engine: 'codex' | 'opencode'; permission: 'read-only' | 'workspace-write'; model?: string;
    directory?: string; methodId?: string; knowledgeRefs: string[] }]
  assess: [id: string, payload: { outcome: 'passed' | 'failed' | 'inconclusive'; assessment: string; evidenceId?: string }]
  improve: [id: string, payload: { targetKind: 'knowledge' | 'skill' | 'agent' | 'harness'; problem: string; desiredBehavior: string; validationPlan: string }]
  reuse: [entry: EvaluationTask]
}>()
const startForm = reactive({ engine: 'codex' as 'codex' | 'opencode', permission: 'read-only' as 'read-only' | 'workspace-write',
  model: '', directory: '', methodId: '', knowledgeRefs: [] as string[] })
const assessment = reactive({ outcome: 'inconclusive' as 'passed' | 'failed' | 'inconclusive', body: '', evidenceId: '' })
const showingImprovement = shallowRef(false)
const improvement = reactive({ targetKind: 'harness' as 'knowledge' | 'skill' | 'agent' | 'harness', problem: '', desiredBehavior: '', validationPlan: '' })
const terminal = computed(() => props.entry.targetKind === 'plugin'
  ? (!props.entry.run || ['succeeded', 'failed', 'unavailable', 'cancelled'].includes(props.entry.run.state))
  : ['succeeded', 'failed', 'unavailable', 'cancelled'].includes(props.entry.run?.state ?? ''))
const acceptedEvidence = computed(() => (props.entry.evidence ?? []).filter(entry => entry.status === 'accepted'))
const validInputs = computed(() => startForm.knowledgeRefs.length <= 10)
const evaluationStatus = computed(() => ({ planned: '待启动', running: '待判断', passed: '评测通过',
  failed: '评测未通过', inconclusive: '无法判断' }[props.entry.outcome || (props.entry.state === 'assessed' ? 'inconclusive' : props.entry.state)]))
const evaluationTone = computed(() => props.entry.outcome === 'passed' ? 'green' :
  props.entry.outcome === 'failed' ? 'red' : props.entry.state === 'planned' ? 'amber' : 'blue')
function submitAssessment() {
  if (!assessment.body.trim() || (assessment.outcome === 'passed' && props.entry.runId && !assessment.evidenceId)) return
  emit('assess', props.entry.id, { outcome: assessment.outcome, assessment: assessment.body.trim(),
    ...(assessment.outcome === 'passed' && assessment.evidenceId ? { evidenceId: assessment.evidenceId } : {}) })
}
function beginImprovement() {
  improvement.targetKind = props.entry.targetKind === 'system' ? 'harness' : 'skill'
  improvement.problem = props.entry.assessment ?? ''
  improvement.desiredBehavior = props.entry.criteria
  improvement.validationPlan = `沿评测 ${props.entry.id} 的同一任务和通过标准再评，比较运行过程与结果。`
  showingImprovement.value = true
}
function submitImprovement() {
  if (!improvement.problem.trim() || !improvement.desiredBehavior.trim() || !improvement.validationPlan.trim()) return
  emit('improve', props.entry.id, {
    targetKind: improvement.targetKind, problem: improvement.problem.trim(),
    desiredBehavior: improvement.desiredBehavior.trim(), validationPlan: improvement.validationPlan.trim(),
  })
}
</script>

<template>
  <article class="evaluation-entry">
    <div class="evaluation-heading"><div><h3>{{ entry.title }}</h3><p class="lw-small lw-sub">{{ entry.targetKind === 'system' ? '整件事 / 平台' : entry.targetKind === 'plugin' ? `插件 ${entry.pluginId} · ${entry.pluginVersion} · 调用 ${entry.pluginCallId}` : `能力候选 ${entry.candidateId} · ${entry.candidateVersion?.slice(0, 10)}` }}</p></div><StatusBadge :value="entry.outcome || entry.state" :tone="evaluationTone">{{ evaluationStatus }}</StatusBadge></div>
    <p class="evaluation-label">本次任务</p><p class="evaluation-copy">{{ entry.instruction }}</p>
    <p class="evaluation-label">通过标准</p><p class="evaluation-copy">{{ entry.criteria }}</p>
    <p v-if="entry.previous" class="lw-small lw-sub">对照前次 {{ entry.previous.id }}：{{ entry.previous.outcome === 'passed' ? '通过' : entry.previous.outcome === 'failed' ? '未通过' : '无法判断' }} · {{ entry.previous.candidateVersion?.slice(0, 10) || (entry.targetKind === 'plugin' ? '同一插件' : '平台整体') }}。{{ entry.previous.assessment }}</p>
    <div class="evaluation-links"><RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(entry.itemId)}/outputs`">打开事项与证据</RouterLink><RouterLink v-if="entry.runId" :to="{ path: `/lifeweave/${workspace}/runs`, query: { runId: entry.runId } }">查看运行过程 · {{ entry.runId }}</RouterLink></div>
    <form v-if="entry.state === 'planned'" class="evaluation-action" @submit.prevent="validInputs && emit('start', entry.id, { engine: startForm.engine, permission: startForm.permission, model: startForm.model || undefined, directory: startForm.directory.trim() || undefined, methodId: startForm.methodId || undefined, knowledgeRefs: startForm.knowledgeRefs })">
      <div class="evaluation-grid"><label class="lw-label">执行器<select v-model="startForm.engine" class="lw-field"><option value="codex">Codex</option><option value="opencode">OpenCode</option></select></label><label class="lw-label">工作目录权限<select v-model="startForm.permission" class="lw-field"><option value="read-only">只读</option><option value="workspace-write">允许写入隔离目录</option></select></label></div>
      <label class="lw-label">模型（可选）<input v-model="startForm.model" class="lw-field" placeholder="留空使用执行器默认模型" /></label>
      <label class="lw-label">要核验的 Git 仓库目录（可选）<input v-model="startForm.directory" class="lw-field" placeholder="不填则在空的隔离目录运行" /></label>
      <label class="lw-label">工作方法（可选）<select v-model="startForm.methodId" class="lw-field"><option value="">不附带方法</option><option v-for="method in methods" :key="method.id" :value="method.id">{{ method.title }}</option></select></label>
      <label v-if="knowledge.length" class="lw-label">附带知识（最多 10 篇，可多选）<select v-model="startForm.knowledgeRefs" class="lw-field" multiple size="4"><option v-for="doc in knowledge" :key="doc.ref" :value="doc.ref">{{ doc.title }}</option></select></label>
      <p v-if="!validInputs" class="lw-small lw-sub" role="alert">本轮最多附带 10 篇知识，请缩小选择。</p>
      <p class="lw-small lw-sub">仓库版本、方法和知识会在启动时固定为本轮输入；不填仓库时，AI 无法核验本机项目源码。</p>
      <button type="submit" class="lw-btn primary" :disabled="busy || !validInputs">开始真实评测</button>
    </form>
    <div v-else-if="entry.state === 'running'">
      <p v-if="entry.targetKind === 'plugin'" class="lw-small lw-sub">固定调用：{{ entry.pluginCall?.operation }} · {{ entry.pluginCall?.state }} · 实现 {{ entry.pluginCall?.implementation_digest?.slice(0, 12) }}。请对照本次调用和原始事项判断，调用成功不自动等于评测通过。</p>
      <template v-else><p class="lw-small lw-sub">运行状态：{{ entry.run?.state ?? '读取中' }}。请到事项中阅读成果和过程，接受对应证据后再判断是否通过。</p>
      <p class="lw-small lw-sub">本轮输入：{{ entry.run?.repositoryPath ? `仓库 ${entry.run.repositoryPath} @ ${entry.run.repositoryRevision?.slice(0, 10) || '未固定提交'}` : '空隔离目录' }}；方法 {{ entry.run?.selectedInputs?.methodId || '无' }}；知识 {{ entry.run?.selectedInputs?.knowledgeRefs?.length || 0 }} 篇。</p></template>
      <form v-if="terminal" class="evaluation-action" @submit.prevent="submitAssessment">
        <label class="lw-label">判断<select v-model="assessment.outcome" class="lw-field"><option value="inconclusive">暂无法判断</option><option value="failed">未通过</option><option value="passed">通过</option></select></label>
        <label v-if="assessment.outcome === 'passed' && entry.runId" class="lw-label">已接受的运行证据<select v-model="assessment.evidenceId" class="lw-field" required><option value="">请选择</option><option v-for="evidence in acceptedEvidence" :key="evidence.id" :value="evidence.id">{{ evidence.summary || evidence.id }}</option></select></label>
        <p v-if="assessment.outcome === 'passed' && entry.runId && !acceptedEvidence.length" class="lw-small lw-sub">此运行还没有已接受证据。先到事项中审阅，再刷新评测列表。</p>
        <label class="lw-label">对照标准的理由<textarea v-model="assessment.body" class="lw-field" rows="3" required /></label>
        <button class="lw-btn primary" type="submit" :disabled="busy || !assessment.body.trim() || (assessment.outcome === 'passed' && !!entry.runId && !assessment.evidenceId)">保存判断</button>
      </form>
    </div>
    <div v-else><p class="evaluation-copy"><strong>{{ entry.outcome === 'passed' ? '通过' : entry.outcome === 'failed' ? '未通过' : '无法判断' }}：</strong>{{ entry.assessment }}</p>
      <div class="evaluation-links"><button class="lw-btn sm" type="button" @click="emit('reuse', entry)">沿同一标准再评</button><button v-if="!entry.improvementId" class="lw-btn sm" type="button" @click="beginImprovement">形成改进建议</button></div>
      <p v-if="entry.improvementId" class="lw-small lw-sub">已关联改进建议 {{ entry.improvementId }}；可在“能力与成长”查看并决定是否形成候选。</p>
      <form v-if="showingImprovement && !entry.improvementId" class="evaluation-action" @submit.prevent="submitImprovement">
        <p class="lw-small lw-sub">这只是带评测来源的建议；不会自动创建或发布 Agent。</p>
        <label class="lw-label">改进哪一层<select v-model="improvement.targetKind" class="lw-field"><option value="knowledge">知识</option><option value="skill">Skill</option><option value="agent">Agent 配置</option><option value="harness">Harness / 流程</option></select></label>
        <label class="lw-label">发现的问题<textarea v-model="improvement.problem" class="lw-field" rows="3" required /></label>
        <label class="lw-label">希望改善的行为<textarea v-model="improvement.desiredBehavior" class="lw-field" rows="3" required /></label>
        <label class="lw-label">下次怎样验证<textarea v-model="improvement.validationPlan" class="lw-field" rows="3" required /></label>
        <button class="lw-btn primary" type="submit" :disabled="busy || !improvement.problem.trim() || !improvement.desiredBehavior.trim() || !improvement.validationPlan.trim()">保存改进建议</button>
      </form>
    </div>
  </article>
</template>

<style scoped>
.evaluation-entry { border: 1px solid #dfe5e9; border-radius: 8px; padding: 16px; display: grid; gap: 8px; }
.evaluation-heading { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
.evaluation-heading h3 { margin: 0; }
.evaluation-heading p { margin: 4px 0 0; }
.evaluation-label { font-size: 11px; font-weight: 700; color: var(--lw-muted); margin: 0; }
.evaluation-copy { white-space: pre-wrap; margin: 0; line-height: 1.6; overflow-wrap: anywhere; }
.evaluation-links { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; }
.evaluation-action { border-top: 1px solid #e7ebee; padding-top: 12px; margin-top: 6px; display: grid; gap: 10px; }
.evaluation-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
@media (max-width: 680px) { .evaluation-grid { grid-template-columns: 1fr; } }
</style>

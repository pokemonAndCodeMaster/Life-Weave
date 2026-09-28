<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiError } from '../../api/lifeweave'
import { getAgentChoices, dispatchAgent, type AgentChoices, type AgentDefinition, type ExecutionRef } from '../../api/agents'
import { developmentChoices, type DevelopmentChoices } from '../../api/development'
import { getRecommendations, type InputRecommendations } from '../../api/continuation'
import { listCapabilities } from '../../api/lifeweave'
import { getWorkView, type ItemWorkView } from '../../api/workView'
import type { WorkspaceKind } from '../../types'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string; initialInstruction?: string; initialAgentId?: string }>()
const emit = defineEmits<{ close: []; launched: [execution: ExecutionRef] }>()
const router = useRouter()
const choices = shallowRef<AgentChoices | null>(null)
const workView = shallowRef<ItemWorkView | null>(null)
const recommendations = shallowRef<InputRecommendations | null>(null)
const candidates = shallowRef<Array<{id:string;title:string;status:string}>>([])
const devChoices = shallowRef<DevelopmentChoices | null>(null)
const devError = shallowRef('')
const loading = shallowRef(false)
const busy = shallowRef(false)
const error = shallowRef('')
const form = reactive({ agentId: '', instruction: '', engine: '', model: '', repositoryPath: '', directory: '', runtime: 'native' as 'native'|'docker', permission: 'read-only' as 'read-only'|'workspace-write', image: '', branch: '', capabilityCandidateId: '', methodId: '', knowledgeRefs: [] as string[], excludeKnowledge:false, executionScope: 'plan_only', reviewMode: 'independent', stepId: '', acknowledgeExcludedChanges: false })
const selected = computed(() => choices.value?.items.find(agent => agent.id === form.agentId) ?? null)
const engine = computed(() => choices.value?.engines.find(entry => entry.id === form.engine))
const worker = computed(() => choices.value?.environment?.localWorker as {enabled?:boolean;running?:boolean} | undefined)
const development = computed(() => selected.value?.capability === 'development')
const declaredPlan = computed(() => workView.value?.plan.source === 'declared' ? workView.value.plan : null)
const targetSteps = computed(() => declaredPlan.value?.nodes.filter(node => node.state !== 'cancelled' && node.expectedOutputs?.some(output => output.kind === (form.executionScope === 'implement' ? 'code' : 'plan'))) ?? [])
const targetStep = computed(() => targetSteps.value.find(step => step.id === form.stepId) ?? (targetSteps.value.length === 1 ? targetSteps.value[0] : null))
const mode = computed(() => selected.value?.capability === 'development' ? 'managed_development' : selected.value?.capability === 'organization' ? 'organization' : 'managed_run')
function engineReady(id: string): boolean {
  if (development.value && devChoices.value && (id === 'codex' || id === 'opencode')) return devChoices.value.executors[id].available
  return !!choices.value?.engines.find(entry => entry.id === id)?.available
}
const engineReason = computed(() => development.value && devChoices.value && (form.engine === 'codex' || form.engine === 'opencode') ? devChoices.value.executors[form.engine].reason : engine.value?.reason)
const available = computed(() => !!selected.value?.enabled && (selected.value.available || (selected.value.engine !== form.engine && engineReady(form.engine))))
let generation = 0

watch(() => [props.workspace, props.itemId], async () => {
  const ticket = ++generation
  loading.value = true; error.value = ''; choices.value = null; workView.value = null; devChoices.value = null; devError.value = ''
  form.instruction = props.initialInstruction ?? ''
  try {
    const [catalog, view, suggested, candidateRows] = await Promise.all([
      getAgentChoices(props.workspace, props.itemId), getWorkView(props.workspace, props.itemId),
      getRecommendations(props.workspace, props.itemId).catch(() => null),
      listCapabilities(props.workspace).catch(() => ({items:[]})),
    ])
    if (ticket !== generation) return
    choices.value = catalog; workView.value = view; recommendations.value = suggested
    candidates.value = (candidateRows.items ?? []).filter((candidate: {status:string}) => ['candidate','verified'].includes(candidate.status))
    form.agentId = props.initialAgentId || catalog.recommendedAgentId || catalog.items.find(agent => agent.available)?.id || catalog.items[0]?.id || ''
    form.engine = catalog.items.find(agent => agent.id === form.agentId)?.engine || 'codex'
    form.methodId = ''
    form.knowledgeRefs = []; form.excludeKnowledge = false
    form.directory = ''; form.image = ''; form.branch = ''; form.capabilityCandidateId = ''
    try { const dev = await developmentChoices(props.workspace, props.itemId); if (ticket === generation) { devChoices.value = dev; form.repositoryPath = dev.recommendedRepositoryPath } }
    catch (caught) { if (ticket === generation) devError.value = apiError(caught).message }
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) loading.value = false }
}, { immediate: true })
watch(selected, (agent: AgentDefinition | null) => { if (agent) { form.engine = agent.engine; form.model = ''; form.runtime = agent.runtime ?? 'native'; form.permission = agent.permission ?? 'read-only'; form.stepId = ''; form.methodId = ''; form.knowledgeRefs = []; form.excludeKnowledge = false } })
watch(() => form.executionScope, () => { form.stepId = '' })

async function submit() {
  if (!selected.value || !available.value || busy.value) return
  if (development.value && !form.repositoryPath.trim()) { error.value = '开发委托需要选择项目 Git 目录。'; return }
  if (development.value && declaredPlan.value && !targetStep.value) { error.value = '请选择与本次交付相符的工作步骤。'; return }
  busy.value = true; error.value = ''
  try {
    const execution = await dispatchAgent(props.workspace, props.itemId, {
      requestId: crypto.randomUUID(), agentId: selected.value.id, mode: mode.value,
      engine: form.engine, ...(form.model.trim() ? {model:form.model.trim()} : {}),
      instruction: form.instruction.trim() || undefined,
      ...(form.methodId ? {methodId:form.methodId} : {}),
      ...(form.excludeKnowledge ? {knowledgeRefs:[]} : form.knowledgeRefs.length ? {knowledgeRefs:form.knowledgeRefs} : {}),
      ...(development.value ? {
        repositoryPath: form.repositoryPath.trim(), executionScope: form.executionScope, reviewMode: form.reviewMode,
        acknowledgeExcludedChanges: form.acknowledgeExcludedChanges,
        ...(declaredPlan.value ? { stepId: targetStep.value!.id, planVersion: declaredPlan.value.version } : {}),
      } : {}),
      ...(mode.value === 'managed_run' ? { directory:form.directory.trim() || undefined, runtime:form.runtime, permission:form.permission, image:form.runtime === 'docker' ? form.image.trim() || undefined : undefined, branch:form.branch.trim() || undefined, capabilityCandidateId:form.capabilityCandidateId || undefined } : {}),
      ...(mode.value === 'organization' ? { organization: { action: 'propose' as const, itemIds: [props.itemId] } } : {}),
    })
    emit('launched', execution)
    await router.push(`/lifeweave/${props.workspace}/agent-executions/${execution.kind}/${encodeURIComponent(execution.id)}`)
  } catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="lw-panel pad agent-launch" aria-label="委托 Agent">
    <div class="lw-between"><div><h2>委托 Agent</h2><p class="lw-small lw-sub">选择已注册的能力，并固定这一次使用的执行环境。</p></div><button type="button" class="lw-btn ghost sm" @click="emit('close')">收起</button></div>
    <p v-if="loading" role="status">正在读取可用 Agent…</p>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <form v-if="choices" class="launch-form" @submit.prevent="submit">
      <label class="lw-label">Agent<select v-model="form.agentId" class="lw-field"><option v-for="agent in choices.items" :key="agent.id" :value="agent.id">{{ agent.name }}{{ agent.available ? '' : '（不可用）' }}</option></select></label>
      <p v-if="selected" class="lw-small lw-sub">{{ selected.description }}<span v-if="!available" class="unavailable"> · {{ selected.reason || '当前不可用' }}</span></p>
      <p v-if="mode !== 'organization' && worker && !worker.running" class="lw-small lw-sub">{{ worker.enabled ? '本机执行已启用，当前执行进程未运行；提交后可能等待执行节点。' : '本机执行尚未启用；请在设置与连接中检查运行环境。' }}</p>
      <label class="lw-label">本次任务<textarea v-model="form.instruction" class="lw-field" rows="3" :required="mode !== 'organization'" placeholder="写明本次要完成什么，以及怎样判断完成" /></label>
      <div v-if="mode !== 'organization'" class="launch-grid">
        <label class="lw-label">执行器<select v-model="form.engine" class="lw-field"><option v-for="entry in choices.engines.filter(entry => entry.id !== 'builtin')" :key="entry.id" :value="entry.id" :disabled="!engineReady(entry.id)">{{ entry.label }}{{ engineReady(entry.id) ? '' : '（不可用）' }}</option></select></label>
        <label class="lw-label">模型（可选）<input v-model="form.model" class="lw-field" :placeholder="selected?.model ? `默认 ${selected.model}；留空则继承` : '留空使用 Agent 默认模型'" /></label>
      </div>
      <p v-if="engine && !engineReady(form.engine)" class="lw-notice warning">{{ engineReason || '执行器当前不可用。' }}</p>
      <template v-if="development">
        <p v-if="devError" class="lw-notice warning">开发环境读取失败：{{ devError }}</p>
        <label class="lw-label">项目 Git 目录<input v-model="form.repositoryPath" class="lw-field" required autocomplete="off" /></label>
        <div class="launch-grid"><label class="lw-label">执行范围<select v-model="form.executionScope" class="lw-field"><option value="plan_only">仅形成并审阅方案</option><option value="implement">审阅通过后实施</option></select></label><label class="lw-label">方案检查<select v-model="form.reviewMode" class="lw-field"><option value="independent">独立审阅</option><option value="self">自检</option></select></label></div>
        <label v-if="declaredPlan && targetSteps.length > 1" class="lw-label">目标步骤<select v-model="form.stepId" class="lw-field" required><option value="">请选择</option><option v-for="step in targetSteps" :key="step.id" :value="step.id">{{ step.title }}</option></select></label>
        <p v-else-if="declaredPlan && !targetStep" class="lw-notice warning">当前计划没有对应的可用开发步骤，请先调整步骤计划。</p>
        <p v-else-if="targetStep" class="lw-small lw-sub">关联步骤：{{ targetStep.title }} · 计划 v{{ declaredPlan?.version }}</p>
        <label class="lw-small"><input v-model="form.acknowledgeExcludedChanges" type="checkbox" /> 我知道未提交的代码改动不会进入受管运行。</label>
      </template>
      <p v-if="mode === 'organization'" class="lw-small lw-sub">整理建议依据父项继承和已维护的明确规则生成；不确定的归属需要进一步判断，任务描述本身不会被当成已确认的分类。</p>
      <details v-if="mode !== 'organization'" class="advanced"><summary>方法、知识与运行设置</summary><p v-if="recommendations" class="lw-small lw-sub">当前建议：{{ recommendations.suggested.methodId || '无方法' }}、{{ recommendations.suggested.knowledgeRefs.length }} 篇知识。{{ recommendations.boundary }}</p><button v-if="recommendations" type="button" class="lw-btn sm" @click="form.methodId = recommendations.suggested.methodId ?? ''; form.knowledgeRefs = [...recommendations.suggested.knowledgeRefs]; form.excludeKnowledge = false">采用建议的输入</button><label class="lw-label">本次方法<select v-model="form.methodId" class="lw-field"><option value="">继承 Agent 默认方法</option><option v-for="method in recommendations?.methods ?? []" :key="method.id" :value="method.id">{{ method.title }}</option></select></label><label class="lw-label">附带知识（多选）<select v-model="form.knowledgeRefs" class="lw-field" multiple size="5" :disabled="form.excludeKnowledge"><option v-for="document in recommendations?.documents ?? []" :key="document.ref" :value="document.ref">{{ document.sourceTitle }} / {{ document.title }}</option></select></label><label class="lw-small"><input v-model="form.excludeKnowledge" type="checkbox" /> 本次明确不带知识</label><p v-if="recommendations?.unavailable.length" class="lw-notice warning">部分推荐材料不可读取，请先核对来源。</p><template v-if="mode === 'managed_run'"><label class="lw-label">目标工作目录<input v-model="form.directory" class="lw-field" autocomplete="off" placeholder="留空使用事项默认目录" /></label><div class="launch-grid"><label class="lw-label">运行方式<select v-model="form.runtime" class="lw-field"><option value="native">本机</option><option value="docker">容器</option></select></label><label class="lw-label">目录权限<select v-model="form.permission" class="lw-field"><option value="read-only">只读分析</option><option value="workspace-write">允许修改工作目录</option></select></label></div><label v-if="form.runtime === 'docker'" class="lw-label">容器镜像<input v-model="form.image" class="lw-field" /></label><label class="lw-label">分支<input v-model="form.branch" class="lw-field" /></label><label class="lw-label">试验能力候选<select v-model="form.capabilityCandidateId" class="lw-field"><option value="">不附加候选</option><option v-for="candidate in candidates" :key="candidate.id" :value="candidate.id">{{ candidate.title }} · {{ candidate.status }}</option></select></label></template></details>
      <button type="submit" class="lw-btn primary" :disabled="busy || !available || (mode !== 'organization' && !engineReady(form.engine)) || (development && (!!devError || (!!declaredPlan && !targetStep)))">{{ busy ? '正在触发…' : '开始委托' }}</button>
    </form>
  </section>
</template>

<style scoped>
.agent-launch{display:grid;gap:12px}.agent-launch h2{margin:0 0 5px}.launch-form{display:grid;gap:13px}.launch-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.unavailable{color:#a04535}@media(max-width:700px){.launch-grid{grid-template-columns:1fr}}
.advanced{border-top:1px solid #e2e9f0;padding-top:12px;display:grid;gap:10px}.advanced summary{cursor:pointer;font-size:12px;color:#426b93;margin-bottom:10px}.advanced .lw-label{margin:10px 0}
</style>

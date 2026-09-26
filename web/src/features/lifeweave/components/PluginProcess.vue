<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { listDevelopment } from '../api/development'
import { getRun, getRunEventsPage } from '../api/lifeweave'
import type { PluginCall, PluginPlan, PluginProcess as Process, PluginStep } from '../api/plugins'
import type { LifeWeaveRun, RunEvent, WorkspaceKind } from '../types'

const props = defineProps<{ process: Process | null; assignmentId: string; error?: string }>()
const route = useRoute()
const scope = computed(() => {
  const { workspace, itemId } = route.params
  return (workspace === 'personal' || workspace === 'team') && typeof itemId === 'string' && itemId === props.process?.itemId
    ? { workspace: workspace as WorkspaceKind, itemId } : null
})
const plans = computed(() => props.process?.plans.filter(plan => plan.item_id === props.process?.itemId && plan.assignment_id === props.assignmentId) ?? [])
const calls = computed(() => props.process?.calls.filter(call => call.item_id === props.process?.itemId && call.assignment_id === props.assignmentId) ?? [])
function matches(plan: PluginPlan, step: PluginStep) {
  return calls.value.filter(call => call.plan_id === plan.id && call.step_id === step.id)
}
const groups = computed(() => [
  ...plans.value.flatMap(plan => plan.steps.map(step => ({ key: `${plan.id}/${step.id}`, plan, step, calls: matches(plan, step) }))),
  { key: 'unmatched', plan: null, step: null, calls: calls.value.filter(call => !plans.value.some(plan => plan.id === call.plan_id && plan.steps.some(step => step.id === call.step_id))) },
].filter(group => group.step || group.calls.length))
function binding(call: PluginCall) { return plans.value.find(plan => plan.id === call.plan_id)?.bindings[call.plugin_id] }
function comparison(call: PluginCall) {
  const fixed = binding(call)
  if (!fixed) return '缺少固定绑定，无法比较'
  const differences = []
  if (fixed.version !== call.plugin_version) differences.push('插件版本不同')
  if (fixed.implementationDigest !== call.implementation_digest) differences.push('实现摘要不同')
  return differences.length ? `已返回调用与固定计划不一致：${differences.join('、')}` : '调用版本与固定计划一致'
}
const stages: Record<string, string> = { planning: '方案', reviewing: '独立审阅', implementing: '实施', plan: '方案', review: '审阅', implementation: '实施' }
const states: Record<string, string> = { started: '已记录开始', accepted: '已受理', succeeded: '成功', failed: '失败', interrupted: '中断', queued: '排队', claimed: '已领取', running: '运行中', pause_requested: '请求暂停', paused: '暂停', cancelling: '取消中', cancelled: '已取消', unavailable: '不可用' }
const observations: Record<string, string> = { platform: '服务端调用边界', 'server-boundary': '服务端调用边界', 'worker-report': '执行节点报告' }
const failures: Record<string, string> = { authentication_failed: '认证失败', insufficient_balance: '余额不足', model_unavailable: '模型不可用', rate_limited: '请求限流', timeout: '超时', executor_error: '执行器错误' }
function known(value: unknown, labels: Record<string, string>, fallback = '未知（内容已隐藏）') {
  return typeof value === 'string' && Object.hasOwn(labels, value) ? labels[value]! : fallback
}
// Only structural identifiers, hashes and finite enums cross this view boundary.
// In particular, summary/error/payload/sourcePath are never rendered verbatim.
function checked(value: unknown, pattern: RegExp): string | null {
  return typeof value === 'string' && pattern.test(value) ? value : null
}
const runId = (value: unknown) => checked(value, /^gzrun-\d{8}-\d{6}-[a-f0-9]{8}$/)
const identity = (value: unknown) => checked(value, /^(?:item|ctxv|method|document|pcall|pplan|dev|cap)-[a-f0-9]{8,64}$/)
const hash = (value: unknown) => checked(value, /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/)
const version = (value: unknown) => hash(value) || checked(value, /^\d{1,6}(?:\.\d{1,6}){0,3}$/)
const plugin = (value: unknown) => checked(value, /^lifeweave\.(?:development|context|knowledge|checks\.repository|execution\.(?:codex|opencode)|method\.method-[a-f0-9]{8,64})$/)
const operation = (value: unknown) => known(value, Object.fromEntries(['plan', 'review', 'implement', 'compile', 'recommend', 'read', 'bind', 'run', 'verify_readonly', 'verify_inputs'].map(key => [key, key])))
function time(value: unknown) {
  return checked(value, /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/) || '未记录或格式不可安全展示'
}
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
function references(value: Record<string, unknown>) {
  const rows: Array<{ label: string; value: string }> = []
  const add = (label: string, safe: string | null) => { if (safe) rows.push({ label, value: safe }) }
  add('Run ID', runId(value.runId))
  add('事项', identity(value.itemId)); add('上下文版本', identity(value.contextVersionId))
  add('源码提交', hash(value.repositoryRevision)); add('方法', identity(value.methodId))
  add('来源版本', version(value.version))
  for (const key of ['stage', 'phase']) add('阶段', known(value[key], stages, '') || null)
  for (const key of ['state', 'outcome']) add('状态', known(value[key], states, '') || null)
  add('检查结果', known(value.result, { clean: '只读检查通过', unchanged: '输入未变化' }, '') || null)
  if (typeof value.exitCode === 'number' && Number.isSafeInteger(value.exitCode)) add('退出码', String(value.exitCode))
  if (Array.isArray(value.methodIds)) value.methodIds.forEach(id => add('方法', identity(id)))
  if (Array.isArray(value.sources)) value.sources.forEach(source => {
    const entry = record(source)
    const id = identity(entry.id), revision = version(entry.version)
    if (revision) add(id ? '来源 / 版本' : '来源版本', id ? `${id} / ${revision}` : revision)
  })
  for (const key of ['knowledgeRefs', 'documentRefs']) {
    if (Array.isArray(value[key])) add('知识引用', `${value[key].length} 条（路径已隐藏）`)
    else if (typeof value[key + 'Count'] === 'number' && Number.isSafeInteger(value[key + 'Count']))
      add('知识引用', `${value[key + 'Count']} 条（路径已隐藏）`)
  }
  return rows
}
function linkedRuns(call: PluginCall) {
  return [...new Set([call.run_id, call.input_ref.runId, call.output_ref.runId].map(runId).filter((id): id is string => !!id))]
}
const openCalls = ref<string[]>([])
function toggleCall(id: string, event: Event) {
  if ((event.target as HTMLDetailsElement).open) { if (!openCalls.value.includes(id)) openCalls.value.push(id) }
  else openCalls.value = openCalls.value.filter(value => value !== id)
}
const runReader = ref<HTMLElement | null>(null)
const selectedRun = ref('')
const run = ref<LifeWeaveRun | null>(null)
const stageLabels = ref<string[]>([])
const events = ref<RunEvent[]>([])
const loading = ref(false), loadingEvents = ref(false), more = ref(false)
const runError = ref(''), eventError = ref(''), pageNotice = ref('')
let generation = 0, cursor = 0
function resetRun() {
  generation++; selectedRun.value = ''; run.value = null; stageLabels.value = []; events.value = []
  loading.value = false; loadingEvents.value = false; more.value = false; cursor = 0
  runError.value = ''; eventError.value = ''; pageNotice.value = ''
}
watch([() => route.params.workspace, () => route.params.itemId, () => props.process?.itemId, () => props.assignmentId], () => {
  resetRun(); openCalls.value = []
}, { flush: 'sync' })
watch(calls, current => {
  openCalls.value = openCalls.value.filter(id => current.some(call => call.id === id))
  if (selectedRun.value && !current.some(call => linkedRuns(call).includes(selectedRun.value))) resetRun()
})
onBeforeUnmount(resetRun)
async function selectRun(id: string) {
  resetRun()
  selectedRun.value = id
  const current = scope.value
  if (!current) { runError.value = '当前路由与事项不一致，未读取运行。'; return }
  const ticket = generation
  void nextTick(() => {
    if (ticket !== generation) return
    runReader.value?.scrollIntoView?.({ block: 'start' })
    runReader.value?.focus({ preventScroll: true })
  })
  loading.value = true
  try {
    const [assignments, snapshot] = await Promise.all([listDevelopment(current.workspace, current.itemId), getRun(current.workspace, id)])
    if (ticket !== generation) return
    if (snapshot.id !== id || snapshot.itemId !== current.itemId) {
      runError.value = '运行归属不符，已隐藏详情且未读取事件。'; return
    }
    const assignment = assignments.find(row => row.id === props.assignmentId && row.itemId === current.itemId)
    stageLabels.value = assignment ? ([['planRunId', '方案'], ['reviewRunId', '独立审阅'], ['implementationRunId', '实施与验证']] as const)
      .filter(([key]) => assignment[key] === id).map(([, label]) => label) : []
    run.value = snapshot
    await loadEvents(ticket)
  } catch { if (ticket === generation) runError.value = '运行暂不可读取（可能不存在或连接失败）；错误原文已隐藏。' }
  finally { if (ticket === generation) loading.value = false }
}
async function loadEvents(ticket = generation) {
  const current = scope.value
  if (!current || !run.value || loadingEvents.value) return
  loadingEvents.value = true; eventError.value = ''
  const after = cursor
  try {
    const page = await getRunEventsPage(current.workspace, selectedRun.value, after)
    if (ticket !== generation) return
    const valid = page.items.filter(event => Number.isSafeInteger(event.sequence) && event.sequence! > 0)
    const bySequence = new Map(events.value.map(event => [event.sequence!, event]))
    for (const event of valid) if (!bySequence.has(event.sequence!)) bySequence.set(event.sequence!, event)
    events.value = [...bySequence.values()].sort((a, b) => a.sequence! - b.sequence!)
    const last = Math.max(after, ...valid.map(event => event.sequence!))
    const advances = Number.isSafeInteger(page.nextSequence) && page.nextSequence > after && page.nextSequence === last
    more.value = page.items.length >= 200 && advances
    if (page.items.length && !advances) pageNotice.value = '事件游标未推进或不一致，已停止继续加载。'
    else if (valid.length !== page.items.length) { more.value = false; pageNotice.value = '部分事件缺少有效序号，已停止继续加载。' }
    else pageNotice.value = more.value ? '已返回满页事件，可能还有记录。' : ''
    if (advances) cursor = page.nextSequence
  } catch { if (ticket === generation) eventError.value = '事件暂不可读取；错误原文已隐藏，可重试读取。' }
  finally { if (ticket === generation) loadingEvents.value = false }
}
const eventTypes = Object.fromEntries(['thread.started', 'turn.started', 'turn.completed', 'turn.failed', 'item.started', 'item.updated', 'item.completed', 'error', 'executor.diagnostic', 'plugin.execution.started', 'plugin.execution.finished', 'run.started', 'run.finished', 'run.queued', 'run.claimed', 'run.running', 'run.succeeded', 'run.failed', 'run.unavailable', 'run.cancel_requested', 'run.cancelled', 'run.pause_requested', 'run.paused'].map(key => [key, key]))
function eventFacts(event: RunEvent) {
  const payload = record(event.payload), item = record(payload.item)
  const facts = references({ exitCode: payload.exitCode, outcome: payload.outcome })
  const kind = known(item.type, { command_execution: '命令执行', agent_message: 'Agent 消息', file_change: '文件变更', mcp_tool_call: 'MCP 调用', reasoning: '推理' }, '')
  if (kind) facts.push({ label: '事件内容类型', value: kind })
  const state = known(item.status, { in_progress: '进行中', completed: '已结束', failed: '失败' }, '')
  if (state) facts.push({ label: '事件内容状态', value: state })
  return facts
}
</script>

<template>
  <details class="plugin-process"><summary>插件计划与实际调用 · 本次已返回 {{ calls.length }} 次</summary>
    <p v-if="error" class="lw-notice warning" role="status">插件过程暂不可读取；错误原文已隐藏。开发阶段、Run 和原生事件仍以各自记录为准。</p>
    <p v-else-if="!process" role="status">正在读取插件过程…</p>
    <template v-if="process">
      <p class="lw-tiny lw-muted">只显示受管插件边界的调用；未观测不等于没有发生。仅展示安全结构化字段，原始摘要、提示词、命令、路径及未知内容已隐藏。</p>
      <p v-if="!error && !plans.length" class="lw-small lw-muted">未找到此委托的固定插件计划，无法仅据此判断创建年代。</p>
      <p v-if="process.truncated" class="lw-tiny lw-muted">已达到返回上限，记录可能不完整；数量仅为本次已返回调用。</p>
      <section v-for="group in groups" :key="group.key" class="plugin-step">
        <template v-if="group.plan && group.step">
          <p class="lw-tiny">固定计划 {{ identity(group.plan.id) || '身份已隐藏' }} · v{{ version(String(group.plan.version)) || '版本已隐藏' }}</p>
          <strong>{{ known(group.step.stage, stages) }} · {{ plugin(group.step.pluginId) || '插件身份已隐藏' }} / {{ operation(group.step.operation) }}</strong>
          <p v-if="!group.calls.length">尚无实际调用记录{{ !group.step.required ? '（条件步骤）' : '' }}{{ process.truncated ? '；记录可能不完整，无法判定' : '' }}</p>
        </template>
        <strong v-else>未匹配固定步骤的调用</strong>
        <details v-for="call in group.calls" :key="call.id" class="plugin-call" :open="openCalls.includes(call.id)" @toggle="toggleCall(call.id, $event)">
          <summary>{{ known(call.state, states) }} · {{ plugin(call.plugin_id) || '插件身份已隐藏' }} / {{ operation(call.operation) }} · {{ identity(call.id) || '调用身份已隐藏' }}</summary>
          <dl>
            <dt>观测来源</dt><dd>{{ known(call.observed_by, observations) }}</dd>
            <dt>调用固定插件版本</dt><dd>{{ version(call.plugin_version) || '版本格式已隐藏' }}</dd>
            <dt>调用实现摘要</dt><dd>{{ hash(call.implementation_digest) || '摘要格式已隐藏' }}</dd>
            <template v-if="binding(call)">
              <dt>计划固定插件版本</dt><dd>{{ version(binding(call)!.version) || '版本格式已隐藏' }}</dd>
              <dt>计划实现摘要</dt><dd>{{ hash(binding(call)!.implementationDigest) || '摘要格式已隐藏' }}</dd>
            </template>
            <dt>绑定核对</dt><dd>{{ comparison(call) }}。仅比较此调用与计划，未检查当前安装版本。</dd>
            <dt>开始时间</dt><dd>{{ time(call.started_at) }}</dd>
            <dt>结束时间</dt><dd>{{ call.finished_at ? time(call.finished_at) : '尚未记录结束；不据此推断仍在运行' }}</dd>
          </dl>
          <div v-for="(reference, index) in [call.input_ref, call.output_ref]" :key="index">
            <strong>{{ index === 0 ? '输入引用' : '输出引用' }}</strong>
            <ul v-if="references(reference).length"><li v-for="(entry, row) in references(reference)" :key="row">{{ entry.label }}：{{ entry.value }}</li></ul>
            <p v-else>{{ Object.keys(reference).length ? '引用中没有可安全展示的字段，内容已隐藏。' : '未记录' }}</p>
          </div>
          <p>错误：{{ call.has_error ? known(call.error_code, failures, '已记录错误；自由文本原文已隐藏。') : '未记录' }}</p>
          <RouterLink v-if="scope && identity(call.id) && ['succeeded', 'failed', 'interrupted'].includes(call.state)" class="lw-text-btn" :to="{ path: `/lifeweave/${scope.workspace}/maintenance`, query: { tab: 'evaluations', itemId: scope.itemId, pluginCallId: call.id } }">评价这次调用</RouterLink>
          <div class="run-links" v-if="linkedRuns(call).length"><button v-for="id in linkedRuns(call)" :key="id" type="button" class="lw-btn ghost sm" :aria-expanded="selectedRun === id" @click="selectRun(id)">查看 Run {{ id }}</button></div>
          <p v-else>未记录可安全读取的 Run 引用。</p>
        </details>
      </section>
    </template>
    <section v-if="selectedRun" ref="runReader" class="run-reader" tabindex="-1" aria-label="只读运行记录" aria-live="polite">
      <div class="run-heading"><strong>Run {{ selectedRun }}</strong><button class="lw-btn ghost sm" type="button" @click="resetRun">收起运行记录</button></div>
      <p v-if="loading" role="status">正在读取运行…</p>
      <p v-if="runError" role="status">{{ runError }}</p>
      <template v-if="run">
        <p>开发阶段：{{ stageLabels.join('、') || '本委托没有记录此 Run 的阶段关联' }} · 状态：{{ known(run.state, states) }}</p>
        <p>原生会话 ID：{{ checked(run.session, /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/) || (run.session ? '格式不可安全展示，已隐藏' : '未记录') }}</p>
        <p class="lw-tiny lw-muted">原生事件仅展示序号、时间、来源、类型及安全结构化信息；摘要与原始内容已隐藏。</p>
        <ol class="event-list"><li v-for="event in events" :key="event.sequence">
          <p>#{{ event.sequence }} · {{ time(event.occurredAt) }} · {{ known(event.source, { platform: '工作台', codex: 'Codex', opencode: 'OpenCode', worker: '执行节点', runtime: '运行服务', api: 'API' }) }} · {{ known(event.eventType || event.type, eventTypes) }}</p>
          <p v-for="(entry, index) in eventFacts(event)" :key="index">{{ entry.label }}：{{ entry.value }}</p>
        </li></ol>
        <p v-if="!events.length && !loadingEvents && !eventError">尚无已返回的事件记录。</p>
        <p v-if="pageNotice" role="status">{{ pageNotice }}</p><p v-if="eventError" role="status">{{ eventError }}</p>
        <button v-if="more || eventError" class="lw-btn ghost sm" type="button" :disabled="loadingEvents" @click="loadEvents()">{{ loadingEvents ? '正在读取事件…' : eventError ? '重试读取事件' : '加载后续事件' }}</button>
      </template>
    </section>
  </details>
</template>

<style scoped>
.plugin-process { border-top: 1px solid var(--lw-line, #dededb); padding-top: 8px; min-width: 0; overflow-wrap: anywhere; }
.plugin-process summary { cursor: pointer; }
.plugin-step, .run-reader { border-top: 1px solid var(--lw-line, #dededb); padding: 10px 0; font-size: 12px; }
.plugin-call { margin-top: 8px; padding: 8px; border: 1px solid var(--lw-line, #dededb); border-radius: 6px; }
.plugin-process dl { display: grid; grid-template-columns: 140px minmax(0, 1fr); gap: 6px 12px; }
.plugin-process dd { margin: 0; }
.run-links, .run-heading { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.run-links button { white-space: normal; overflow-wrap: anywhere; max-width: 100%; }
.run-reader { scroll-margin-top: 80px; }
.event-list { max-height: 400px; overflow: auto; padding-left: 24px; }
.plugin-process summary:focus-visible, .plugin-process button:focus-visible { outline: 2px solid currentColor; outline-offset: 3px; }
@media (max-width: 620px) { .plugin-process dl { grid-template-columns: minmax(0, 1fr); } .plugin-process dt { font-weight: 600; } }
</style>

<script setup lang="ts">
import { onBeforeUnmount, reactive, shallowRef, watch } from 'vue'
import { apiError, getRun, getRunEvents } from '../api/lifeweave'
import { cancelDevelopment, createDevelopment, developmentChoices, getDevelopmentDiff, listDevelopment } from '../api/development'
import type { DevelopmentAssignment, DevelopmentChoices, DevelopmentDiff } from '../api/development'
import type { LifeWeaveRun, RunEvent, WorkspaceKind } from '../types'
import MarkdownBody from './MarkdownBody.vue'
import RunTrace from './RunTrace.vue'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string; initialInstruction?: string }>()
const choices = shallowRef<DevelopmentChoices | null>(null)
const assignments = shallowRef<DevelopmentAssignment[]>([])
const runs = shallowRef<Record<string, LifeWeaveRun>>({})
const events = shallowRef<Record<string, RunEvent[]>>({})
const diffs = shallowRef<Record<string, DevelopmentDiff>>({})
const error = shallowRef('')
const busy = shallowRef(false)
const requestId = shallowRef(crypto.randomUUID())
const form = reactive({ instruction: '', repositoryPath: '', model: '', reviewMode: 'independent' as 'independent' | 'self', acknowledgeExcludedChanges: false })
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
async function refresh(ticket = generation) {
  try {
    const rows = await listDevelopment(props.workspace, props.itemId)
    if (ticket !== generation) return
    assignments.value = rows
    const runIds = rows.flatMap(row => [row.planRunId, row.reviewRunId, row.implementationRunId]).filter((id): id is string => !!id)
    const snapshots = await Promise.all(runIds.map(async id => ({ id, run: await getRun(props.workspace, id), trace: await getRunEvents(props.workspace, id) })))
    if (ticket !== generation) return
    runs.value = Object.fromEntries(snapshots.map(row => [row.id, row.run]))
    events.value = Object.fromEntries(snapshots.map(row => [row.id, row.trace]))
    error.value = ''
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) timer = setTimeout(() => void refresh(ticket), 4000) }
}
watch(() => [props.workspace, props.itemId], async () => {
  const ticket = ++generation
  clearTimeout(timer); assignments.value = []; runs.value = {}; events.value = {}; diffs.value = {}; choices.value = null; error.value = ''
  form.instruction = props.initialInstruction || ''; form.repositoryPath = ''
  try {
    const value = await developmentChoices(props.workspace, props.itemId)
    if (ticket !== generation) return
    choices.value = value; form.repositoryPath = value.recommendedRepositoryPath
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  if (ticket === generation) void refresh(ticket)
}, { immediate: true })
onBeforeUnmount(() => { generation++; clearTimeout(timer) })
async function submit() {
  if (busy.value || !form.instruction.trim()) return
  busy.value = true; error.value = ''
  try {
    await createDevelopment(props.workspace, {
      requestId: requestId.value, itemId: props.itemId, instruction: form.instruction.trim(),
      repositoryPath: form.repositoryPath.trim(), agentId: 'development', engine: 'codex', model: form.model.trim() || null,
      methodId: choices.value?.methodId, knowledgeRefs: choices.value?.knowledgeRefs,
      reviewMode: form.reviewMode, acknowledgeExcludedChanges: form.acknowledgeExcludedChanges,
    })
    requestId.value = crypto.randomUUID(); form.instruction = ''; clearTimeout(timer); await refresh()
  } catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
async function cancel(id: string) {
  busy.value = true
  try { await cancelDevelopment(props.workspace, id); clearTimeout(timer); await refresh() }
  catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
async function showDiff(id: string) {
  try { diffs.value = { ...diffs.value, [id]: await getDevelopmentDiff(props.workspace, id) } }
  catch (caught) { error.value = apiError(caught).message }
}
const stages: Array<{ key: 'planRunId' | 'reviewRunId' | 'implementationRunId'; title: string }> = [
  { key: 'planRunId', title: '方案' }, { key: 'reviewRunId', title: '独立审阅' }, { key: 'implementationRunId', title: '实施与验证' },
]
</script>

<template>
  <section class="lw-panel pad development-panel" aria-label="开发 Agent">
    <div class="lw-between"><div><h2>开发 Agent</h2><p class="lw-small lw-sub">同一事项记录固定背景、方案、审阅、实施和实际验证。推荐使用 Codex；当前阶段只执行已验证的 Codex 链路。</p></div><button class="lw-btn ghost sm" type="button" @click="refresh()">刷新</button></div>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <form class="lw-stack" @submit.prevent="submit">
      <label class="lw-label">这次要交付什么<textarea v-model="form.instruction" class="lw-field" rows="4" required maxlength="100000" placeholder="描述具体用户结果、限制和验收方式"></textarea></label>
      <label class="lw-label">项目 Git 目录<input v-model="form.repositoryPath" class="lw-field" required autocomplete="off" /></label>
      <div class="lw-form-grid">
        <label class="lw-label">Agent / 执行器<input class="lw-field" value="开发 Agent · Codex" readonly /></label>
        <label class="lw-label">Codex 模型（可选）<input v-model="form.model" class="lw-field" maxlength="256" autocomplete="off" placeholder="留空使用本机 Codex 默认模型" /></label>
        <label class="lw-label">方案检查<select v-model="form.reviewMode" class="lw-field"><option value="independent">独立审阅（复杂改动）</option><option value="self">方案自检（小改动）</option></select></label>
      </div>
      <label class="lw-small"><input v-model="form.acknowledgeExcludedChanges" type="checkbox" /> 我知道仓库未提交改动不会进入受管运行；运行从上方目录的当前提交创建隔离工作树。</label>
      <p class="lw-tiny lw-muted">固定方法：{{ choices?.methodId || '加载中' }} · 默认项目知识 {{ choices?.knowledgeRefs.length || 0 }} 篇。执行结果留在隔离工作树，需核对后合入项目。</p>
      <button class="lw-btn primary" type="submit" :disabled="busy || !choices?.agents.find(agent => agent.id === 'development')?.available">{{ busy ? '正在登记…' : '开始开发委托' }}</button>
    </form>
    <div v-if="assignments.length" class="development-history">
      <h3>本事项的开发委托</h3>
      <article v-for="assignment in assignments" :key="assignment.id" class="lw-note-card">
        <div class="lw-between"><strong>{{ assignment.instruction }}</strong><span class="lw-small">{{ assignment.status }}</span></div>
        <p class="lw-tiny lw-muted">{{ assignment.agentId }} {{ assignment.agentVersion.slice(0, 12) }} · {{ assignment.engine }}{{ assignment.model ? ` / ${assignment.model}` : ' / 默认模型' }} · Git {{ assignment.repositoryRevision.slice(0, 12) }} · 上下文 {{ assignment.contextVersionId }} · {{ assignment.reviewMode === 'self' ? '自检' : '独立审阅' }}</p>
        <p v-if="assignment.workingTreeExcluded" class="lw-small">开始时仓库存在未提交改动，本轮输入不包含它们。</p>
        <p v-if="assignment.error" class="lw-notice warning">{{ assignment.error }}</p>
        <button v-if="['planning','reviewing','implementing'].includes(assignment.status)" class="lw-btn ghost sm" type="button" :disabled="busy" @click="cancel(assignment.id)">停止委托</button>
        <p v-if="assignment.status === 'awaiting_acceptance'" class="lw-small">实施运行已结束。请打开结果和运行事件核对改动、测试及隔离工作树，再决定怎样合入。</p>
        <div v-if="assignment.implementationRunId"><button class="lw-btn ghost sm" type="button" @click="showDiff(assignment.id)">查看实际 Git 差异</button><details v-if="diffs[assignment.id]" open><summary>实际改动 {{ diffs[assignment.id]!.fileCount }} 个文件{{ diffs[assignment.id]!.truncated ? ' · 页面已截断' : '' }}</summary><p class="lw-tiny lw-muted">基于提交 {{ diffs[assignment.id]!.baseRevision.slice(0, 12) }}。执行输入文件已从差异中排除；此差异尚未合入原仓。</p><pre class="development-diff">{{ diffs[assignment.id]!.patch || '没有代码差异' }}</pre></details></div>
        <details v-if="assignment.inputVersions.length"><summary>固定输入与版本</summary><ul><li v-for="entry in assignment.inputVersions" :key="entry.id">{{ entry.id }} · {{ entry.version.slice(0, 12) }} · {{ entry.sourcePath }}</li></ul></details>
        <details v-for="stage in stages" :key="stage.key" :open="stage.key === 'implementationRunId' && assignment.status === 'awaiting_acceptance'">
          <summary>{{ stage.title }} · {{ assignment[stage.key] ? (runs[assignment[stage.key]!]?.state || '读取中') : '尚未开始' }}</summary>
          <template v-if="assignment[stage.key]"><p class="lw-tiny lw-mono">Run {{ assignment[stage.key] }} · {{ runs[assignment[stage.key]!]?.directory || '等待执行机' }}</p><p v-if="runs[assignment[stage.key]!]?.environmentSnapshot" class="lw-tiny lw-muted">实际模型：{{ runs[assignment[stage.key]!]!.environmentSnapshot?.effectiveModel || '执行器未报告' }} · 来源：{{ runs[assignment[stage.key]!]!.environmentSnapshot?.modelSource || '未知' }} · 凭据：{{ runs[assignment[stage.key]!]!.environmentSnapshot?.credentialSource || '未报告' }}</p>
            <MarkdownBody v-if="runs[assignment[stage.key]!]?.result" :content="runs[assignment[stage.key]!]!.result!" />
            <p v-if="runs[assignment[stage.key]!]?.error" class="lw-notice warning">{{ runs[assignment[stage.key]!]!.error }}</p>
            <RunTrace :events="events[assignment[stage.key]!] || []" />
          </template>
        </details>
      </article>
    </div>
    <p v-else class="lw-small lw-muted">此事项尚无开发委托。本机 Codex 直接工作时仍需关联此事项并主动上报阶段；平台不会假装捕获它的内部命令。</p>
  </section>
</template>

<style scoped>
.development-panel { display: grid; gap: 18px; }
.development-history { display: grid; gap: 12px; border-top: 1px solid var(--lw-line, #dededb); padding-top: 16px; }
.development-history article { display: grid; gap: 8px; overflow-wrap: anywhere; }
.development-history details { border-top: 1px solid var(--lw-line, #dededb); padding-top: 8px; }
.development-history summary { cursor: pointer; }
.development-history ul { padding-left: 18px; }
.development-diff { max-height: 560px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; background: #f5f7f5; padding: 12px; }
</style>

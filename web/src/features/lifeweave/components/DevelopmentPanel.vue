<script setup lang="ts">
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError, getRun, getRunEvents } from '../api/lifeweave'
import { cancelDevelopment, getDevelopmentDelivery, getDevelopmentDiff, listDevelopment } from '../api/development'
import type { DevelopmentAssignment, DevelopmentDelivery as DevelopmentDeliveryValue, DevelopmentDiff } from '../api/development'
import { pluginProcess } from '../api/plugins'
import type { PluginProcess as PluginProcessValue } from '../api/plugins'
import type { LifeWeaveRun, RunEvent, WorkspaceKind } from '../types'
import MarkdownBody from './MarkdownBody.vue'
import RunTrace from './RunTrace.vue'
import PluginProcess from './PluginProcess.vue'
import DevelopmentDelivery from './DevelopmentDelivery.vue'
import ExternalDevelopmentPanel from './ExternalDevelopmentPanel.vue'
import AgentLaunch from './agents/AgentLaunch.vue'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string; initialInstruction?: string }>()
const assignments = shallowRef<DevelopmentAssignment[]>([])
const runs = shallowRef<Record<string, LifeWeaveRun>>({})
const events = shallowRef<Record<string, RunEvent[]>>({})
const diffs = shallowRef<Record<string, DevelopmentDiff>>({})
const deliveries = shallowRef<Record<string, DevelopmentDeliveryValue>>({})
const process = shallowRef<PluginProcessValue | null>(null)
const processError = shallowRef('')
const error = shallowRef('')
const busy = shallowRef(false)
const launching = shallowRef(false)
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
async function refresh(ticket = generation) {
  try {
    const [rows, currentProcess] = await Promise.all([listDevelopment(props.workspace, props.itemId), pluginProcess(props.workspace, props.itemId).catch(() => null)])
    if (ticket !== generation) return
    assignments.value = rows
    process.value = currentProcess
    processError.value = currentProcess ? '' : '未能读取插件过程。'
    const deliveryRows = await Promise.all(rows.filter(row => ['awaiting_acceptance', 'accepted', 'rejected'].includes(row.status)).map(async row => {
      try { return { id: row.id, delivery: await getDevelopmentDelivery(props.workspace, row.id) } } catch { return null }
    }))
    if (ticket !== generation) return
    deliveries.value = Object.fromEntries(deliveryRows.filter((row): row is {id:string;delivery:DevelopmentDeliveryValue} => !!row).map(row => [row.id, row.delivery]))
    const runIds = rows.flatMap(row => [row.planRunId, row.reviewRunId, row.implementationRunId]).filter((id): id is string => !!id)
    const snapshots = await Promise.all(runIds.map(async id => ({ id, run: await getRun(props.workspace, id), trace: await getRunEvents(props.workspace, id) })))
    if (ticket !== generation) return
    runs.value = Object.fromEntries(snapshots.map(row => [row.id, row.run]))
    events.value = Object.fromEntries(snapshots.map(row => [row.id, row.trace]))
    error.value = ''
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation && assignments.value.some(row => ['planning','reviewing','implementing'].includes(row.status))) timer = setTimeout(() => void refresh(ticket), 4000) }
}
watch(() => [props.workspace, props.itemId], () => { generation++; clearTimeout(timer); assignments.value=[]; runs.value={}; events.value={}; deliveries.value={}; void refresh(generation) }, { immediate:true })
onBeforeUnmount(() => { generation++; clearTimeout(timer) })
async function cancel(id: string) { busy.value=true; try { await cancelDevelopment(props.workspace,id); await refresh() } catch (caught) { error.value=apiError(caught).message } finally { busy.value=false } }
async function showDiff(id: string) { try { diffs.value={...diffs.value,[id]:await getDevelopmentDiff(props.workspace,id)} } catch (caught) { error.value=apiError(caught).message } }
const stages: Array<{ key: 'planRunId' | 'reviewRunId' | 'implementationRunId'; title: string }> = [{key:'planRunId',title:'方案'},{key:'reviewRunId',title:'独立审阅'},{key:'implementationRunId',title:'实施与验证'}]
</script>
<template>
  <section class="lw-panel pad development-panel" aria-label="开发 Agent">
    <div class="lw-between"><div><h2>开发 Agent</h2><p class="lw-small lw-sub">这里保留本事项的开发历史与固定交付。新的委托使用共同的 Agent 配置。</p></div><button class="lw-btn ghost sm" type="button" @click="refresh()">刷新</button></div>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <button type="button" class="lw-btn primary" :aria-expanded="launching" @click="launching = !launching">{{ launching ? '收起委托' : '新建开发委托' }}</button>
    <AgentLaunch v-if="launching" :workspace="workspace" :item-id="itemId" :initial-instruction="initialInstruction" initial-agent-id="development" @close="launching = false" @launched="refresh()" />
    <div v-if="assignments.length" class="development-history">
      <h3>本事项的开发委托</h3>
      <article v-for="assignment in assignments" :key="assignment.id" class="lw-note-card">
        <div class="lw-between"><strong>{{ assignment.instruction }}</strong><span class="lw-small">{{ assignment.status }}</span></div>
        <p class="lw-tiny lw-muted">{{ assignment.agentId }} {{ assignment.agentVersion.slice(0, 12) }} · {{ assignment.engine }}{{ assignment.model ? ` / ${assignment.model}` : ' / 默认模型' }} · Git {{ assignment.repositoryRevision.slice(0, 12) }} · 上下文 {{ assignment.contextVersionId }} · {{ assignment.reviewMode === 'self' ? '自检' : '独立审阅' }}</p>
        <p v-if="assignment.workingTreeExcluded" class="lw-small">开始时仓库存在未提交改动，本轮输入不包含它们。</p>
        <p v-if="assignment.error" class="lw-notice warning">{{ assignment.error }}</p>
        <button v-if="['planning','reviewing','implementing'].includes(assignment.status)" class="lw-btn ghost sm" type="button" :disabled="busy" @click="cancel(assignment.id)">停止委托</button>
        <p v-if="assignment.status === 'plan_ready'" class="lw-small">方案与审阅已完成。本次仅授权方案，未建立可写实施运行。若要实施，请发起新的委托以重新核对当前源码、事项背景和知识版本。</p>
        <p v-if="assignment.status === 'delivery_failed'" class="lw-notice warning">实施运行已结束，但固定交付包未生成：{{ assignment.error }}</p>
        <p v-if="assignment.status === 'awaiting_acceptance'" class="lw-small">实施运行已结束。请核对结果、运行事件与固定交付包；业务接受仍待确认。</p>
        <DevelopmentDelivery v-if="deliveries[assignment.id]" :workspace="workspace" :delivery="deliveries[assignment.id]!" @updated="refresh()" />
        <p v-else-if="assignment.status === 'awaiting_acceptance'" class="lw-small lw-muted">此历史委托没有固定交付包；请核对原始 Run 与 Git 差异，不能在这里直接接受。</p>
        <div v-if="assignment.implementationRunId"><button class="lw-btn ghost sm" type="button" @click="showDiff(assignment.id)">查看实际 Git 差异</button><details v-if="diffs[assignment.id]" open><summary>实际改动 {{ diffs[assignment.id]!.fileCount }} 个文件{{ diffs[assignment.id]!.truncated ? ' · 页面已截断' : '' }}</summary><p class="lw-tiny lw-muted">基于提交 {{ diffs[assignment.id]!.baseRevision.slice(0, 12) }}。执行输入文件已从差异中排除；受管运行本身不会自动合入目标仓。</p><p v-if="diffs[assignment.id]!.generatedArtifactsExcluded.length" class="lw-tiny lw-muted">已排除 {{ diffs[assignment.id]!.generatedArtifactsExcluded.length }} 个未跟踪的测试缓存文件；它们未计入改动数。</p><pre class="development-diff">{{ diffs[assignment.id]!.patch || '没有代码差异' }}</pre></details></div>
        <details v-if="assignment.inputVersions.length"><summary>固定输入与版本</summary><ul><li v-for="entry in assignment.inputVersions" :key="entry.id">{{ entry.id }} · {{ entry.version.slice(0, 12) }} · {{ entry.sourcePath }}</li></ul></details>
        <PluginProcess :process="process" :assignment-id="assignment.id" :error="processError" />
        <RouterLink class="lw-btn ghost sm" :to="`/lifeweave/${workspace}/agent-executions/managed_development/${assignment.id}`">查看统一执行详情</RouterLink>
        <details v-for="stage in stages" :key="stage.key" :open="stage.key === 'implementationRunId' && assignment.status === 'awaiting_acceptance'">
          <summary>{{ stage.title }} · {{ assignment[stage.key] ? (runs[assignment[stage.key]!]?.state || '读取中') : '尚未开始' }}</summary>
          <template v-if="assignment[stage.key]"><p class="lw-tiny lw-mono">Run {{ assignment[stage.key] }} · {{ runs[assignment[stage.key]!]?.directory || '等待执行机' }}</p><p v-if="runs[assignment[stage.key]!]?.environmentSnapshot" class="lw-tiny lw-muted">实际模型：{{ runs[assignment[stage.key]!]!.environmentSnapshot?.effectiveModel || '执行器未报告' }} · 来源：{{ runs[assignment[stage.key]!]!.environmentSnapshot?.modelSource || '未知' }} · 凭据：{{ runs[assignment[stage.key]!]!.environmentSnapshot?.credentialSource || '未报告' }}</p>
            <MarkdownBody v-if="runs[assignment[stage.key]!]?.result" :content="runs[assignment[stage.key]!]!.result!" />
            <p v-if="runs[assignment[stage.key]!]?.error" class="lw-notice warning">{{ runs[assignment[stage.key]!]!.error }}</p>
            <RouterLink class="lw-text-btn" :to="`/lifeweave/${workspace}/agent-executions/managed_run/${assignment[stage.key]}`">查看完整事件 →</RouterLink><RunTrace :events="events[assignment[stage.key]!] || []" />
          </template>
        </details>
      </article>
    </div>
    <p v-else class="lw-small lw-muted">此事项尚无网页发起的开发委托。</p>
    <ExternalDevelopmentPanel :workspace="workspace" :item-id="itemId" />
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

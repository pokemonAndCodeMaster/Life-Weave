<script setup lang="ts">
import { computed, toRef } from 'vue'
import { RouterLink } from 'vue-router'
import type { ExecutionKind } from '../../api/agents'
import { useExecutionDetail } from '../../composables/useExecutionDetail'
import type { WorkspaceKind } from '../../types'
import ExecutionEventList from './ExecutionEventList.vue'

const props = defineProps<{ workspace: WorkspaceKind; kind: ExecutionKind; executionId: string }>()
const { detail, loading, error, refresh } = useExecutionDetail(toRef(props, 'workspace'), toRef(props, 'kind'), toRef(props, 'executionId'))
const execution = computed(() => detail.value?.execution)
const inputRows = computed(() => Object.entries(detail.value?.inputs ?? {}).filter(([, value]) => value !== null && value !== undefined && value !== ''))
const outputRows = computed(() => detail.value?.outputs ?? [])
const failure = computed(() => {
  const row = detail.value?.execution as unknown as Record<string, unknown> | undefined
  return typeof row?.error === 'string' ? row.error : ''
})
const labels: Record<string, string> = {managed_development:'受管开发',managed_run:'受管运行',external_session:'外部会话',organization:'事项整理'}
function text(value: unknown): string { return typeof value === 'string' ? value : typeof value === 'number' || typeof value === 'boolean' ? String(value) : JSON.stringify(value) }
function outputTitle(value: Record<string, unknown>): string { return value.kind === 'organization_proposal' ? '事项整理建议与变更' : String(value.title ?? value.name ?? value.id ?? '成果') }
function proposal(value: Record<string, unknown>): { changes?: Array<{itemId:string;title:string;before:unknown;after:unknown}>; status?:string } | null { return value.kind === 'organization_proposal' && value.proposal && typeof value.proposal === 'object' ? value.proposal as {changes?:Array<{itemId:string;title:string;before:unknown;after:unknown}>;status?:string} : null }
</script>

<template>
  <section class="execution-detail" aria-label="执行详情">
    <p v-if="loading && !detail" role="status">正在读取执行详情…</p>
    <div v-if="error" class="lw-notice warning" role="alert">{{ error }} <button type="button" class="lw-btn sm" @click="refresh()">重试</button></div>
    <template v-if="detail && execution">
      <header class="detail-head"><div><p class="eyebrow">{{ labels[execution.kind] }} · {{ execution.agentName || execution.agentId || '未记录 Agent' }}<span v-if="execution.agentIdentity === 'inferred'">（按历史记录推断关联）</span></p><h1>{{ execution.title || '执行详情' }}</h1><p class="detail-status">{{ execution.status }} · {{ execution.createdAt ? new Date(execution.createdAt).toLocaleString('zh-CN') : '开始时间未报告' }} <span v-if="execution.engine">· {{ execution.engine === 'builtin' ? '内置规则执行' : execution.engine }}{{ execution.model ? ` / ${execution.model}` : '' }}</span></p></div><button type="button" class="lw-btn sm" @click="refresh()">刷新</button></header>
      <p v-if="failure" class="lw-notice warning" role="alert">{{ failure }}</p>
      <div class="detail-links"><RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(execution.itemId)}/overview`">打开所属事项</RouterLink><RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(execution.itemId)}/outputs`">阅读固定成果</RouterLink></div>
      <div class="detail-grid"><section class="detail-card"><h2>本次输入</h2><dl v-if="inputRows.length"><template v-for="[key, value] in inputRows" :key="key"><dt>{{ key }}</dt><dd><details v-if="typeof value === 'object'"><summary>查看已固定输入</summary><pre>{{ JSON.stringify(value, null, 2) }}</pre></details><template v-else>{{ text(value) }}</template></dd></template></dl><p v-else>没有可展示的输入快照。</p></section><section class="detail-card"><h2>执行配置</h2><dl v-if="Object.keys(detail.configuration || {}).length"><template v-for="[key, value] in Object.entries(detail.configuration)" :key="key"><dt>{{ key }}</dt><dd>{{ text(value) }}</dd></template></dl><p v-else>没有配置快照。</p></section></div>
      <section class="detail-card"><h2>实际产出</h2><ul v-if="outputRows.length" class="output-list"><li v-for="(output, index) in outputRows" :key="String(output.id ?? index)"><strong>{{ outputTitle(output) }}</strong><p v-if="output.summary">{{ output.summary }}</p><template v-if="proposal(output)"><p>整理建议 {{ proposal(output)?.status }} · {{ proposal(output)?.changes?.length ?? 0 }} 项关系变化</p><ul><li v-for="change in proposal(output)?.changes ?? []" :key="change.itemId">{{ change.title }}<details><summary>查看前后差异</summary><pre>之前 {{ JSON.stringify(change.before, null, 2) }}
之后 {{ JSON.stringify(change.after, null, 2) }}</pre></details></li></ul></template><RouterLink v-if="output.id && output.kind !== 'organization_proposal'" :to="{ path: `/lifeweave/${workspace}/items/${encodeURIComponent(execution.itemId)}/outputs`, query: { output: String(output.id) } }">在事项中阅读</RouterLink><details><summary>查看产出原始记录</summary><pre>{{ JSON.stringify(output, null, 2) }}</pre></details></li></ul><p v-else>目前没有登记产出。</p></section>
      <section v-if="detail.children.length" class="detail-card"><h2>执行步骤</h2><ul class="child-list"><li v-for="child in detail.children" :key="child.kind + ':' + child.id"><RouterLink :to="`/lifeweave/${workspace}/agent-executions/${child.kind}/${encodeURIComponent(child.id)}`">{{ child.stage || child.id }}</RouterLink><span>{{ child.status }}</span></li></ul></section>
      <section v-if="detail.launches?.length" class="detail-card"><h2>操作记录</h2><ol class="operation-list"><li v-for="launch in detail.launches" :key="launch.requestId || launch.createdAt"><strong>{{ launch.operation }} · {{ launch.agentName || launch.agentId }}</strong><span>{{ new Date(launch.createdAt).toLocaleString('zh-CN') }}</span><details><summary>本次固定配置与输入</summary><pre>{{ JSON.stringify({configuration:launch.configuration,input:launch.input,output:launch.output}, null, 2) }}</pre></details></li></ol></section>
      <div class="coverage" role="note"><strong>轨迹来源与覆盖</strong><p>{{ detail.coverage.description || execution.traceCoverage || detail.coverage.level }}</p><ul v-if="detail.coverage.missing.length"><li v-for="gap in detail.coverage.missing" :key="gap">{{ gap }}</li></ul></div>
      <ExecutionEventList :events="detail.events" />
    </template>
  </section>
</template>

<style scoped>
.execution-detail{display:grid;gap:18px;min-width:0}.detail-head{display:flex;justify-content:space-between;align-items:start;gap:15px}.eyebrow{font-size:11px;color:#5a7896;margin:0 0 5px}.detail-head h1{font-size:24px;margin:0;color:#263a4f}.detail-status{font-size:12px;color:#697d8f;margin:7px 0 0}.detail-links{display:flex;gap:15px;flex-wrap:wrap;font-size:12px}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.detail-card,.coverage{border:1px solid #e1e8ef;border-radius:10px;padding:17px;background:#fff;min-width:0}.detail-card h2{font-size:14px;margin:0 0 12px}.detail-card p,.coverage p{font-size:12px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere}.detail-card dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:7px 13px;font-size:12px}.detail-card dt{color:#65798d}.detail-card dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.output-list,.child-list{margin:0;padding-left:18px;display:grid;gap:9px;font-size:12px}.output-list p{margin:4px 0}.child-list li{display:flex;gap:10px;justify-content:space-between}.coverage{background:#f7f9fc}.coverage strong{font-size:12px}.coverage ul{margin:0;padding-left:18px;font-size:11px;color:#687d90}@media(max-width:700px){.detail-grid{grid-template-columns:1fr}.detail-head{flex-wrap:wrap}}
.detail-card details{font-size:11px}.detail-card summary{cursor:pointer;color:#426b93}.detail-card pre{max-height:450px;overflow:auto;background:#f8fafc;padding:9px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:10px}
.operation-list{display:grid;gap:10px;margin:0;padding-left:18px;font-size:12px}.operation-list li span{margin-left:10px;color:#71869a}
</style>

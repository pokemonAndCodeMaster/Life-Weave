<script setup lang="ts">
import { computed, toRef } from 'vue'
import { RouterLink } from 'vue-router'
import type { ExecutionKind } from '../../api/agents'
import { useExecutionDetail } from '../../composables/useExecutionDetail'
import type { WorkspaceKind } from '../../types'
import MarkdownBody from '../MarkdownBody.vue'
import ExecutionEventList from './ExecutionEventList.vue'

const props = defineProps<{ workspace: WorkspaceKind; kind: ExecutionKind; executionId: string }>()
const { detail, loading, error, refresh } = useExecutionDetail(toRef(props, 'workspace'), toRef(props, 'kind'), toRef(props, 'executionId'))
const execution = computed(() => detail.value?.execution)
const inputs = computed<Record<string, unknown>>(() => detail.value?.inputs ?? {})
const configuration = computed<Record<string, unknown>>(() => detail.value?.configuration ?? {})
const outputRows = computed(() => detail.value?.outputs ?? [])
const failure = computed(() => {
  const row = detail.value?.execution as unknown as Record<string, unknown> | undefined
  return typeof row?.error === 'string' ? row.error : ''
})

const kindLabels: Record<string, string> = { managed_development: '受管开发', managed_run: '受管运行', external_session: '外部会话', organization: '事项整理' }
const statusLabels: Record<string, string> = {
  queued: '等待执行', claimed: '准备中', running: '执行中', planning: '形成方案', reviewing: '审阅中', implementing: '实施中',
  pause_requested: '正在暂停', paused: '已暂停', cancelling: '正在取消', cancelled: '已取消',
  succeeded: '已成功', failed: '执行失败', unavailable: '环境不可用', blocked: '受阻',
  plan_ready: '方案待审阅', awaiting_acceptance: '成果待验收', delivery_failed: '交付生成失败',
  accepted: '已接受', rejected: '已拒绝', reported: '已有外部报告', finished: '外部会话已结束',
  proposed: '建议待应用', applied: '已应用', undone: '已撤销',
}
const stageLabels: Record<string, string> = { plan: '方案', review: '审阅', implementation: '实施与验证' }
const operationLabels: Record<string, string> = { propose: '提出建议', apply: '应用整理', undo: '撤销整理' }
function brief(value: string, limit = 180): string {
  const plain = value.replace(/\s+/g, ' ').trim()
  return plain.length > limit ? `${plain.slice(0, limit)}…` : plain
}
function stringValue(value: unknown): string { return typeof value === 'string' ? value.trim() : '' }
function statusLabel(value: string): string { return statusLabels[value] ?? '状态未说明' }
function engineLabel(value: unknown): string { return ({ codex: 'Codex', opencode: 'OpenCode', builtin: '内置规则执行' } as Record<string, string>)[String(value)] ?? (value ? String(value) : '未记录') }
const heading = computed(() => brief(execution.value?.title || '执行详情', 120))
const task = computed(() => brief(stringValue(inputs.value.instruction) || execution.value?.title || '', 180) || '任务说明未记录')
const repository = computed(() => brief(stringValue(inputs.value.repositoryPath) || stringValue(configuration.value.repositoryPath) || stringValue(inputs.value.directory), 120))
const model = computed(() => brief(stringValue(configuration.value.model) || execution.value?.model || '', 80) || '执行器默认')
const method = computed(() => brief(stringValue(configuration.value.methodTitle) || stringValue(inputs.value.methodTitle), 120) ||
  (configuration.value.methodId || inputs.value.methodId ? '已绑定方法（展开查看标识）' : '未指定'))
const knowledgeCount = computed(() => {
  const direct = configuration.value.knowledgeRefs ?? inputs.value.knowledgeRefs
  if (Array.isArray(direct)) return direct.length
  const environment = inputs.value.environment as Record<string, unknown> | undefined
  const selected = environment?.selectedInputs as Record<string, unknown> | undefined
  return Array.isArray(selected?.knowledgeRefs) ? selected.knowledgeRefs.length : null
})
const scopeLabel = computed(() => {
  const scope = configuration.value.executionScope ?? inputs.value.executionScope
  return scope === 'implement' ? '方案通过后实施' : scope === 'plan_only' ? '仅形成方案' : ''
})
const reviewLabel = computed(() => {
  const mode = configuration.value.reviewMode ?? inputs.value.reviewMode
  return mode === 'independent' ? '独立审阅' : mode === 'self' ? '自检' : ''
})
function outputTitle(value: Record<string, unknown>): string {
  const label: Record<string, string> = { organization_proposal: '事项整理建议与变更', plan: '方案', review: '审阅结论', delivery: '固定交付', result: '运行结果', artifact_candidate: '待固定产物候选' }
  return label[String(value.kind)] ?? brief(String(value.title ?? value.name ?? '成果'), 120)
}
function proposal(value: Record<string, unknown>): { changes?: Array<{itemId:string;title:string;before:unknown;after:unknown}>; status?:string } | null {
  return value.kind === 'organization_proposal' && value.proposal && typeof value.proposal === 'object'
    ? value.proposal as {changes?:Array<{itemId:string;title:string;before:unknown;after:unknown}>;status?:string}
    : null
}
</script>

<template>
  <section class="execution-detail" aria-label="执行详情">
    <p v-if="loading && !detail" role="status">正在读取执行详情…</p>
    <div v-if="error" class="lw-notice warning" role="alert">{{ error }} <button type="button" class="lw-btn sm" @click="refresh()">重试</button></div>
    <template v-if="detail && execution">
      <header class="detail-head">
        <div>
          <p class="eyebrow">{{ kindLabels[execution.kind] }} · {{ execution.agentName || '未记录 Agent' }}<span v-if="execution.agentIdentity === 'inferred'">（按历史记录推断关联）</span></p>
          <h1>{{ heading }}</h1>
          <p class="detail-status">{{ statusLabel(execution.status) }} · {{ execution.createdAt ? new Date(execution.createdAt).toLocaleString('zh-CN') : '开始时间未报告' }} <span v-if="execution.engine">· {{ engineLabel(execution.engine) }}{{ execution.model ? ` / ${model}` : '' }}</span></p>
        </div>
        <button type="button" class="lw-btn sm" @click="refresh()">刷新</button>
      </header>
      <p v-if="failure" class="lw-notice warning" role="alert">{{ failure }}</p>
      <div class="detail-links">
        <RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(execution.itemId)}/overview`">打开所属事项</RouterLink>
        <RouterLink :to="`/lifeweave/${workspace}/items/${encodeURIComponent(execution.itemId)}/outputs`">阅读固定成果</RouterLink>
      </div>
      <div class="detail-grid">
        <section class="detail-card" aria-label="本次输入">
          <h2>本次输入</h2>
          <dl class="summary-list"><dt>任务</dt><dd>{{ task }}</dd><template v-if="repository"><dt>目标仓库</dt><dd>{{ repository }}</dd></template><template v-if="scopeLabel"><dt>执行范围</dt><dd>{{ scopeLabel }}</dd></template><template v-if="reviewLabel"><dt>检查方式</dt><dd>{{ reviewLabel }}</dd></template></dl>
          <details v-if="Object.keys(inputs).length" class="raw-record"><summary>查看完整固定输入</summary><pre>{{ JSON.stringify(inputs, null, 2) }}</pre></details>
        </section>
        <section class="detail-card" aria-label="执行配置">
          <h2>执行配置</h2>
          <dl class="summary-list"><dt>Agent</dt><dd>{{ execution.agentName || '未记录' }}</dd><dt>执行器</dt><dd>{{ engineLabel(configuration.engine ?? execution.engine) }}</dd><dt>模型</dt><dd>{{ model }}</dd><dt>方法</dt><dd>{{ method }}</dd><dt>知识</dt><dd>{{ knowledgeCount == null ? '未记录' : `${knowledgeCount} 篇` }}</dd><template v-if="configuration.runtime"><dt>运行方式</dt><dd>{{ configuration.runtime === 'docker' ? '容器' : '本机' }}</dd></template><template v-if="configuration.permission"><dt>目录权限</dt><dd>{{ configuration.permission === 'workspace-write' ? '工作目录可写' : '只读' }}</dd></template></dl>
          <details v-if="Object.keys(configuration).length" class="raw-record"><summary>查看完整配置与技术标识</summary><pre>{{ JSON.stringify(configuration, null, 2) }}</pre></details>
        </section>
      </div>
      <section class="detail-card" aria-label="实际产出">
        <h2>实际产出</h2>
        <ul v-if="outputRows.length" class="output-list"><li v-for="(output, index) in outputRows" :key="String(output.id ?? index)"><strong>{{ outputTitle(output) }}</strong><p v-if="output.summary || output.content">{{ brief(String(output.summary || output.content), 220) }}</p><template v-if="proposal(output)"><p>整理建议 {{ statusLabel(proposal(output)?.status || '') }} · {{ proposal(output)?.changes?.length ?? 0 }} 项关系变化</p><ul><li v-for="change in proposal(output)?.changes ?? []" :key="change.itemId">{{ brief(change.title, 120) }}<details><summary>查看前后差异</summary><pre>之前 {{ JSON.stringify(change.before, null, 2) }}
之后 {{ JSON.stringify(change.after, null, 2) }}</pre></details></li></ul></template><RouterLink v-if="output.id && output.kind !== 'organization_proposal'" :to="{ path: `/lifeweave/${workspace}/items/${encodeURIComponent(execution.itemId)}/outputs`, query: { output: String(output.id) } }">在事项中阅读</RouterLink><details v-if="typeof output.content === 'string' && output.content" class="output-reading"><summary>展开阅读正文</summary><MarkdownBody :content="String(output.content)" :workspace="workspace" /></details><details><summary>查看产出原始记录</summary><pre>{{ JSON.stringify(output, null, 2) }}</pre></details></li></ul>
        <p v-else>目前没有登记产出。</p>
      </section>
      <section v-if="detail.children.length" class="detail-card" aria-label="执行步骤"><h2>执行步骤</h2><ul class="child-list"><li v-for="child in detail.children" :key="child.kind + ':' + child.id"><RouterLink :to="`/lifeweave/${workspace}/agent-executions/${child.kind}/${encodeURIComponent(child.id)}`">{{ stageLabels[child.stage] || '执行阶段' }}</RouterLink><span>{{ statusLabel(child.status) }}</span></li></ul></section>
      <section v-if="detail.launches?.length" class="detail-card" aria-label="操作记录"><h2>操作记录</h2><ol class="operation-list"><li v-for="launch in detail.launches" :key="launch.requestId || launch.createdAt"><strong>{{ operationLabels[launch.operation] || '操作' }} · {{ launch.agentName || 'Agent' }}</strong><span>{{ new Date(launch.createdAt).toLocaleString('zh-CN') }}</span><details><summary>本次固定配置与输入</summary><pre>{{ JSON.stringify({configuration:launch.configuration,input:launch.input,output:launch.output}, null, 2) }}</pre></details></li></ol></section>
      <div class="coverage" role="note"><strong>轨迹来源与覆盖</strong><p>{{ detail.coverage.description || execution.traceCoverage || detail.coverage.level }}</p><ul v-if="detail.coverage.missing.length"><li v-for="gap in detail.coverage.missing" :key="gap">{{ gap }}</li></ul></div>
      <ExecutionEventList :events="detail.events" />
    </template>
  </section>
</template>

<style scoped>
.execution-detail{display:grid;gap:18px;min-width:0}.detail-head{display:flex;justify-content:space-between;align-items:start;gap:15px}.eyebrow{font-size:11px;color:#5a7896;margin:0 0 5px}.detail-head h1{font-size:24px;margin:0;color:#263a4f;overflow-wrap:anywhere}.detail-status{font-size:12px;color:#697d8f;margin:7px 0 0}.detail-links{display:flex;gap:15px;flex-wrap:wrap;font-size:12px}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.detail-card,.coverage{border:1px solid #e1e8ef;border-radius:10px;padding:17px;background:#fff;min-width:0}.detail-card h2{font-size:14px;margin:0 0 12px}.detail-card p,.coverage p{font-size:12px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere}.summary-list{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:7px 13px;margin:0;font-size:12px}.summary-list dt{color:#65798d}.summary-list dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.output-list,.child-list{margin:0;padding-left:18px;display:grid;gap:9px;font-size:12px}.output-list p{margin:4px 0}.child-list li{display:flex;gap:10px;justify-content:space-between}.coverage{background:#f7f9fc}.coverage strong{font-size:12px}.coverage ul{margin:0;padding-left:18px;font-size:11px;color:#687d90}.raw-record{margin-top:15px;border-top:1px solid #e9eef3;padding-top:10px}@media(max-width:700px){.detail-grid{grid-template-columns:1fr}.detail-head{flex-wrap:wrap}}
.detail-card details{font-size:11px}.detail-card summary{cursor:pointer;color:#426b93}.detail-card pre{max-height:450px;overflow:auto;background:#f8fafc;padding:9px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:10px}.operation-list{display:grid;gap:10px;margin:0;padding-left:18px;font-size:12px}.operation-list li span{margin-left:10px;color:#71869a}
</style>

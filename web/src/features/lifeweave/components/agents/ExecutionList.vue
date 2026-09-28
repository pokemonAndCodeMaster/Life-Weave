<script setup lang="ts">
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError } from '../../api/lifeweave'
import { listAgentExecutions, type ExecutionRef } from '../../api/agents'
import type { WorkspaceKind } from '../../types'

const props = defineProps<{ workspace: WorkspaceKind; initialAgentId?: string }>()
const rows = shallowRef<ExecutionRef[]>([])
const total = shallowRef(0)
const agentId = shallowRef('')
const itemId = shallowRef('')
const status = shallowRef('')
const error = shallowRef('')
const loading = shallowRef(false)
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
async function load(more = false, ticket = generation) {
  loading.value = true; clearTimeout(timer)
  try {
    const result = await listAgentExecutions(props.workspace, { agentId: agentId.value || undefined, itemId: itemId.value || undefined, status: status.value || undefined, limit: 50, offset: more ? rows.value.length : 0 })
    if (ticket !== generation) return
    rows.value = more ? [...rows.value, ...result.items] : result.items
    total.value = result.total; error.value = ''
    if (rows.value.some(row => ['queued','claimed','running','planning','reviewing','implementing'].includes(row.status))) timer = setTimeout(() => void load(false, ticket), 3000)
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) loading.value = false }
}
watch(() => [props.workspace, props.initialAgentId], () => { agentId.value = props.initialAgentId ?? ''; generation++; rows.value = []; void load(false, generation) }, { immediate: true })
watch([agentId, itemId, status], () => { generation++; rows.value = []; void load(false, generation) })
onBeforeUnmount(() => { generation++; clearTimeout(timer) })
const source: Record<string,string> = {managed_development:'受管开发',managed_run:'受管运行',external_session:'外部会话',organization:'事项整理'}
</script>

<template>
  <section class="execution-list">
    <div class="filters"><label class="lw-label">Agent ID<input v-model="agentId" class="lw-field" placeholder="全部 Agent" /></label><label class="lw-label">事项 ID<input v-model="itemId" class="lw-field" placeholder="全部事项" /></label><label class="lw-label">状态<select v-model="status" class="lw-field"><option value="">全部状态</option><option value="running">运行中</option><option value="succeeded">成功</option><option value="failed">失败</option><option value="awaiting_acceptance">待验收</option><option value="cancelled">已取消</option></select></label><button type="button" class="lw-btn sm" @click="load()">刷新</button></div>
    <p v-if="error" role="alert" class="lw-notice warning">{{ error }} <button type="button" class="lw-btn sm" @click="load()">重试</button></p>
    <p v-if="loading && !rows.length" role="status">正在读取执行记录…</p>
    <div class="lw-panel"><ul v-if="rows.length" class="execution-rows"><li v-for="row in rows" :key="row.kind + ':' + row.id"><RouterLink class="execution-link" :to="`/lifeweave/${workspace}/agent-executions/${row.kind}/${encodeURIComponent(row.id)}`"><strong>{{ row.title || row.agentName || row.agentId || row.id }}</strong><span>{{ source[row.kind] }} · {{ row.status }} · {{ row.createdAt ? new Date(row.createdAt).toLocaleString('zh-CN') : '时间未报告' }}</span><small>事项 {{ row.itemId }} · {{ row.traceCoverage || '轨迹覆盖未说明' }}</small></RouterLink></li></ul><div v-else-if="!loading" class="lw-empty">没有符合条件的执行记录。</div></div>
    <div class="footer"><span>{{ rows.length }} / {{ total }} 条</span><button v-if="rows.length < total" type="button" class="lw-btn sm" :disabled="loading" @click="load(true)">加载更多</button></div>
  </section>
</template>

<style scoped>
.execution-list{display:grid;gap:13px}.filters{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.filters label{flex:1 1 170px}.execution-rows{list-style:none;margin:0;padding:0}.execution-rows li+li{border-top:1px solid #e7ecf0}.execution-link{display:grid;gap:5px;padding:13px 16px;text-decoration:none;color:inherit}.execution-link:hover{background:#f7fafd}.execution-link strong{font-size:13px;color:#264a70}.execution-link span,.execution-link small{font-size:11px;color:#647a8d}.footer{display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#718598}
</style>

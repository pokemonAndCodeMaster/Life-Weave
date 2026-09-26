<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError } from '../api/lifeweave'
import { getExternalDiff, listExternalSessions } from '../api/externalDevelopment'
import type { ExternalActivity, ExternalDiff } from '../api/externalDevelopment'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string }>()
const activities = shallowRef<ExternalActivity[]>([])
const diffs = shallowRef<Record<string, ExternalDiff>>({})
const error = shallowRef('')
const diffError = shallowRef('')
const loading = shallowRef(true)
let generation = 0
let sequence = 0
let timer: ReturnType<typeof setTimeout> | undefined

const sessions = computed(() => {
  const grouped = new Map<string, { start: ExternalActivity; events: ExternalActivity[] }>()
  for (const row of activities.value) {
    const id = row.payload?.sessionId
    if (!id) continue
    if (row.kind === 'external_development_start') grouped.set(id, { start: row, events: [] })
  }
  for (const row of activities.value) {
    const group = grouped.get(row.payload?.sessionId)
    if (group && row.kind !== 'external_development_start') group.events.push(row)
  }
  for (const group of grouped.values()) group.events.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
  return [...grouped.values()].sort((a, b) => b.start.createdAt.localeCompare(a.start.createdAt))
})
const date = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
const source = (row: ExternalActivity) => row.kind === 'external_development_hook'
  ? 'Codex Hook 元事件' : row.kind === 'external_development_binding' ? '本机 CLI 绑定' : '本机会话主动上报'
const phase = (value: string) => ({
  started: '开始', native_binding: '绑定', context: '背景', design: '方案', implementation: '实施',
  verification: '验证', knowledge: '知识', finished: '结束', blocked: '受阻', tool: '工具', stop: 'Turn 停止', interrupt: '中断',
}[value] || value)
async function refresh() {
  clearTimeout(timer)
  const ticket = generation
  const request = ++sequence
  try {
    const rows = await listExternalSessions(props.workspace, props.itemId)
    if (ticket !== generation || request !== sequence) return
    activities.value = rows
    error.value = ''
  } catch (caught) {
    if (ticket === generation && request === sequence) error.value = apiError(caught).message
  } finally {
    if (ticket === generation && request === sequence) {
      loading.value = false
      timer = setTimeout(() => void refresh(), 5000)
    }
  }
}
watch(() => [props.workspace, props.itemId], () => {
  generation++
  clearTimeout(timer)
  activities.value = []; diffs.value = {}; error.value = ''; diffError.value = ''; loading.value = true
  void refresh()
}, { immediate: true })
onBeforeUnmount(() => { generation++; clearTimeout(timer) })
async function showDiff(sessionId: string) {
  const ticket = generation
  const workspace = props.workspace
  const itemId = props.itemId
  try {
    const value = await getExternalDiff(workspace, itemId, sessionId)
    if (ticket !== generation) return
    diffs.value = { ...diffs.value, [sessionId]: value }
    diffError.value = ''
  } catch (caught) {
    if (ticket === generation) diffError.value = apiError(caught).message
  }
}
</script>

<template>
  <section class="external-development" aria-label="本机 Codex 会话">
    <div class="lw-between">
      <div><h3>本机 Codex 会话</h3><p class="lw-small lw-sub">本机 CLI 先关联同一事项，再主动上报阶段；Hook 只显示已收到的元事件。这里不会启动另一个 Agent。</p></div>
      <button class="lw-btn ghost sm" type="button" @click="refresh">刷新会话</button>
    </div>
    <p v-if="error" class="lw-notice warning" role="alert">本机会话读取失败：{{ error }}</p>
    <p v-if="loading" class="lw-small" role="status">正在读取本机会话…</p>
    <p v-else-if="!sessions.length && !error" class="lw-small lw-muted">此事项尚未登记本机 Codex 会话；这不代表此前没有本机开发。</p>
    <article v-for="session in sessions" :key="session.start.payload.sessionId" class="lw-note-card session-card">
      <div class="lw-between"><strong>{{ session.start.body }}</strong><span class="lw-tiny lw-muted">{{ date(session.start.createdAt) }}</span></div>
      <p class="lw-tiny lw-mono">本机记录 {{ session.start.payload.sessionId }}<br />原生 Codex 会话 {{ session.start.payload.nativeSessionId || '未登记' }}</p>
      <p v-if="session.start.payload.observedGit" class="lw-tiny lw-mono">仓库 {{ session.start.payload.observedGit.repositoryPath }}<br />开始提交 {{ session.start.payload.observedGit.revision }}</p>
      <p class="lw-tiny lw-muted">固定方法 {{ session.start.payload.methodId || '未报告' }} · 开始时登记知识 {{ session.start.payload.declaredInputs?.length || 0 }} 篇</p>
      <details v-if="session.start.payload.declaredInputs?.length">
        <summary>固定输入与版本</summary>
        <ul><li v-for="entry in session.start.payload.declaredInputs" :key="entry.id">{{ entry.title }} · {{ entry.sourcePath }} · {{ entry.version }}</li></ul>
      </details>
      <p class="lw-tiny lw-muted">已收到 {{ session.events.filter(row => row.kind === 'external_development_hook').length }} 条 Hook 元事件；{{ session.events.some(row => row.kind === 'external_development_hook') ? '仅代表已收到的事件，不证明完整覆盖' : '尚未观测到 Hook 事件' }}。</p>
      <details v-if="session.events.length">
        <summary>阶段与观测 · {{ session.events.length }} 条</summary>
        <ol class="session-events">
          <li v-for="event in session.events" :key="event.id">
            <strong>{{ phase(event.payload.phase) }} · {{ source(event) }}</strong><span class="lw-tiny lw-muted"> {{ date(event.createdAt) }}</span>
            <p class="lw-small">{{ event.body }}</p>
            <p v-if="event.kind === 'external_development_hook'" class="lw-tiny lw-mono">工具 {{ event.payload.toolName || '未报告' }} · 模型 {{ event.payload.model || '未报告' }} · Turn {{ event.payload.turnId || '未报告' }} · {{ event.payload.exitCode == null ? '退出码未报告' : `退出码 ${event.payload.exitCode}` }} · 输入哈希 {{ event.payload.inputHash || '未报告' }}</p>
            <p v-if="event.payload.observedGit" class="lw-tiny lw-muted">当时 Git {{ event.payload.observedGit.revision.slice(0, 12) }} · 已改 {{ event.payload.observedGit.changedCount }} · 未跟踪 {{ event.payload.observedGit.untrackedCount }}</p>
            <ul v-if="event.payload.reportedChecks?.length"><li v-for="(check, index) in event.payload.reportedChecks" :key="index">主动上报检查：{{ check }}</li></ul>
            <ul v-if="event.payload.declaredInputs?.length"><li v-for="entry in event.payload.declaredInputs" :key="entry.id">新增登记知识：{{ entry.title }} · {{ entry.version }}</li></ul>
          </li>
        </ol>
      </details>
      <button class="lw-btn ghost sm" type="button" @click="showDiff(session.start.payload.sessionId)">查看当前仓库差异</button>
      <p v-if="diffError" class="lw-notice warning" role="alert">{{ diffError }}</p>
      <details v-if="diffs[session.start.payload.sessionId]" open>
        <summary>当前差异 {{ diffs[session.start.payload.sessionId]!.fileCount }} 个文件{{ diffs[session.start.payload.sessionId]!.truncated ? ' · 已截断' : '' }}</summary>
        <p class="lw-tiny lw-muted">{{ diffs[session.start.payload.sessionId]!.scope }}</p>
        <pre class="session-diff">{{ diffs[session.start.payload.sessionId]!.patch || '当前没有 Git 差异' }}</pre>
      </details>
    </article>
  </section>
</template>

<style scoped>
.external-development { display: grid; gap: 12px; border-top: 1px solid var(--lw-line, #dededb); padding-top: 16px; min-width: 0; }
.session-card { display: grid; gap: 8px; min-width: 0; overflow-wrap: anywhere; }
.session-card details { border-top: 1px solid var(--lw-line, #dededb); padding-top: 8px; }
.session-card summary { cursor: pointer; }
.session-card ul, .session-events { padding-inline-start: 20px; }
.session-events li { margin-block: 10px; overflow-wrap: anywhere; }
.session-events p { margin-block: 4px; }
.session-diff { max-height: 440px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; background: #f5f7f5; padding: 12px; }
</style>

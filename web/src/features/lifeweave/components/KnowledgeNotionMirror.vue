<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
import type { Document } from '../api/library'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind; document: Document }>()
interface State { status: string; version?: string; url?: string; lastAttempt?: { status: string; version: string; error: string } }
const configured = shallowRef(false)
const state = shallowRef<State | null>(null)
const busy = shallowRef(false)
const error = shallowRef('')
const message = shallowRef('')
let generation = 0
const key = () => `project:${props.document.path}`
async function refresh() {
  const ticket = ++generation
  const workspace = props.workspace, path = props.document.path
  error.value = ''; message.value = ''
  try {
    const [settings, records] = await Promise.all([
      http.get<{ configured: boolean }>(`/lifeweave/${workspace}/notion-mirror/settings`),
      http.get<Record<string, State>>(`/lifeweave/${workspace}/notion-mirror/status`),
    ])
    if (ticket !== generation || workspace !== props.workspace || path !== props.document.path) return
    configured.value = settings.data.configured
    state.value = records.data[key()] ?? null
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
}
watch(() => [props.workspace, props.document.sourceId, props.document.path, props.document.version], () => {
  configured.value = false; state.value = null; busy.value = false; void refresh()
}, { immediate: true })
async function publish() {
  if (busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  const workspace = props.workspace, path = props.document.path, version = props.document.version
  const ticket = generation
  try {
    const response = await http.post<State>(`/lifeweave/${workspace}/notion-mirror/document`, {
      sourceId: props.document.sourceId, path, expectedVersion: version,
    })
    if (ticket !== generation || workspace !== props.workspace || path !== props.document.path) return
    if (response.data.status === 'unconfigured') { configured.value = false; message.value = 'Notion 后端尚未配置，原文没有发布。' }
    else { state.value = response.data; message.value = '已发布并回读确认当前原文。' }
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) busy.value = false }
}
</script>

<template>
  <section v-if="document.sourceId === 'lifeweave-project'" class="knowledge-mirror" aria-label="Notion 镜像">
    <div class="lw-between"><strong>Notion 镜像</strong><button class="lw-btn sm" type="button" :disabled="busy || !configured" @click="publish">{{ busy ? '正在核对…' : '发布并核对此篇' }}</button></div>
    <p v-if="!configured" class="lw-small lw-muted">产品后端未配置 Notion 镜像。<RouterLink :to="`/lifeweave/${workspace}/settings`">前往设置</RouterLink></p>
    <p v-if="state?.status === 'confirmed'" class="lw-small">上次回读确认：源版本 {{ state.version?.slice(0, 12) }}{{ state.version === document.version ? '（与当前原文相同）' : '（当前原文已变化）' }}。<a v-if="state.url" :href="state.url" target="_blank" rel="noopener noreferrer">打开镜像</a></p>
    <p v-else class="lw-small lw-muted">此篇尚无已确认的镜像。</p>
    <p v-if="state?.lastAttempt?.status === 'failed'" class="lw-small lw-muted">上次尝试失败：{{ state.lastAttempt.error }}</p>
    <p v-if="message" class="lw-small" role="status">{{ message }}</p>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.knowledge-mirror { border-top: 1px solid var(--lw-line, #dededb); margin-top: 18px; padding-top: 14px; display: grid; gap: 8px; }
.knowledge-mirror p { margin: 0; }
</style>

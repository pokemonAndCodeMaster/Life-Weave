<script setup lang="ts">
import { reactive, shallowRef, watch } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind }>()
const form = reactive({ enabled: false, tokenFile: '', rootPage: '' })
const busy = shallowRef(false)
const loaded = shallowRef(false)
const message = shallowRef('')
const status = shallowRef<Record<string, { status: string; url?: string; version?: string; lastAttempt?: { status: string; version: string; error: string } }> >({})
let generation = 0
const endpoint = () => `/lifeweave/${props.workspace}/notion-mirror`
function statusLabel(entry: { status: string; version?: string; lastAttempt?: { status: string; version: string } }) {
  if (entry.lastAttempt?.status === 'failed') {
    if (entry.status === 'confirmed' && entry.version !== entry.lastAttempt.version) return '镜像过期；当前版本同步失败'
    if (entry.status === 'confirmed') return '最近回读失败；远端当前状态未确认'
    return '镜像失败'
  }
  return entry.status === 'confirmed' ? '已回读确认' : entry.status
}
watch(() => props.workspace, async () => {
  const ticket = ++generation; loaded.value = false; message.value = ''
  try {
    const [settings, records] = await Promise.all([http.get(`${endpoint()}/settings`), http.get(`${endpoint()}/status`)])
    if (ticket === generation) { Object.assign(form, settings.data); status.value = records.data; loaded.value = true }
  } catch (caught) { if (ticket === generation) message.value = apiError(caught).message }
}, { immediate: true })
async function save() {
  busy.value = true; message.value = ''
  try { await http.put(`${endpoint()}/settings`, form); message.value = form.enabled ? '已验证 Notion 页面访问并启用自动镜像。' : '已保存，自动镜像停用。' }
  catch (caught) { message.value = apiError(caught).message }
  finally { busy.value = false }
}
async function sync() {
  busy.value = true; message.value = ''
  try {
    const result = (await http.post<{ count: number; failedCount: number }>(`${endpoint()}/sync`, {})).data
    status.value = (await http.get(`${endpoint()}/status`)).data
    message.value = `已回读确认 ${result.count} 篇当前项目文档；${result.failedCount} 篇失败，具体原因见下方状态。`
  } catch (caught) { message.value = apiError(caught).message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="lw-panel pad">
    <h2>Notion 知识镜像</h2>
    <p class="lw-small lw-sub">项目文档和成功归档的研究成果以原文为准，自动生成可在其他设备打开的 Notion 镜像。源文件仍留在代码仓和本机；Linear 保留历史只读。</p>
    <form v-if="loaded" class="lw-stack" @submit.prevent="save">
      <label><input v-model="form.enabled" type="checkbox" :disabled="busy" /> 启用本空间自动镜像</label>
      <label class="lw-label">Notion 集成凭据文件<input v-model="form.tokenFile" class="lw-field" autocomplete="off" placeholder="/home/用户名/.config/lifeweave/notion-token" :disabled="busy" /></label>
      <label class="lw-label">镜像根页面链接<input v-model="form.rootPage" class="lw-field" autocomplete="off" placeholder="https://www.notion.so/..." :disabled="busy" /></label>
      <p class="lw-tiny lw-muted">凭据须存放在当前用户拥有、权限为 600 的本机文件中，并把根页面共享给此集成。保存时验证访问；浏览器中的 Codex OAuth 不能供后台使用。</p>
      <div class="lw-inline"><button class="lw-btn primary" type="submit" :disabled="busy">保存并检查</button><button class="lw-btn" type="button" :disabled="busy || !form.enabled" @click="sync">立即核对项目文档</button></div>
    </form>
    <p v-if="message" class="lw-small" role="status">{{ message }}</p>
    <details v-if="Object.keys(status).length"><summary>镜像状态（{{ Object.keys(status).length }}）</summary><ul><li v-for="(entry, source) in status" :key="source">{{ source }} · {{ statusLabel(entry) }} <span v-if="entry.version">· 上次确认源版本 {{ entry.version.slice(0, 12) }}</span><span v-if="entry.lastAttempt?.status === 'failed'"> · 本次源版本 {{ entry.lastAttempt.version.slice(0, 12) }}：{{ entry.lastAttempt.error }}</span> <a v-if="entry.url" :href="entry.url" target="_blank" rel="noopener noreferrer">打开上次镜像</a></li></ul></details>
  </section>
</template>

<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { apiError } from '../api/lifeweave'
import { pluginCatalog, pluginDetail, setPluginEnabled } from '../api/plugins'
import type { PluginCall, PluginDescriptor } from '../api/plugins'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind }>()
const items = shallowRef<PluginDescriptor[]>([])
const loading = shallowRef(false)
const saving = shallowRef('')
const error = shallowRef('')
const selected = shallowRef('')
const recent = shallowRef<PluginCall[]>([])
const groups = computed(() => {
  const labels: Record<string, string> = { foundation: '基础能力', composite: '组合工作', skill: '工作方法', executor: '执行器', script: '检查脚本' }
  return Object.entries(labels).map(([kind, title]) => ({ kind, title, items: items.value.filter(item => item.kind === kind) }))
    .filter(group => group.items.length)
})
let generation = 0
async function refresh() {
  const ticket = ++generation
  loading.value = true
  try {
    const result = await pluginCatalog(props.workspace)
    if (ticket === generation) { items.value = result.items; error.value = '' }
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) loading.value = false }
}
watch(() => props.workspace, () => { items.value = []; selected.value = ''; recent.value = []; void refresh() }, { immediate: true })
async function inspect(plugin: PluginDescriptor) {
  if (selected.value === plugin.id) { selected.value = ''; recent.value = []; return }
  const workspace = props.workspace
  const ticket = generation
  try {
    const detail = await pluginDetail(workspace, plugin.id)
    if (ticket === generation && workspace === props.workspace) { selected.value = plugin.id; recent.value = detail.recentCalls }
  }
  catch (caught) { if (ticket === generation && workspace === props.workspace) error.value = apiError(caught).message }
}
async function toggle(plugin: PluginDescriptor) {
  if (saving.value) return
  saving.value = plugin.id
  try { await setPluginEnabled(props.workspace, plugin.id, !plugin.enabled, plugin.configVersion); await refresh() }
  catch (caught) { error.value = apiError(caught).message }
  finally { saving.value = '' }
}
</script>

<template>
  <section class="lw-panel pad plugin-catalog" aria-label="插件目录">
    <header class="lw-between"><div><h2>插件目录</h2><p class="lw-small lw-sub">登记、可运行和实际用过分别显示。调用记录请到具体事项查看。</p></div><button class="lw-btn sm" type="button" :disabled="loading" @click="refresh">刷新</button></header>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <p v-if="loading && !items.length" class="lw-small" role="status">正在读取插件…</p>
    <section v-for="group in groups" :key="group.kind" class="plugin-group" :aria-label="group.title">
      <h3>{{ group.title }}</h3>
      <article v-for="plugin in group.items" :key="plugin.id" class="lw-note-card plugin-card">
        <div class="lw-between"><strong>{{ plugin.name }}</strong><span class="lw-tag">{{ plugin.runnable ? '可运行' : '不可运行' }}</span></div>
        <p class="lw-small">{{ plugin.description }}</p>
        <p class="lw-tiny lw-muted">{{ plugin.reason }}</p>
        <div class="lw-between"><span class="lw-tiny lw-muted">{{ plugin.enabled ? '此空间已启用' : '此空间已停用' }} · 配置 v{{ plugin.configVersion }}</span><button class="lw-btn ghost sm" type="button" :disabled="!!saving || loading" @click="toggle(plugin)">{{ plugin.enabled ? '停用新调用' : '启用新调用' }}</button></div>
        <details><summary>身份、组成与观测范围</summary>
          <p class="lw-tiny lw-mono">{{ plugin.id }} @ {{ plugin.version }} · 实现 {{ plugin.implementationDigest.slice(0, 12) }}</p>
          <p class="lw-tiny">操作：{{ plugin.operations.join('、') }}<br />依赖：{{ plugin.requires.length ? plugin.requires.join('、') : '无' }}<br />组成：{{ plugin.composed_of.length ? plugin.composed_of.join('、') : '无' }}</p>
          <p class="lw-tiny lw-muted">{{ plugin.observation_boundary }}</p>
        </details>
        <div><button class="lw-btn ghost sm" type="button" @click="inspect(plugin)">{{ selected === plugin.id ? '收起使用记录' : '查看近期使用' }}</button></div>
        <div v-if="selected === plugin.id" class="plugin-history">
          <p v-if="!recent.length" class="lw-tiny lw-muted">此空间尚无受管调用记录。</p>
          <RouterLink v-for="call in recent" :key="call.id" class="lw-small" :to="`/lifeweave/${workspace}/items/${encodeURIComponent(call.item_id)}/development`">{{ call.started_at.slice(0, 16).replace('T', ' ') }} · {{ call.operation }} · {{ call.state }} · {{ call.item_id }}</RouterLink>
        </div>
      </article>
    </section>
    <p v-if="!loading && !error && !items.length" class="lw-small lw-muted">当前空间没有可显示的插件。</p>
  </section>
</template>

<style scoped>
.plugin-catalog,.plugin-group { display: grid; gap: 12px; }
.plugin-group { border-top: 1px solid var(--lw-line, #dededb); padding-top: 14px; }
.plugin-card { display: grid; gap: 5px; overflow-wrap: anywhere; }
.plugin-card p { margin: 0; }
.plugin-card summary { cursor: pointer; }
.plugin-history { display: grid; gap: 6px; padding: 8px 0; }
</style>

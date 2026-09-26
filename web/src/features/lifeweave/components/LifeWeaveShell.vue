<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { apiError, getLifeWeaveConfig } from '../api/lifeweave'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkspaceKind } from '../types'
import LifeWeaveIcon from './LifeWeaveIcon.vue'
import LifeWeaveModalHost from './LifeWeaveModalHost.vue'
import LoadingState from './LoadingState.vue'

const route = useRoute()
const router = useRouter()
const { activeWorkspace, state, loading, error, toast, rootItems, load, loadRuntime, openModal } = useLifeWeaveWorkspace()
const navOpen = shallowRef(false)
const initialized = shallowRef(false)
const allowedWorkspaces = shallowRef<WorkspaceKind[]>(['personal', 'team'])
const pageLabels: Record<string, string> = { conversation: '与 AI 对话', plan: '计划与优先级', settings: '设置与连接', connections: 'Linear 历史', runs: 'AI 委托', home: '我的日常', items: '工作事项', ideas: '灵感与讨论', knowledge: '知识', meeting: '组会 / 回顾', maintenance: '维护中心', 'item-detail': '事项' }
const workspace = computed(() => activeWorkspace.value)
const isTeam = computed(() => workspace.value === 'team')
const pageLabel = computed(() => pageLabels[String(route.name)] ?? 'LifeWeave')
const nav = computed(() => [
  { name: 'conversation', label: '与 AI 对话', icon: 'message' },
  { name: 'home', label: '我的日常', icon: 'home' }, { name: 'items', label: '工作事项', icon: 'work' },
  { name: 'plan', label: '计划与优先级', icon: 'flag' }, { name: 'runs', label: 'AI 委托', icon: 'spark' }, { name: 'maintenance', label: '能力与评测', icon: 'layers' }, { name: 'connections', label: 'Linear 历史', icon: 'link' }, { name: 'ideas', label: '灵感与讨论', icon: 'idea' }, { name: 'knowledge', label: '知识', icon: 'book' },
])

function path(name: string) { return `/lifeweave/${workspace.value}/${name}` }
async function initialize() {
  try {
    const config = await getLifeWeaveConfig()
    allowedWorkspaces.value = config.workspaces
    const requested = String(route.params.workspace) as WorkspaceKind
    const selected = config.workspaces.includes(requested) ? requested : config.defaultWorkspace
    if (selected !== requested) await router.replace(route.fullPath.replace(/^\/lifeweave\/[^/]+/, `/lifeweave/${selected}`))
    await Promise.all([load(selected), loadRuntime()])
  } catch (caught) {
    const fallback = String(route.params.workspace) as WorkspaceKind
    await load(['personal', 'team'].includes(fallback) ? fallback : 'personal')
    console.warn(apiError(caught).message)
  } finally { initialized.value = true }
}

async function switchWorkspace(event: Event) {
  const next = (event.target as HTMLSelectElement).value as WorkspaceKind
  await router.push(`/lifeweave/${next}/conversation`)
}

function onKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openModal('search') }
}

watch(() => route.params.workspace, async (value, previous) => {
  if (!initialized.value || value === previous) return
  const next = String(value) as WorkspaceKind
  if (!allowedWorkspaces.value.includes(next)) return router.replace(`/lifeweave/${allowedWorkspaces.value[0]}/conversation`)
  await Promise.all([load(next), loadRuntime()])
  navOpen.value = false
})
watch(pageLabel, (label) => { document.title = `${label} · LifeWeave` }, { immediate: true })
onMounted(() => { window.addEventListener('keydown', onKeydown); void initialize() })
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="lifeweave-app">
    <a class="lw-skip-link" href="#lw-main">跳到主要内容</a>
    <aside class="lw-sidebar" :class="{ open: navOpen }">
      <div class="lw-brand"><img src="/favicon.svg" width="32" height="32" alt="" />LifeWeave</div>
      <label class="lw-workspace-switch"><LifeWeaveIcon :name="isTeam ? 'layers' : 'user'" /><select :value="workspace" aria-label="切换工作空间" @change="switchWorkspace"><option v-if="allowedWorkspaces.includes('team')" value="team">团队空间</option><option v-if="allowedWorkspaces.includes('personal')" value="personal">我的空间 · 个人版</option></select></label>
      <div class="lw-nav-caption">日常安排</div>
      <nav aria-label="LifeWeave 主要导航"><RouterLink v-for="entry in nav" :key="entry.name" class="lw-nav-item" :to="path(entry.name)" @click="navOpen = false"><LifeWeaveIcon :name="entry.icon" />{{ entry.label }}<span v-if="entry.name === 'home'" class="count">{{ rootItems.filter((item) => item.attention).length }}</span></RouterLink></nav>
      <div class="lw-nav-caption">固定呈现</div><RouterLink class="lw-nav-item" :to="path('meeting')"><LifeWeaveIcon name="meeting" />{{ isTeam ? '周度组会' : '我的周回顾' }}</RouterLink>
      <div class="lw-nav-note">工作与生活，有序展开。<br />把注意力留给重要的事。</div>
      <div class="lw-sidebar-footer"><RouterLink class="lw-nav-item" :to="path('settings')"><LifeWeaveIcon name="settings" />设置与连接</RouterLink><div class="lw-profile"><span class="lw-avatar me">我</span><div><div class="lw-small lw-strong">{{ isTeam ? '团队成员 / 维护者' : '个人使用者' }}</div><div class="lw-tiny lw-sub">LifeWeave</div></div></div></div>
    </aside>
    <header class="lw-topbar"><button class="lw-btn ghost lw-mobile-nav" type="button" aria-label="打开导航" @click="navOpen = true"><LifeWeaveIcon name="menu" /></button><div class="lw-crumb"><span>{{ isTeam ? '团队空间' : '我的空间' }}</span><span>/</span><span>{{ pageLabel }}</span></div><span class="lw-spacer"></span><button class="lw-btn lw-search-button" type="button" @click="openModal('search')"><LifeWeaveIcon name="search" /><span>查找事项或知识</span><span class="lw-spacer"></span><kbd class="lw-kbd">⌘ K</kbd></button><RouterLink class="lw-btn" :to="{ path: path('conversation'), query: route.params.itemId ? { itemId: String(route.params.itemId) } : {} }"><LifeWeaveIcon name="message" />对话</RouterLink><button class="lw-btn primary" type="button" @click="openModal('idea-create')"><LifeWeaveIcon name="plus" />记录</button></header>
    <main id="lw-main" class="lw-content" tabindex="-1"><div class="lw-page"><LoadingState v-if="!initialized || (loading && !state)" :loading="true" /><LoadingState v-else-if="error && !state" :error="error.message" @retry="load(workspace)" /><RouterView v-else /></div></main>
    <button v-if="navOpen" class="lw-nav-backdrop" type="button" aria-label="关闭导航" @click="navOpen = false"></button>
    <LifeWeaveModalHost />
    <Transition name="lw-toast"><div v-if="toast" class="lw-toast" role="status">{{ toast }}</div></Transition>
  </div>
</template>

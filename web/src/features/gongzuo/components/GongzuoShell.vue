<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { apiError, getGongzuoConfig } from '../api/gongzuo'
import { useGongzuoWorkspace } from '../composables/useGongzuoWorkspace'
import type { WorkspaceKind } from '../types'
import GongzuoIcon from './GongzuoIcon.vue'
import GongzuoModalHost from './GongzuoModalHost.vue'
import LoadingState from './LoadingState.vue'

const route = useRoute()
const router = useRouter()
const { activeWorkspace, state, loading, error, toast, rootItems, load, loadRuntime, openModal } = useGongzuoWorkspace()
const navOpen = shallowRef(false)
const initialized = shallowRef(false)
const allowedWorkspaces = shallowRef<WorkspaceKind[]>(['personal', 'team'])
const pageLabels: Record<string, string> = { plan: '计划与优先级', settings: '设置与连接', connections: 'Linear 事项', runs: 'AI 委托', home: '我的日常', items: '工作事项', ideas: '灵感与讨论', knowledge: '知识', meeting: '组会 / 回顾', maintenance: '维护中心', 'item-detail': '事项' }
const workspace = computed(() => activeWorkspace.value)
const isTeam = computed(() => workspace.value === 'team')
const pageLabel = computed(() => pageLabels[String(route.name)] ?? '经纬')
const nav = computed(() => [
  { name: 'home', label: '我的日常', icon: 'home' }, { name: 'items', label: '工作事项', icon: 'work' },
  { name: 'plan', label: '计划与优先级', icon: 'flag' }, { name: 'runs', label: 'AI 委托', icon: 'spark' }, { name: 'connections', label: 'Linear 事项', icon: 'link' }, { name: 'ideas', label: '灵感与讨论', icon: 'idea' }, { name: 'knowledge', label: '知识', icon: 'book' },
])

function path(name: string) { return `/lifeweave/${workspace.value}/${name}` }
async function initialize() {
  try {
    const config = await getGongzuoConfig()
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
  await router.push(`/lifeweave/${next}/home`)
}

function onKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openModal('search') }
}

watch(() => route.params.workspace, async (value, previous) => {
  if (!initialized.value || value === previous) return
  const next = String(value) as WorkspaceKind
  if (!allowedWorkspaces.value.includes(next)) return router.replace(`/lifeweave/${allowedWorkspaces.value[0]}/home`)
  await Promise.all([load(next), loadRuntime()])
  navOpen.value = false
})
watch(pageLabel, (label) => { document.title = `${label} · 经纬 LifeWeave` }, { immediate: true })
onMounted(() => { window.addEventListener('keydown', onKeydown); void initialize() })
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="gongzuo-app">
    <a class="gz-skip-link" href="#gz-main">跳到主要内容</a>
    <aside class="gz-sidebar" :class="{ open: navOpen }">
      <div class="gz-brand"><img src="/favicon.svg" width="32" height="32" alt="" />经纬 <small>LifeWeave</small></div>
      <label class="gz-workspace-switch"><GongzuoIcon :name="isTeam ? 'layers' : 'user'" /><select :value="workspace" aria-label="切换工作空间" @change="switchWorkspace"><option v-if="allowedWorkspaces.includes('team')" value="team">团队空间</option><option v-if="allowedWorkspaces.includes('personal')" value="personal">我的空间 · 个人版</option></select></label>
      <div class="gz-nav-caption">日常安排</div>
      <nav aria-label="经纬主要导航"><RouterLink v-for="entry in nav" :key="entry.name" class="gz-nav-item" :to="path(entry.name)" @click="navOpen = false"><GongzuoIcon :name="entry.icon" />{{ entry.label }}<span v-if="entry.name === 'home'" class="count">{{ rootItems.filter((item) => item.attention).length }}</span></RouterLink></nav>
      <div class="gz-nav-caption">固定呈现</div><RouterLink class="gz-nav-item" :to="path('meeting')"><GongzuoIcon name="meeting" />{{ isTeam ? '周度组会' : '我的周回顾' }}</RouterLink>
      <div class="gz-nav-note">工作与生活，有序展开。<br />把注意力留给重要的事。</div>
      <div class="gz-sidebar-footer"><RouterLink class="gz-nav-item" :to="path('settings')"><GongzuoIcon name="settings" />设置与连接</RouterLink><div class="gz-profile"><span class="gz-avatar me">我</span><div><div class="gz-small gz-strong">{{ isTeam ? '团队成员 / 维护者' : '个人使用者' }}</div><div class="gz-tiny gz-sub">LifeWeave · 经纬</div></div></div></div>
    </aside>
    <header class="gz-topbar"><button class="gz-btn ghost gz-mobile-nav" type="button" aria-label="打开导航" @click="navOpen = true"><GongzuoIcon name="menu" /></button><div class="gz-crumb"><span>{{ isTeam ? '团队空间' : '我的空间' }}</span><span>/</span><span>{{ pageLabel }}</span></div><span class="gz-spacer"></span><button class="gz-btn gz-search-button" type="button" @click="openModal('search')"><GongzuoIcon name="search" /><span>查找事项或知识</span><span class="gz-spacer"></span><kbd class="gz-kbd">⌘ K</kbd></button><button class="gz-btn primary" type="button" @click="openModal('idea-create')"><GongzuoIcon name="plus" />记录</button></header>
    <main id="gz-main" class="gz-content" tabindex="-1"><div class="gz-page"><LoadingState v-if="!initialized || (loading && !state)" :loading="true" /><LoadingState v-else-if="error && !state" :error="error.message" @retry="load(workspace)" /><RouterView v-else /></div></main>
    <button v-if="navOpen" class="gz-nav-backdrop" type="button" aria-label="关闭导航" @click="navOpen = false"></button>
    <GongzuoModalHost />
    <Transition name="gz-toast"><div v-if="toast" class="gz-toast" role="status">{{ toast }}</div></Transition>
  </div>
</template>

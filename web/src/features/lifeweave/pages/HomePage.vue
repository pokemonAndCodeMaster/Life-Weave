<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import HomeDashboardCard from '../components/HomeDashboardCard.vue'
import PageHeader from '../components/PageHeader.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import { defaultHomeLayout, homeCardLabels, moveHomeCard, normalizeHomeLayout } from '../utils/homeLayout'
import type { HomeCardLayout } from '../types'
import { apiError } from '../api/lifeweave'

const router = useRouter()
const quickIdea = shallowRef('')
const { activeWorkspace, rootItems, runs, state, createIdea, saveHomeLayout } = useLifeWeaveWorkspace()
const needsAttention = computed(() => rootItems.value.filter(item => item.attention))
const activeItems = computed(() => rootItems.value.filter(item => !['已完成', 'accepted', '已取消'].includes(item.state)))
const activeRuns = computed(() => runs.value.filter(run => ['queued', 'claimed', 'running', 'pause_requested'].includes(run.state)))
const isTeam = computed(() => activeWorkspace.value === 'team')
const editing = shallowRef(false)
const saving = shallowRef(false)
const layoutError = shallowRef('')
const cards = shallowRef<HomeCardLayout[]>(defaultHomeLayout(activeWorkspace.value))
const mainCards = computed(() => cards.value.filter(card => card.visible && card.column === 'main'))
const asideCards = computed(() => cards.value.filter(card => card.visible && card.column === 'aside'))
watch(activeWorkspace, () => {
  editing.value = false
  layoutError.value = ''
  cards.value = defaultHomeLayout(activeWorkspace.value)
})
watch([activeWorkspace, () => state.value?.homeLayout], () => {
  if (!editing.value && state.value?.workspace === activeWorkspace.value)
    cards.value = normalizeHomeLayout(state.value.homeLayout, activeWorkspace.value)
}, { immediate: true })

function updateCard(key: HomeCardLayout['key'], change: Partial<HomeCardLayout>) {
  cards.value = cards.value.map(card => card.key === key ? { ...card, ...change } : card)
}
function cancelEditing() {
  cards.value = normalizeHomeLayout(state.value?.homeLayout, activeWorkspace.value)
  editing.value = false
  layoutError.value = ''
}
async function saveLayout() {
  saving.value = true
  layoutError.value = ''
  try {
    await saveHomeLayout({ cards: cards.value })
    editing.value = false
  } catch (caught) { layoutError.value = apiError(caught).message }
  finally { saving.value = false }
}
async function saveQuickIdea() {
  const body = quickIdea.value.trim()
  if (!body) return
  await createIdea({ body, scope: activeWorkspace.value === 'team' ? '团队' : '个人' })
  quickIdea.value = ''
}
</script>

<template>
  <PageHeader
    :title="isTeam ? '团队工作' : '我的日常'"
    :subtitle="isTeam ? '一起看清当前进展、待决事项与最近共识。' : '工作、学习与生活中的计划，在这里接着推进。'"
    eyebrow="FOCUS / 把注意力留给真正需要你的事"
  >
    <RouterLink class="lw-btn primary" :to="`/lifeweave/${activeWorkspace}/conversation`"><LifeWeaveIcon name="message" />与 AI 对话</RouterLink>
    <button class="lw-btn" type="button" @click="router.push(`/lifeweave/${activeWorkspace}/meeting`)"><LifeWeaveIcon name="meeting" />{{ isTeam ? '打开组会' : '打开周回顾' }}</button>
    <button class="lw-btn" type="button" @click="editing ? cancelEditing() : editing = true">{{ editing ? '取消调整' : '调整首页' }}</button>
  </PageHeader>

  <section v-if="editing" class="lw-panel pad home-layout-editor" aria-label="调整首页卡片">
    <div class="lw-between"><div><h2>首页卡片</h2><p class="lw-small lw-sub">个人与团队各自保存布局；隐藏卡片不会删除事项或知识。</p></div><button class="lw-btn sm" type="button" @click="cards = defaultHomeLayout(activeWorkspace)">恢复本空间预设</button></div>
    <div class="home-layout-rows"><div v-for="(card, index) in cards" :key="card.key" class="home-layout-row">
      <label class="lw-checkline"><input type="checkbox" :checked="card.visible" @change="updateCard(card.key, { visible: ($event.target as HTMLInputElement).checked })" />{{ homeCardLabels[card.key] }}</label>
      <label class="lw-small">位置 <select class="lw-field" :value="card.column" @change="updateCard(card.key, { column: ($event.target as HTMLSelectElement).value as HomeCardLayout['column'] })"><option value="main">主栏</option><option value="aside">侧栏</option></select></label>
      <div class="lw-inline"><button class="lw-btn sm" type="button" :disabled="index === 0" :aria-label="`上移${homeCardLabels[card.key]}`" @click="cards = moveHomeCard(cards, card.key, -1)">↑</button><button class="lw-btn sm" type="button" :disabled="index === cards.length - 1" :aria-label="`下移${homeCardLabels[card.key]}`" @click="cards = moveHomeCard(cards, card.key, 1)">↓</button></div>
    </div></div>
    <p v-if="layoutError" class="lw-notice warning" role="alert">{{ layoutError }}</p>
    <button class="lw-btn primary" type="button" :disabled="saving" @click="saveLayout">保存本空间首页</button>
  </section>

  <div class="lw-two-cols">
    <div class="lw-stack">
      <div class="lw-summary-line"><div><strong>{{ needsAttention.length }}</strong><span>项需要判断</span></div><div><strong>{{ activeItems.length }}</strong><span>项正在推进</span></div><div><strong>{{ activeRuns.length }}</strong><span>个委托运行</span></div></div>
      <HomeDashboardCard v-for="card in mainCards" :key="card.key" v-model:idea="quickIdea" :kind="card.key" :workspace="activeWorkspace" :compact="false" :needs-attention="needsAttention" :active-items="activeItems" :root-items="rootItems" @save-idea="saveQuickIdea" />
    </div>
    <aside class="lw-stack">
      <HomeDashboardCard v-for="card in asideCards" :key="card.key" v-model:idea="quickIdea" :kind="card.key" :workspace="activeWorkspace" :compact="true" :needs-attention="needsAttention" :active-items="activeItems" :root-items="rootItems" @save-idea="saveQuickIdea" />
      <section v-if="!state?.items.length" class="lw-notice neutral">当前空间没有数据，可从“记录”开始建立真实内容。</section>
    </aside>
  </div>
</template>

<style scoped>
.home-layout-editor { margin-bottom: 20px; }
.home-layout-editor h2 { margin: 0 0 4px; }
.home-layout-rows { display: grid; gap: 8px; margin: 16px 0; }
.home-layout-row { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(140px, 190px) auto; gap: 12px; align-items: center; border-top: 1px solid #e5ebef; padding-top: 8px; }
.home-layout-row .lw-field { margin-left: 8px; width: auto; }
@media (max-width: 700px) { .home-layout-row { grid-template-columns: 1fr auto; } .home-layout-row > label:nth-child(2) { grid-column: 1; } }
</style>

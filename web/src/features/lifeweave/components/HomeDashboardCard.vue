<script setup lang="ts">
import { computed } from 'vue'
import type { HomeCardLayout, WorkItem, WorkspaceKind } from '../types'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import LifeWeaveIcon from './LifeWeaveIcon.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  kind: HomeCardLayout['key']
  workspace: WorkspaceKind
  compact: boolean
  needsAttention: WorkItem[]
  activeItems: WorkItem[]
  rootItems: WorkItem[]
}>()
const idea = defineModel<string>('idea', { required: true })
const emit = defineEmits<{ saveIdea: [] }>()
const { openModal } = useLifeWeaveWorkspace()
const isTeam = computed(() => props.workspace === 'team')
function itemUrl(id: string, tab = 'overview') {
  return `/lifeweave/${props.workspace}/items/${encodeURIComponent(id)}/${tab}`
}
</script>

<template>
  <section v-if="kind === 'attention' && !compact"><div class="lw-section-title"><h2>需要我处理</h2><StatusBadge value="先看变化，再作决定" tone="blue" /></div><div class="lw-panel"><div v-for="item in needsAttention" :key="item.id" class="lw-action-row"><span class="lw-badge-icon"><LifeWeaveIcon :name="item.state === '已阻塞' ? 'flag' : 'message'" /></span><div class="lw-row-main"><div class="lw-inline"><span class="lw-mono lw-muted">{{ item.id }}</span><StatusBadge :value="item.state === '已阻塞' ? '补充条件' : item.state === '待验收' ? '审阅结果' : item.context.proposals.length ? '有新提案' : '需要判断'" tone="amber" /></div><h3>{{ item.title }}</h3><p>{{ item.update }}</p><span class="lw-tiny lw-muted">{{ item.context.proposals.length ? '候选修改保留原文与来源，采纳后更新共享上下文。' : '这项决定属于你，不需要重新描述全部背景。' }}</span></div><RouterLink class="lw-btn" :to="itemUrl(item.id, item.context.proposals.length ? 'context' : 'overview')">{{ item.context.proposals.length ? '查看上下文变化' : '打开事项' }}</RouterLink></div><div v-if="!needsAttention.length" class="lw-empty">当前没有待你判断的事项。</div></div></section>
  <section v-else-if="kind === 'active' && !compact"><div class="lw-section-title"><h2>我关注的结果</h2><RouterLink class="lw-btn ghost sm" :to="`/lifeweave/${workspace}/items`">查看全部 <LifeWeaveIcon name="arrow" /></RouterLink></div><div class="lw-panel"><div v-for="item in activeItems" :key="item.id" class="lw-list-row home-active-row"><span class="lw-mono lw-muted">{{ item.id }}</span><div class="lw-grow"><RouterLink class="lw-text-btn lw-list-title" :to="itemUrl(item.id)">{{ item.title }}</RouterLink><div class="lw-list-sub">{{ item.update }}</div></div><StatusBadge :value="item.state" /><button class="lw-btn ghost icon-only" type="button" :aria-label="`速览 ${item.title}`" @click="openModal('peek', { item })"><LifeWeaveIcon name="eye" /></button></div><div v-if="!activeItems.length" class="lw-empty">当前没有正在推进的事项。</div></div></section>
  <section v-else-if="kind === 'attention' || kind === 'active'" class="lw-panel pad"><h2>{{ kind === 'attention' ? '需要我处理' : '我关注的结果' }}</h2><div v-for="item in kind === 'attention' ? needsAttention : activeItems" :key="item.id" class="lw-list-row"><RouterLink class="lw-text-btn" :to="itemUrl(item.id)">{{ item.title }}</RouterLink><StatusBadge :value="item.state" /></div><p v-if="!(kind === 'attention' ? needsAttention : activeItems).length" class="lw-empty">{{ kind === 'attention' ? '当前没有待判断事项。' : '当前没有正在推进的事项。' }}</p></section>
  <section v-else-if="kind === 'capture'" class="lw-panel pad"><h2 class="lw-small-heading">先把想法留下来</h2><textarea v-model="idea" class="lw-capture" aria-label="随手记录" placeholder="一句灵感、一个问题，或一段反馈……"></textarea><div class="lw-between lw-mt-10"><span class="lw-tiny lw-muted">仅保存，不启动 AI</span><button class="lw-btn primary sm" type="button" @click="emit('saveIdea')">记下来</button></div></section>
  <section v-else-if="kind === 'context' && rootItems[0]" class="lw-panel pad"><h2 class="lw-small-heading">最近的共同理解</h2><div class="lw-note-card"><div class="lw-inline"><StatusBadge :value="rootItems[0].context.revision ? `共识 v${rootItems[0].context.revision}` : '打开查看上下文'" tone="blue" /><span class="lw-tiny lw-muted">{{ rootItems[0].id }}</span></div><p>{{ rootItems[0].scope }}</p><RouterLink class="lw-text-btn" :to="itemUrl(rootItems[0].id, 'context')">查看依据与未决问题 <LifeWeaveIcon name="arrow" /></RouterLink></div></section>
  <section v-else-if="kind === 'environment'" class="lw-panel pad"><span class="lw-tiny lw-muted">当前工作环境</span><h3 class="lw-environment-title">{{ isTeam ? '团队工作空间' : 'Codex / OpenCode + 这台电脑' }}</h3><p class="lw-small lw-sub">{{ isTeam ? '团队内容单独保存；当前仍由本机用户管理。' : '个人事项也可以没有代码仓、容器和研发流程。' }}</p></section>
</template>

<style scoped>
@media (max-width: 600px) {
  .home-active-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: start; }
  .home-active-row > .lw-mono { grid-column: 1; overflow-wrap: anywhere; }
  .home-active-row > .lw-grow { grid-column: 1 / -1; min-width: 0; }
  .home-active-row > .lw-grow .lw-list-title { overflow-wrap: anywhere; }
  .home-active-row > .lw-tag { grid-column: 1; width: max-content; }
  .home-active-row > button { grid-column: 2; justify-self: end; }
}
</style>

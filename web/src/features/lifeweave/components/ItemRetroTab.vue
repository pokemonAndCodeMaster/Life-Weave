<script setup lang="ts">
import LifeWeaveIcon from './LifeWeaveIcon.vue'
import StatusBadge from './StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkItem } from '../types'

defineProps<{ item: WorkItem; rootItem: WorkItem }>()
const { openModal } = useLifeWeaveWorkspace()
</script>

<template>
  <div class="lw-notice lw-mb-18"><LifeWeaveIcon name="refresh" /><div><strong>复盘让这次工作，改变下一次的做法。</strong><br />只有有复用价值且经过验证的部分，才进入知识、Skill 或 Harness。</div></div>
  <article class="lw-panel lw-article"><h2>从本次工作中提取什么</h2><h3>可复用经验</h3><p>把真实工作里反复出现的问题、有效方法和适用边界保留下来。</p><h3>需要改进的做法</h3><p>记录是哪一段能力导致问题，以及用什么案例证明修改有用。</p><div class="lw-inline"><button class="lw-btn primary" type="button" @click="openModal('improvement-create', { item: rootItem })">形成改进候选</button><button class="lw-btn" type="button" @click="openModal('feedback', { item: rootItem, anchor: '复盘' })">保留复盘记录</button></div></article>
  <div class="lw-section-title"><h2>本事项的能力改进候选</h2></div>
  <article v-for="improvement in rootItem.improvements" :key="improvement.id" class="lw-retro-row"><div class="lw-between"><div class="lw-inline"><StatusBadge :value="improvement.kind" /><span class="lw-mono lw-tiny lw-muted">来自 {{ rootItem.id }}</span></div><StatusBadge :value="improvement.state" /></div><h3>{{ improvement.title }}</h3><p>{{ improvement.body }}</p><div class="lw-tiny lw-muted">目标：{{ improvement.target }} · {{ improvement.version }}</div><div class="lw-step-chips"><span class="on">来源问题</span><b>→</b><span class="on">改进候选</span><b>→</b><span :class="{ on: improvement.checks }">回归验证</span><b>→</b><span :class="{ on: improvement.state === '已发布' }">受审发布</span></div><button class="lw-btn sm" type="button" @click="openModal('improvement-detail', { improvement, item: rootItem })">查看改进与验证</button></article>
  <div v-if="!rootItem.improvements.length" class="lw-panel lw-empty">还没有候选。不要求每件小事都进行完整复盘。</div>
</template>

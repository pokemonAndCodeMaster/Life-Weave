<script setup lang="ts">
import { computed } from 'vue'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'

const stages = ['待整理', '讨论中', '已有后续']
const { activeWorkspace, state, openModal } = useLifeWeaveWorkspace()
const ideas = computed(() => state.value?.ideas ?? [])
</script>

<template>
  <PageHeader title="灵感与讨论" subtitle="记录原话，保留分歧。成熟的线索可以关联到已有事项，也可以形成新的工作。">
    <button class="lw-btn primary" type="button" @click="openModal('idea-create')"><LifeWeaveIcon name="plus" />记录灵感</button>
  </PageHeader>
  <div class="lw-board">
    <section v-for="stage in stages" :key="stage" class="lw-board-col">
      <div class="lw-between"><h2>{{ stage }}</h2><StatusBadge :value="String(ideas.filter((idea) => idea.state === stage).length)" /></div>
      <article v-for="idea in ideas.filter((candidate) => candidate.state === stage)" :key="idea.id" class="lw-idea-card">
        <div class="lw-inline lw-mb-10"><StatusBadge :value="idea.scope" /><span class="lw-mono lw-tiny lw-muted">{{ idea.id }}</span></div>
        <h3>{{ idea.title }}</h3><p class="lw-preline">{{ idea.body }}</p>
        <div class="lw-idea-match"><LifeWeaveIcon name="link" /> {{ idea.reason }}</div>
        <div class="lw-origin">{{ idea.origin }} · 原始记录保留</div>
        <div class="lw-inline">
          <RouterLink v-if="idea.related" class="lw-btn sm" :to="`/lifeweave/${activeWorkspace}/items/${encodeURIComponent(idea.related)}/overview`">查看 {{ idea.related }}</RouterLink>
          <button v-else class="lw-btn sm" type="button" @click="openModal('item-create', { idea })">形成工作事项</button>
          <button class="lw-btn ghost sm" type="button" @click="openModal('idea-discuss', { idea })">继续讨论</button>
        </div>
      </article>
      <div v-if="!ideas.some((idea) => idea.state === stage)" class="lw-empty">这里还没有灵感</div>
    </section>
  </div>
</template>

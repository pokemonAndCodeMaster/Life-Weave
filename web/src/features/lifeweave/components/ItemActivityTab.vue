<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import ExternalDevelopmentEvent from './ExternalDevelopmentEvent.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkItem } from '../types'

const props = defineProps<{ item: WorkItem; rootItem: WorkItem }>()
const { runs, openModal } = useLifeWeaveWorkspace()
const itemRuns = computed(() => runs.value.filter((run) => run.itemId === props.item.id || run.itemId === props.rootItem.id))
const activities = computed(() => props.item.id === props.rootItem.id ? props.item.activities :
  [...props.rootItem.activities, ...props.item.activities].sort((a,b) => a.time.localeCompare(b.time)))
</script>

<template>
  <section class="lw-panel pad"><h2>推进记录</h2><p class="lw-small lw-sub">聚合有意义的变化、决定与运行；不要求所有工作经过同一套阶段。</p><div class="lw-timeline"><div v-for="activity in [...activities].reverse()" :key="activity.id ?? `${activity.time}-${activity.title}`" class="lw-timeline-event"><time>{{ activity.time }}</time><h3>{{ activity.payload?.sessionId ? '外部开发 · '+activity.payload.phase : activity.title }}</h3><p>{{ activity.text }}</p><ExternalDevelopmentEvent :activity="activity" /></div><div v-if="!activities.length" class="lw-empty">事项已建立，等待下一动作。</div></div></section>
  <div class="lw-section-title"><h2>执行尝试与原生会话</h2></div>
  <section class="lw-panel pad"><article v-for="run in itemRuns" :key="run.id" class="lw-run-row"><div class="lw-between"><strong class="lw-mono">{{ run.id }}</strong><StatusBadge :value="run.state" /></div><p class="lw-small">{{ run.instruction || run.result || '本次委托' }}</p><div class="lw-mono lw-muted">{{ run.engine }} · {{ run.session || '会话尚未建立' }} · 上下文 v{{ run.rev }}</div><div class="lw-between lw-mt-10"><span class="lw-tiny lw-muted">{{ run.directory || '工作目录尚未分配' }}</span><button class="lw-btn sm" type="button" @click="openModal('run-detail', { runId: run.id })">查看详情</button></div></article><div v-if="!itemRuns.length" class="lw-empty">尚无运行记录。手工完成的工作也可以关联成果。</div></section>
</template>

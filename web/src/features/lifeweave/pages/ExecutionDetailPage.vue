<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ExecutionDetail from '../components/agents/ExecutionDetail.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { ExecutionKind } from '../api/agents'

const route = useRoute()
const { activeWorkspace } = useLifeWeaveWorkspace()
const kind = computed(() => String(route.params.kind) as ExecutionKind)
const executionId = computed(() => String(route.params.executionId))
</script>

<template>
  <div class="execution-page"><RouterLink :to="`/lifeweave/${activeWorkspace}/agents?tab=executions`" class="lw-text-btn">← 返回执行记录</RouterLink><ExecutionDetail :workspace="activeWorkspace" :kind="kind" :execution-id="executionId" /></div>
</template>

<style scoped>.execution-page{display:grid;gap:18px}</style>

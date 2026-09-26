<script setup lang="ts">
import { computed } from 'vue'
import type { PluginProcess as Process } from '../api/plugins'

const props = defineProps<{ process: Process | null; assignmentId: string; error?: string }>()
const plans = computed(() => props.process?.plans.filter(plan => plan.assignment_id === props.assignmentId) ?? [])
const calls = computed(() => props.process?.calls.filter(call => call.assignment_id === props.assignmentId) ?? [])
const stageNames: Record<string, string> = { planning: '方案', reviewing: '独立审阅', implementing: '实施' }
function matches(stepId: string) { return calls.value.filter(call => call.step_id === stepId) }
function label(state: string) { return ({ started: '进行中', accepted: '已受理', succeeded: '成功', failed: '失败', interrupted: '中断' } as Record<string, string>)[state] || state }
</script>

<template>
  <details class="plugin-process"><summary>插件计划与实际调用 · {{ calls.length }} 次</summary>
    <p v-if="error" class="lw-notice warning" role="status">插件过程暂不可读取：{{ error }}。开发阶段、Run 和原生事件仍以各自记录为准。</p>
    <p class="lw-tiny lw-muted">{{ process?.boundary || '正在读取本次调用…' }}</p>
    <p v-if="!plans.length" class="lw-small lw-muted">此委托创建于插件计划接入之前，没有可追溯的固定插件计划。</p>
    <template v-for="plan in plans" :key="plan.id">
      <p class="lw-tiny lw-mono">固定计划 {{ plan.id }} · v{{ plan.version }}</p>
      <div v-for="step in plan.steps" :key="step.id" class="plugin-step">
        <span><strong>{{ stageNames[step.stage] || step.stage }}</strong> · {{ step.pluginId }} / {{ step.operation }}</span>
        <span class="lw-tiny">{{ step.observation === 'binding-drift' ? '绑定版本偏离' : step.observation === 'unknown-truncated' ? '记录超限，无法判定' : matches(step.id).length ? matches(step.id).map(call => label(call.state)).join('、') : step.required ? '尚无实际调用' : '条件步骤' }}</span>
        <small v-if="matches(step.id).length" class="lw-muted">{{ matches(step.id).map(call => `${call.observed_by} · ${call.run_id || call.id}`).join('；') }}</small>
      </div>
    </template>
    <p v-if="process?.truncated" class="lw-tiny lw-muted">调用列表达到本页上限；请缩小到单次委托读取，避免把截断结果当作完整过程。</p>
    <p v-if="plans.length && calls.some(call => !call.step_id || !plans.some(plan => plan.steps.some(step => step.id === call.step_id)))" class="lw-tiny lw-muted">另有不属于固定步骤的受管调用；可在调用明细接口核对。</p>
  </details>
</template>

<style scoped>
.plugin-process { border-top: 1px solid var(--lw-line, #dededb); padding-top: 8px; }
.plugin-process summary { cursor: pointer; }
.plugin-step { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 12px; padding: 7px 0; border-bottom: 1px solid var(--lw-line, #dededb); font-size: 12px; overflow-wrap: anywhere; }
.plugin-step small { grid-column: 1 / -1; }
@media (max-width: 620px) { .plugin-step { grid-template-columns: 1fr; } }
</style>

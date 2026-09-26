<script setup lang="ts">
import { computed } from 'vue'
import type { RunEvent } from '../types'

const props = defineProps<{ events: RunEvent[] }>()
const ordered = computed(() => [...props.events].sort((left, right) => (left.sequence ?? 0) - (right.sequence ?? 0)))
function time(value?: string) { return value ? new Date(value).toLocaleString('zh-CN') : '时间未报告' }
</script>

<template>
  <div class="run-trace">
    <p v-if="!ordered.length" class="lw-small lw-sub">尚无执行过程事件；排队或执行器未返回过程时可能出现。</p>
    <ol v-else class="run-trace-list">
      <li v-for="event in ordered" :key="event.id ?? event.sequence" class="run-trace-event">
        <div class="run-trace-meta"><span class="run-trace-sequence">#{{ event.sequence ?? '?' }}</span><time>{{ time(event.occurredAt) }}</time><span>{{ event.source || '平台' }}</span><span>{{ event.eventType || event.type || '事件' }}</span></div>
        <p>{{ event.summary || '此步骤没有文字摘要' }}</p>
        <details v-if="event.payload && Object.keys(event.payload).length"><summary>查看原始记录</summary><pre>{{ JSON.stringify(event.payload, null, 2) }}</pre></details>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.run-trace-list { list-style: none; margin: 0; padding: 0 0 0 16px; border-left: 1px solid #dbe3e7; }
.run-trace-event { position: relative; padding: 0 0 18px 18px; overflow-wrap: anywhere; }
.run-trace-event::before { content: ''; position: absolute; left: -21px; top: 5px; width: 9px; height: 9px; background: #4c7893; border: 2px solid #fff; border-radius: 50%; }
.run-trace-meta { display: flex; gap: 8px; flex-wrap: wrap; color: var(--lw-muted); font-size: 11px; }
.run-trace-sequence { font-weight: 700; color: #35617c; }
.run-trace-event p { margin: 6px 0 0; white-space: pre-wrap; line-height: 1.55; }
.run-trace-event details { margin-top: 8px; font-size: 11px; }
.run-trace-event pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 320px; overflow: auto; padding: 10px; border: 1px solid #e2e8ec; border-radius: 6px; }
</style>

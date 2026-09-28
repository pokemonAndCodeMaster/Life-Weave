<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import type { ExecutionEvent } from '../../api/agents'

const props = defineProps<{ events: readonly Readonly<ExecutionEvent>[] }>()
const query = shallowRef('')
const showRaw = shallowRef(false)
const visible = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  return needle ? props.events.filter(event => JSON.stringify(event).toLocaleLowerCase().includes(needle)) : props.events
})
</script>

<template>
  <section class="trace-events" aria-labelledby="trace-heading">
    <div class="trace-header"><h2 id="trace-heading">运行轨迹 <span class="muted">{{ visible.length }} / {{ events.length }} 条</span></h2><label class="lw-small">搜索已采集事件<input v-model="query" class="lw-field" type="search" placeholder="步骤、工具或错误" /></label></div>
    <label class="lw-small"><input v-model="showRaw" type="checkbox" /> 查看原始事件</label>
    <p v-if="!events.length" class="lw-empty">尚未采集到事件。</p>
    <p v-else-if="!visible.length" class="lw-empty">没有匹配的事件。</p>
    <ol v-else class="event-list"><li v-for="event in visible" :key="event.id"><details class="event"><summary><span class="event-number">{{ event.sequence ?? '·' }}</span><span class="event-body"><strong>{{ event.summary || event.eventType }}</strong><small>{{ event.eventType }} · {{ event.source }} · {{ {native:'执行器原生记录',platform:'平台记录',reported:'会话主动报告'}[event.observed] }} · {{ event.occurredAt ? new Date(event.occurredAt).toLocaleString('zh-CN') : '时间未报告' }}</small></span></summary><pre>{{ JSON.stringify(showRaw ? event : event.payload ?? {}, null, 2) }}</pre></details></li></ol>
  </section>
</template>

<style scoped>
.trace-events{display:grid;gap:12px}.trace-header{display:flex;justify-content:space-between;align-items:start;gap:12px;flex-wrap:wrap}.trace-header h2{margin:0;font-size:16px}.trace-header label{min-width:220px}.muted{color:#73879a;font-weight:400;font-size:12px}.event-list{list-style:none;padding:0;margin:0;display:grid;gap:7px}.event{border:1px solid #e1e8ef;border-radius:7px;background:#fff}.event summary{display:flex;align-items:baseline;gap:10px;padding:10px 12px;cursor:pointer}.event-number{width:32px;flex:none;color:#74879a;font:11px ui-monospace,monospace}.event-body{display:grid;gap:3px;min-width:0}.event-body strong{font-size:12px;overflow-wrap:anywhere}.event-body small{font-size:10px;color:#708398}.event pre{margin:0;border-top:1px solid #e1e8ef;padding:11px 12px;overflow:auto;max-height:520px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px;background:#f8fafc}
</style>

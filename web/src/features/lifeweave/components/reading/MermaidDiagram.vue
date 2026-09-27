<script setup lang="ts">
import { onBeforeUnmount, shallowRef, useId, watch } from 'vue'
import { renderMermaid } from '../../utils/mermaidRenderer'
import ReadingMediaDialog from './ReadingMediaDialog.vue'
const props = defineProps<{ source: string }>()
const svg = shallowRef('')
const error = shallowRef('')
const loading = shallowRef(false)
const enlarged = shallowRef(false)
const id = useId().replace(/[^a-zA-Z0-9_-]/g, '-')
let generation = 0
watch(() => props.source, async source => {
  const ticket = ++generation
  svg.value = ''; error.value = ''; loading.value = true; enlarged.value = false
  try { const result = await renderMermaid(`lw-diagram-${id}-${ticket}`, source); if (ticket === generation) svg.value = result }
  catch (caught) { if (ticket === generation) error.value = caught instanceof Error ? caught.message.slice(0, 500) : '图定义无法解析。' }
  finally { if (ticket === generation) loading.value = false }
}, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>
<template>
  <figure class="mermaid-diagram">
    <figcaption class="diagram-heading"><span>框图</span><button v-if="svg" type="button" class="lw-btn sm" @click="enlarged = true">放大查看框图</button></figcaption>
    <p v-if="loading" role="status" class="diagram-message">正在绘制框图…</p>
    <div v-if="svg" class="diagram-svg" role="img" aria-label="Mermaid 框图" v-html="svg"></div>
    <p v-if="error" class="diagram-message" role="status">框图未能绘制：{{ error }}</p>
    <details class="diagram-source" :open="error ? true : undefined"><summary>查看框图源码</summary><pre><code>{{ source }}</code></pre></details>
    <ReadingMediaDialog v-if="enlarged" title="框图大图" :svg="svg" @close="enlarged = false" />
  </figure>
</template>
<style scoped>
.mermaid-diagram { min-width: 0; margin: 20px 0; padding: 16px; border: 1px solid #dce5ed; border-radius: 9px; }
.diagram-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #526b82; font-size: 13px; }
.diagram-svg { overflow: auto; padding: 12px 0; text-align: center; }
.diagram-svg :deep(svg) { max-width: 100%; height: auto; }
.diagram-source { color: #526b82; font-size: 12px; }
.diagram-source summary { cursor: pointer; }
.diagram-source pre { overflow: auto; max-height: 300px; white-space: pre; font-size: 12px; }
.diagram-message { font-size: 13px; overflow-wrap: anywhere; }
</style>

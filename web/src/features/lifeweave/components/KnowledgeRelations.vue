<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { apiError } from '../api/lifeweave'
import { links } from '../api/library'
import type { KnowledgeRelations } from '../api/library'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind; sourceId: string; path: string; version: string }>()
const relations = shallowRef<KnowledgeRelations | null>(null)
const error = shallowRef('')
const loading = shallowRef(false)
let request = 0
watch(() => [props.workspace, props.sourceId, props.path, props.version] as const, async () => {
  const ticket = ++request
  relations.value = null; error.value = ''; loading.value = true
  try {
    const result = await links(props.workspace, props.path, props.sourceId)
    if (ticket !== request) return
    relations.value = result
  } catch (caught) { if (ticket === request) error.value = apiError(caught).message }
  finally { if (ticket === request) loading.value = false }
}, { immediate: true })
function destination(sourceId: string, path: string) {
  return { path: `/lifeweave/${props.workspace}/knowledge`, query: { source: sourceId, path } }
}
</script>

<template>
  <section class="knowledge-relations" aria-label="知识引用关系">
    <div class="relations-heading"><h3>知识之间的引用</h3><span v-if="relations" class="lw-tiny lw-muted">从 {{ relations.scannedDocuments }} 篇当前可读文档生成</span></div>
    <p v-if="loading" class="lw-small lw-sub" role="status">正在整理引用关系…</p>
    <p v-else-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <template v-else-if="relations">
      <div class="relations-grid"><div><h4>本文引用</h4><ul v-if="relations.outgoing.length"><li v-for="entry in relations.outgoing" :key="entry.href + entry.status"><RouterLink v-if="entry.status === 'valid' && entry.path" :to="destination(entry.sourceId, entry.path)">{{ entry.label }}</RouterLink><span v-else>{{ entry.label }} <small>（{{ entry.status === 'missing' ? '目标文件不存在' : '超出知识目录或不可读取' }}）</small></span><span v-if="entry.count > 1" class="lw-tiny lw-muted"> · {{ entry.count }} 次</span></li></ul><p v-else class="lw-small lw-sub">本文没有指向同一来源 Markdown 的链接。</p></div>
      <div><h4>引用本文</h4><ul v-if="relations.backlinks.length"><li v-for="entry in relations.backlinks" :key="entry.sourceId + ':' + entry.path"><RouterLink :to="destination(entry.sourceId, entry.path)">{{ entry.title }}</RouterLink><span v-if="entry.count > 1" class="lw-tiny lw-muted"> · {{ entry.count }} 次</span></li></ul><p v-else class="lw-small lw-sub">当前可读文档中还没有指向本文的链接。</p></div></div>
      <details v-if="relations.unavailableSources.length || relations.unavailableDocuments.length"><summary>有来源未纳入本次引用检查</summary><p v-for="source in relations.unavailableSources" :key="source" class="lw-small lw-sub">来源不可用：{{ source }}</p><p v-for="file in relations.unavailableDocuments" :key="file.path" class="lw-small lw-sub">{{ file.path }}：{{ file.reason }}</p></details>
    </template>
  </section>
</template>

<style scoped>
.knowledge-relations { border-top: 1px solid #e2e8eb; margin-top: 24px; padding-top: 20px; }
.relations-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.relations-heading h3 { margin: 0 0 12px; }
.relations-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.relations-grid h4 { margin: 0 0 8px; font-size: 12px; }
.relations-grid ul { margin: 0; padding-left: 18px; }
.relations-grid li { margin-bottom: 6px; line-height: 1.45; overflow-wrap: anywhere; }
.relations-grid small { color: var(--lw-muted); }
@media (max-width: 680px) { .relations-grid { grid-template-columns: 1fr; } }
</style>

<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { apiError } from '../api/lifeweave'
import { semanticRelations } from '../api/library'
import type { SemanticRelations } from '../api/library'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind; sourceId: string; path: string; version: string }>()
const result = shallowRef<SemanticRelations | null>(null)
const error = shallowRef('')
let generation = 0
watch(() => [props.workspace, props.sourceId, props.path, props.version], async () => {
  const ticket = ++generation
  result.value = null; error.value = ''
  try {
    const data = await semanticRelations(props.workspace, props.path, props.sourceId)
    if (ticket === generation && data.version === props.version) result.value = data
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
}, { immediate: true })
</script>

<template>
  <section v-if="sourceId === 'lifeweave-project'" class="semantic-relations" aria-label="已核对的知识关系">
    <h3>这篇知识由什么实现和验证</h3>
    <p class="lw-small lw-muted">只显示人工登记、带来源版本的关系；普通链接不自动成为实现或验证关系。</p>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
    <ul v-else-if="result?.items.length">
      <li v-for="entry in result.items" :key="entry.relation + entry.targetPath">
        <strong>{{ entry.relation === 'implemented_by' ? '实现' : '验证' }}</strong>：
        <a v-if="entry.targetUrl" :href="entry.targetUrl" target="_blank" rel="noopener noreferrer">{{ entry.targetPath }}</a><span v-else>{{ entry.targetPath }}</span>
        <span class="lw-tiny lw-muted"> · {{ entry.status === 'current' ? (entry.targetUrl ? '本地与 GitHub 版本已核对' : '本地版本已核对；远端链接未确认') : entry.status === 'missing' ? '目标不存在' : '来源或目标已变化，需复核' }}</span>
        <p class="lw-tiny lw-muted">依据：{{ entry.evidenceQuote }}</p>
      </li>
    </ul>
    <p v-else class="lw-small lw-muted">此篇尚无人工登记的语义关系。</p>
  </section>
</template>

<style scoped>
.semantic-relations { border-top: 1px solid var(--lw-line, #dededb); margin-top: 18px; padding-top: 14px; }
.semantic-relations h3 { margin: 0 0 8px; }
.semantic-relations ul { padding-left: 18px; }
.semantic-relations li { margin: 8px 0; overflow-wrap: anywhere; }
.semantic-relations li p { margin: 4px 0; }
</style>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
import type { InputRecommendations } from '../api/continuation'
import MarkdownBody from './MarkdownBody.vue'

const props = defineProps<{ workspace: string; materials: InputRecommendations }>()
const method = ref<{ title: string; content: string; version: string } | null>(null)
const error = ref(''); const loading = ref(false)
let generation = 0
watch(() => [props.workspace, props.materials], () => { generation++; method.value = null; error.value = ''; loading.value = false })
onBeforeUnmount(() => { generation++ })
async function readMethod(id: string) {
  const ticket = ++generation; loading.value = true; error.value = ''
  try {
    const result = await http.get(`/lifeweave/${props.workspace}/methods/${encodeURIComponent(id)}`)
    if (ticket === generation) method.value = result.data
  } catch (e) { if (ticket === generation) error.value = apiError(e).message }
  finally { if (ticket === generation) loading.value = false }
}
</script>

<template>
  <details class="lw-mb-10">
    <summary>推荐材料：{{ materials.methods.length }} 个方法候选、{{ materials.documents.length }} 篇知识</summary>
    <p class="lw-small">{{ materials.boundary }}</p>
    <p v-for="entry in materials.methods" :key="entry.id"><strong>{{ entry.title }}</strong> · {{ entry.reason }} <button class="lw-text-btn" type="button" :disabled="loading" @click="readMethod(entry.id)">阅读方法正文</button></p>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="method" class="lw-note-card"><MarkdownBody :content="method.content" /><p class="lw-tiny lw-muted">当前方法版本 {{ method.version.slice(0, 12) }}；执行时固定实际加载版本。</p></div>
    <p v-for="doc in materials.documents" :key="doc.ref"><RouterLink :to="{ path: `/lifeweave/${workspace}/knowledge`, query: { source: doc.sourceId, path: doc.path } }">{{ doc.title }}</RouterLink> · {{ doc.sourceTitle }} · {{ doc.reason }}</p>
    <p v-if="!materials.methods.length && !materials.documents.length">未找到文本匹配材料。可在设置登记来源，或调整事项的当前目标。</p>
    <p v-for="problem in materials.unavailable" :key="problem.path" role="status">来源缺口：{{ problem.path }} · {{ problem.reason }}</p>
  </details>
</template>

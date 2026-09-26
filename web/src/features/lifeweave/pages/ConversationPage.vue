<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import ConversationWorkspace from '../components/conversation/ConversationWorkspace.vue'
import type { WorkspaceKind } from '../types'
const route = useRoute()
const workspace = computed(() => String(route.params.workspace) as WorkspaceKind)
const conversationId = computed(() => String(route.params.conversationId || ''))
const itemId = computed(() => typeof route.query.itemId === 'string' ? route.query.itemId : '')
const quote = shallowRef<{ text: string; runId: string | null; anchor: string }>()
watch(() => [workspace.value, itemId.value, conversationId.value], () => {
  quote.value = undefined
  try { const key = `lifeweave:quote:${workspace.value}:${itemId.value}`; const saved = sessionStorage.getItem(key); if (saved) quote.value = JSON.parse(saved) } catch { /* Plain discussion still works when browser storage is unavailable. */ }
}, { immediate: true })
function clearQuote() {
  quote.value = undefined
  try { sessionStorage.removeItem(`lifeweave:quote:${workspace.value}:${itemId.value}`) } catch { /* The current form still clears its reference. */ }
}
</script>

<template>
  <PageHeader title="与 AI 对话" subtitle="从眼前的问题开始，接着已有的工作往前走。" />
  <ConversationWorkspace :workspace="workspace" :conversation-id="conversationId" :item-id="itemId" :initial-mode="route.query.mode==='discuss'?'discuss':undefined" :quote="quote" @clear-quote="clearQuote" />
</template>

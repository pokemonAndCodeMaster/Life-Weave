<script setup lang="ts">
import { computed } from 'vue'
import type { ConversationTurn } from '../../api/conversations'
import type { WorkspaceKind } from '../../types'
import MarkdownBody from '../MarkdownBody.vue'
import ConversationRunReceipt from './ConversationRunReceipt.vue'
const props = defineProps<{ turns: ConversationTurn[]; workspace: WorkspaceKind; sending: boolean }>()
defineEmits<{ cancel: [id: string]; retry: [turn: ConversationTurn] }>()
const statusLabels = { queued: '已保存 · 等待处理', processing: '正在处理', completed: '已回复', failed: '处理失败', cancelled: '已取消' }
function receiptPath(receipt: ConversationTurn['receipts'][number], turn: ConversationTurn) {
  const itemId = receipt.itemId || turn.itemId || (receipt.kind === 'item' ? receipt.id : '')
  if (!itemId) return ''
  const tab = receipt.kind === 'context' ? 'context' : receipt.kind === 'knowledge' ? 'outputs' : 'overview'
  return `/lifeweave/${props.workspace}/items/${encodeURIComponent(itemId)}/${tab}`
}
const rows = computed(() => props.turns.map(turn => ({ ...turn, runIds: [...new Set([turn.runId, ...turn.receipts.map(receipt => receipt.runId || (receipt.kind === 'run' ? receipt.id : null))].filter((id): id is string => !!id))] })))
</script>

<template>
  <div class="turn-list" aria-label="对话记录">
    <article v-for="turn in rows" :key="turn.id" class="turn">
      <div class="user-message"><span class="speaker">我</span><p>{{ turn.body }}</p></div>
      <div class="assistant-message">
        <div class="lw-between"><span class="speaker">经纬</span><span class="lw-tiny lw-muted" role="status">{{ statusLabels[turn.status] }}</span></div>
        <MarkdownBody v-if="turn.reply" :content="turn.reply" />
        <p v-else-if="turn.status === 'queued' || turn.status === 'processing'" class="lw-small lw-muted">请求已保存，可以离开后再回来查看。</p>
        <p v-if="turn.error" role="alert">{{ turn.error }}</p>
        <div v-if="turn.receipts.length" class="receipt-links"><template v-for="receipt in turn.receipts" :key="`${receipt.kind}:${receipt.id}`"><RouterLink v-if="receiptPath(receipt, turn)" class="lw-text-btn" :to="receiptPath(receipt, turn)">{{ receipt.title }}{{ ['context', 'knowledge'].includes(receipt.kind) ? ' · 前往审阅候选' : '' }}</RouterLink><span v-else-if="receipt.kind !== 'run'" class="lw-small">{{ receipt.title }}</span></template></div>
        <ConversationRunReceipt v-for="id in turn.runIds" :key="id" :workspace="workspace" :run-id="id" :item-id="turn.itemId" />
        <details v-if="turn.sources?.length" class="sources"><summary>本次参考来源（{{ turn.sources.length }}）</summary><ul><li v-for="(source, index) in turn.sources" :key="index">{{ source.title || source.path || source.ref || '已记录来源' }}<span v-if="source.path && source.title"> · {{ source.path }}</span></li></ul></details>
        <button v-if="turn.status === 'queued' || turn.status === 'processing'" class="lw-btn ghost sm" type="button" @click="$emit('cancel', turn.id)">取消本次处理</button>
        <button v-if="turn.status === 'failed'" class="lw-btn ghost sm" type="button" :disabled="sending" @click="$emit('retry', turn)">将原文带回输入框</button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.turn-list { min-width: 0; }
.turn { margin-bottom: 30px; }
.speaker { font-size: 12px; font-weight: 650; color: #687069; }
.user-message { margin: 0 0 18px 8%; padding: 14px 18px; background: #f0f2ed; border-radius: 12px 12px 2px 12px; }
.user-message p { margin: 6px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.assistant-message { padding: 0 4px; min-width: 0; }
.receipt-links { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
.sources { font-size: 12px; color: #657066; margin: 14px 0; overflow-wrap: anywhere; }
</style>

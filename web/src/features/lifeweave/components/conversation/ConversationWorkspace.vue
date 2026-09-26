<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useConversation } from '../../composables/useConversation'
import type { ConversationInputContext, ConversationMode, ConversationTurn } from '../../api/conversations'
import type { WorkspaceKind } from '../../types'
import ConversationComposer from './ConversationComposer.vue'
import ConversationTurnList from './ConversationTurnList.vue'
import ResearchContextPicker from './ResearchContextPicker.vue'
import PersonalModelEditor from '../PersonalModelEditor.vue'
const props = defineProps<{ workspace: WorkspaceKind; conversationId: string; itemId: string; initialMode?: ConversationMode; quote?: { text: string; runId: string | null; anchor: string } }>()
const emit = defineEmits<{ clearQuote: [] }>()
const router = useRouter()
function select(id: string) {
  try {
    const key=`lifeweave:draft:${props.workspace}:${id}`
    localStorage.setItem(`${key}:research`,JSON.stringify(researchItemIds.value))
    localStorage.setItem(`${key}:mode`,mode.value)
  } catch { /* The submitted sources remain recorded on the server. */ }
  void router.replace({ path: `/lifeweave/${props.workspace}/conversation/${encodeURIComponent(id)}`, query: props.itemId ? { itemId: props.itemId } : {} })
}
const { current, history, error, loading, sending, pending, busy, refresh, submit, cancel } = useConversation({ workspace: () => props.workspace, conversationId: () => props.conversationId, itemId: () => props.itemId, selected: select })
const researchItemIds = shallowRef<string[]>([])
const body = shallowRef(''); const mode = shallowRef<ConversationMode>('auto')
const repositoryPath = shallowRef(''); const acknowledgeExcludedChanges = shallowRef(false)
const retryContext = shallowRef<ConversationInputContext | null>(null)
const scopeItemId = computed(() => current.value?.itemId || props.itemId)
const draftKey = computed(() => `lifeweave:draft:${props.workspace}:${props.conversationId || props.itemId || 'new'}`)
watch(() => [draftKey.value, props.initialMode], () => {
  retryContext.value = null; mode.value = props.initialMode || 'auto'; researchItemIds.value = []; repositoryPath.value = ''; acknowledgeExcludedChanges.value = false
  try {
    body.value = localStorage.getItem(draftKey.value) || ''
    researchItemIds.value = JSON.parse(localStorage.getItem(`${draftKey.value}:research`) || '[]')
    repositoryPath.value = localStorage.getItem(`${draftKey.value}:repository`) || ''
    const context = localStorage.getItem(`${draftKey.value}:context`); if (context) retryContext.value = JSON.parse(context)
    const savedMode = localStorage.getItem(`${draftKey.value}:mode`)
    if (!props.initialMode && savedMode && ['auto', 'record', 'discuss', 'execute'].includes(savedMode)) mode.value = savedMode as ConversationMode
  }
  catch { body.value = '' }
}, { immediate: true })
watch(researchItemIds, value => { try { localStorage.setItem(`${draftKey.value}:research`,JSON.stringify(value)) } catch { /* Keep current selection in memory. */ } })
watch(repositoryPath, value => { try { localStorage.setItem(`${draftKey.value}:repository`, value) } catch { /* Keep it in the form. */ } })
watch(mode, value => { try { localStorage.setItem(`${draftKey.value}:mode`, value) } catch { /* Mode remains in this form. */ } })
watch(retryContext, value => { try { if (value) localStorage.setItem(`${draftKey.value}:context`, JSON.stringify(value)); else localStorage.removeItem(`${draftKey.value}:context`) } catch { /* Context remains in this form when browser storage is unavailable. */ } })
watch(body, value => { try { if (value) localStorage.setItem(draftKey.value, value); else localStorage.removeItem(draftKey.value) } catch { /* Draft remains editable without browser storage. */ } })
watch(pending, value => { if (value) { body.value = value.input.body; mode.value = value.input.mode; researchItemIds.value = value.input.researchItemIds || []; repositoryPath.value = value.input.repositoryPath || ''; acknowledgeExcludedChanges.value = !!value.input.acknowledgeExcludedChanges } }, { immediate: true })
watch(() => props.quote, quote => { if (quote && !pending.value) { body.value = quote.text; retryContext.value = null } }, { immediate: true })
async function send() {
  if (!body.value.trim()) return
  const oldDraftKey = draftKey.value; const workspace = props.workspace
  const inputContext = retryContext.value ?? { itemId: scopeItemId.value || undefined, runId: props.quote?.runId || undefined, anchor: props.quote?.anchor?.slice(0, 2000) }
  const accepted = await submit({ body: body.value, mode: mode.value, ...inputContext, researchItemIds: researchItemIds.value, repositoryPath: repositoryPath.value.trim() || null, acknowledgeExcludedChanges: acknowledgeExcludedChanges.value })
  if (accepted && workspace === props.workspace) { body.value = ''; retryContext.value = null; emit('clearQuote'); try { localStorage.removeItem(oldDraftKey); localStorage.removeItem(`${oldDraftKey}:context`) } catch { /* Saved server history is authoritative. */ } }
}
function retry(turn: ConversationTurn) {
  if (!pending.value && !sending.value) {
    body.value = turn.body; mode.value = turn.mode; researchItemIds.value = turn.inputContext?.researchItemIds || []
    repositoryPath.value = turn.inputContext?.repositoryPath || ''; acknowledgeExcludedChanges.value = !!turn.inputContext?.acknowledgeExcludedChanges
    retryContext.value = turn.inputContext ? { ...turn.inputContext } : { itemId: turn.itemId, runId: turn.runId, anchor: null }
  }
}
function clearQuote() {
  if (retryContext.value) retryContext.value = { ...retryContext.value, runId: null, anchor: null }
  emit('clearQuote')
}
</script>

<template>
  <div class="conversation-layout">
    <aside class="conversation-history" aria-label="历史对话">
      <RouterLink class="lw-btn" :to="{ path: `/lifeweave/${workspace}/conversation`, query: itemId ? { itemId } : {} }">开始新对话</RouterLink>
      <h2 class="lw-small-heading">{{ itemId ? '本事项的对话' : '最近对话' }}</h2>
      <p v-if="!history.length && !loading" class="lw-small lw-muted">发送第一条消息后，对话会保存在这里。</p>
      <nav class="history-list"><RouterLink v-for="entry in history" :key="entry.id" class="history-entry" :class="{ selected: current?.id === entry.id }" :to="{ path: `/lifeweave/${workspace}/conversation/${encodeURIComponent(entry.id)}`, query: itemId ? { itemId } : {} }"><strong>{{ entry.title || '未命名对话' }}</strong><span>{{ new Date(entry.updatedAt).toLocaleDateString('zh-CN') }}{{ entry.itemId ? ' · 已关联事项' : '' }}</span></RouterLink></nav>
      <PersonalModelEditor :workspace="workspace" />
    </aside>
    <section class="lw-panel conversation-main" aria-label="当前对话">
      <div class="conversation-heading"><div><h2>{{ current?.title || '从一句话开始' }}</h2><RouterLink v-if="scopeItemId" class="lw-text-btn lw-small" :to="`/lifeweave/${workspace}/items/${encodeURIComponent(scopeItemId)}/overview`">查看关联事项 {{ scopeItemId }}</RouterLink><p v-else class="lw-small lw-muted">问题、想法和委托，都可以在这里接着聊。</p></div><button class="lw-btn ghost sm" type="button" :disabled="loading" @click="refresh">刷新</button></div>
      <p v-if="loading" role="status">正在读取保存的对话…</p><p v-if="error" class="conversation-error" role="alert">{{ error }}</p>
      <ConversationTurnList v-if="current?.turns.length" :turns="current.turns" :workspace="workspace" :sending="sending || !!pending" @cancel="cancel" @retry="retry" />
      <div v-else-if="!loading" class="conversation-empty"><h3>把背景和想做的事告诉我</h3><p>“先帮我理解这篇论文的问题和动机。”<br />“只记一下这个想法，暂时不用展开。”<br />“请继续修订这份报告，补上训练数据的来源。”</p></div>
      <p v-if="busy" class="lw-small lw-muted" role="status">正在处理已保存的消息，运行状态会自动更新。</p>
      <ResearchContextPicker v-model="researchItemIds" :workspace="workspace" :item-id="scopeItemId||undefined" :disabled="sending||!!pending||busy" />
      <ConversationComposer v-model="body" v-model:mode="mode" v-model:repository-path="repositoryPath" v-model:acknowledge-excluded-changes="acknowledgeExcludedChanges" :sending="sending" :uncertain="!!pending" :processing="busy" :disabled="loading || (!!conversationId && !current)" :anchor="(pending?.input.anchor ?? (retryContext ? retryContext.anchor : quote?.anchor)) || undefined" @send="send" @clear-quote="clearQuote" />
    </section>
  </div>
</template>

<style scoped>
.conversation-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 24px; align-items: start; }
.conversation-history { min-width: 0; }
.conversation-history h2 { margin-top: 24px; }
.history-list { display: grid; gap: 4px; max-height: 400px; overflow-y: auto; }
.history-entry { display: grid; padding: 10px 12px; border-radius: 7px; color: inherit; text-decoration: none; gap: 5px; }
.history-entry strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 500; }
.history-entry span { font-size: 11px; color: #767d74; }
.history-entry:hover, .history-entry.selected { background: #eaf0e7; }
.conversation-main { padding: 24px; min-width: 0; }
.conversation-heading { display: flex; justify-content: space-between; gap: 16px; align-items: start; border-bottom: 1px solid #e7e8e3; padding-bottom: 18px; margin-bottom: 24px; }
.conversation-heading h2 { margin: 0 0 8px; overflow-wrap: anywhere; }
.conversation-empty { color: #747c72; padding: 18px 0 30px; line-height: 1.9; }
.conversation-empty h3 { color: #344433; font-weight: 500; }
.conversation-error { color: #923d34; padding: 12px; background: #fff4ee; border-radius: 6px; }
@media (max-width: 900px) { .conversation-layout { grid-template-columns: minmax(0, 1fr); gap: 18px; }.history-list { max-height: 135px; }.conversation-history { display: grid; grid-template-columns: 1fr; }.conversation-main { padding: 18px; } }
</style>

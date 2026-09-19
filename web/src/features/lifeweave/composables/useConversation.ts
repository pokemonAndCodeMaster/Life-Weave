import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError } from '../api/lifeweave'
import { cancelConversationTurn, createConversation, getConversation, listConversations, sendConversationTurn } from '../api/conversations'
import type { Conversation, ConversationSummary, TurnInput } from '../api/conversations'
import type { WorkspaceKind } from '../types'

interface Pending { creationId: string; conversationId?: string; input: TurnInput }
export function useConversation(options: { workspace: () => WorkspaceKind; conversationId: () => string; itemId: () => string; selected: (id: string) => void }) {
  const current = shallowRef<Conversation | null>(null)
  const history = shallowRef<ConversationSummary[]>([])
  const error = shallowRef(''); const loading = shallowRef(false); const sending = shallowRef(false)
  const pending = shallowRef<Pending | null>(null)
  let generation = 0; let timer: ReturnType<typeof setTimeout> | undefined
  const storageKey = () => `lifeweave:pending:${options.workspace()}:${options.conversationId() || options.itemId() || 'new'}`
  function persist(value: Pending | null, key = storageKey()) {
    try { if (value) localStorage.setItem(key, JSON.stringify(value)); else localStorage.removeItem(key) } catch { /* Request identity still lives in memory when storage is unavailable. */ }
  }
  const busy = computed(() => current.value?.turns.some(turn => ['queued', 'processing'].includes(turn.status)) ?? false)
  async function refresh() {
    const ticket = generation; const workspace = options.workspace(); const id = current.value?.id || options.conversationId()
    clearTimeout(timer)
    try {
      const [rows, detail] = await Promise.all([listConversations(workspace, options.itemId() || undefined), id ? getConversation(workspace, id) : Promise.resolve(null)])
      if (ticket !== generation) return
      history.value = rows.items; if (detail) current.value = detail
      error.value = ''
    } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
    finally { if (ticket === generation) { loading.value = false; timer = setTimeout(() => void refresh(), 4000) } }
  }
  async function submit(input: Omit<TurnInput, 'requestId'>): Promise<boolean> {
    if (sending.value) return false
    const ticket = generation; const workspace = options.workspace(); const key = storageKey()
    if (!pending.value) pending.value = { creationId: crypto.randomUUID(), conversationId: current.value?.id, input: { ...input, requestId: crypto.randomUUID() } }
    const request = pending.value
    persist(request, key); sending.value = true; error.value = ''
    try {
      if (!request.conversationId) {
        const conversation = await createConversation(workspace, { requestId: request.creationId, title: request.input.body.slice(0, 80), itemId: request.input.itemId })
        request.conversationId = conversation.id
        persist(request, key)
        if (ticket !== generation) return false
        current.value = { ...conversation, turns: [] }
      }
      const turn = await sendConversationTurn(workspace, request.conversationId, request.input)
      persist(null, key)
      if (ticket !== generation) return false
      pending.value = null
      if (current.value) current.value = { ...current.value, turns: [...current.value.turns.filter(row => row.id !== turn.id), turn] }
      options.selected(request.conversationId)
      void refresh()
      return true
    } catch (caught) {
      if (ticket === generation) {
        const problem = apiError(caught)
        if (problem.status >= 400 && problem.status < 500 && ![408, 409, 429].includes(problem.status)) { pending.value = null; persist(null, key) }
        error.value = problem.message
      }
      return false
    } finally { if (ticket === generation) sending.value = false }
  }
  async function cancel(turnId: string) {
    if (!current.value) return
    const ticket = generation
    try { await cancelConversationTurn(options.workspace(), current.value.id, turnId); if (ticket === generation) await refresh() }
    catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  }
  watch(() => [options.workspace(), options.conversationId(), options.itemId()], (next, previous) => {
    if (previous && next[0] === previous[0] && next[2] === previous[2] && next[1] && next[1] === current.value?.id) return
    generation++; clearTimeout(timer); current.value = null; history.value = []; sending.value = false; pending.value = null; error.value = ''; loading.value = true
    try { const saved = localStorage.getItem(storageKey()); if (saved) pending.value = JSON.parse(saved) as Pending } catch { /* An unreadable local draft does not prevent reading saved conversations. */ }
    if (pending.value?.conversationId) current.value = { id: pending.value.conversationId, title: '', itemId: options.itemId() || null, createdAt: '', updatedAt: '', turns: [] }
    void refresh()
  }, { immediate: true })
  onBeforeUnmount(() => { generation++; clearTimeout(timer) })
  return { current, history, error, loading, sending, pending, busy, refresh, submit, cancel }
}

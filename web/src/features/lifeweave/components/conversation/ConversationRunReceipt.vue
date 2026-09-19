<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiError, getRun, runAction } from '../../api/lifeweave'
import type { LifeWeaveRun, WorkspaceKind } from '../../types'
import ResearchOutputPanel from '../ResearchOutputPanel.vue'
const props = defineProps<{ workspace: WorkspaceKind; runId: string; itemId?: string | null }>()
const router = useRouter()
const outputRefresh = shallowRef(0)
function quoteForConversation(quote: { text: string; runId: string | null; anchor: string }) {
  const itemId = run.value?.itemId || props.itemId
  if (!itemId) return
  try { sessionStorage.setItem(`lifeweave:quote:${props.workspace}:${itemId}`, JSON.stringify(quote)) }
  catch { error.value = '浏览器未能保存引用，请复制段落后打开事项继续对话。'; return }
  void router.push({ path: `/lifeweave/${props.workspace}/conversation`, query: { itemId } })
}
const run = shallowRef<LifeWeaveRun | null>(null); const error = shallowRef(''); const cancelling = shallowRef(false)
const activeStates = ['queued', 'claimed', 'running', 'pause_requested', 'cancelling']
const active = computed(() => !!run.value && activeStates.includes(run.value.state))
const labels: Record<string, string> = { queued: '排队中', claimed: '准备执行', running: '执行中', pause_requested: '正在暂停', cancelling: '正在取消', cancelled: '已取消', completed: '执行结束 · 待审阅', succeeded: '执行结束 · 待审阅', failed: '执行失败', paused: '已暂停', interrupted: '执行中断' }
const stateLabel = computed(() => run.value ? labels[run.value.state] ?? run.value.state : '正在读取运行状态')
let generation = 0; let timer: ReturnType<typeof setTimeout> | undefined
async function refresh() {
  const ticket = generation; clearTimeout(timer)
  try {
    const result = await getRun(props.workspace, props.runId)
    if (ticket !== generation) return
    run.value = result; error.value = ''
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) timer = setTimeout(() => void refresh(), !run.value || active.value || error.value ? 3500 : 15000) }
}
async function cancel() {
  const ticket = generation; cancelling.value = true
  try { await runAction(props.workspace, props.runId, 'cancel'); if (ticket === generation) await refresh() }
  catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) cancelling.value = false }
}
watch(() => [props.workspace, props.runId], () => { generation++; clearTimeout(timer); run.value = null; error.value = ''; cancelling.value = false; void refresh() }, { immediate: true })
onBeforeUnmount(() => { generation++; clearTimeout(timer) })
</script>

<template>
  <section class="run-receipt" aria-label="实际执行回执">
    <div class="lw-between"><strong>{{ stateLabel }}</strong><button v-if="active" class="lw-btn ghost sm" type="button" :disabled="cancelling || run?.state === 'cancelling'" @click="cancel">{{ cancelling ? '正在取消…' : '取消运行' }}</button></div>
    <p class="lw-tiny lw-muted">运行 {{ runId }}</p>
    <p v-if="run?.error" role="alert">{{ run.error }}</p><p v-if="error" role="alert">{{ error }}</p>
    <div v-if="run && !active && (run.itemId || itemId)" class="receipt-output"><p class="lw-small lw-muted">以下展示该事项的当前成果，可能包含后续运行的修订。可用成果版本选择查看历史版本。</p><ResearchOutputPanel :workspace="workspace" :item-id="run.itemId || itemId || ''" :refresh-key="outputRefresh" @quote="quoteForConversation" @feedback-saved="outputRefresh++" @candidate-created="router.push(`/lifeweave/${workspace}/items/${encodeURIComponent(run.itemId || itemId || '')}/outputs`)" /></div>
    <RouterLink v-if="run?.itemId || itemId" class="lw-text-btn" :to="`/lifeweave/${workspace}/items/${encodeURIComponent(run?.itemId || itemId || '')}/outputs`">打开当前成果与反馈</RouterLink>
  </section>
</template>

<style scoped>
.run-receipt { padding: 14px; margin-top: 14px; background: #f5f6f2; border: 1px solid #dce2d8; border-radius: 8px; }
.receipt-output { margin: 12px 0; }
</style>

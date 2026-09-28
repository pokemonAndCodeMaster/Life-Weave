import { onBeforeUnmount, readonly, shallowRef, watch, type Ref } from 'vue'
import { getAgentExecution, type ExecutionDetail, type ExecutionKind } from '../api/agents'
import { apiError } from '../api/lifeweave'
import type { WorkspaceKind } from '../types'

const active = new Set(['queued', 'claimed', 'running', 'planning', 'reviewing', 'implementing', 'pause_requested', 'cancelling', 'pending'])
export function useExecutionDetail(workspace: Readonly<Ref<WorkspaceKind>>, kind: Readonly<Ref<ExecutionKind>>, id: Readonly<Ref<string>>) {
  const detail = shallowRef<ExecutionDetail | null>(null)
  const loading = shallowRef(false)
  const error = shallowRef('')
  let generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  async function refresh(ticket = generation) {
    if (!id.value) return
    const scope = workspace.value, executionKind = kind.value, executionId = id.value
    loading.value = !detail.value
    clearTimeout(timer)
    try {
      const result = await getAgentExecution(scope, executionKind, executionId)
      if (disposed || ticket !== generation || scope !== workspace.value || executionKind !== kind.value || executionId !== id.value) return
      detail.value = result
      error.value = ''
      if (active.has(result.execution.status.toLowerCase())) timer = setTimeout(() => void refresh(ticket), 3000)
    } catch (caught) {
      if (disposed || ticket !== generation) return
      error.value = apiError(caught).message
      // A failed request remains visible and retryable; polling must not turn it into a success state.
    } finally { if (!disposed && ticket === generation) loading.value = false }
  }
  watch([workspace, kind, id], () => {
    generation += 1
    clearTimeout(timer)
    detail.value = null; error.value = ''
    void refresh(generation)
  }, { immediate: true })
  onBeforeUnmount(() => { disposed = true; generation += 1; clearTimeout(timer) })
  return { detail: readonly(detail), loading: readonly(loading), error: readonly(error), refresh }
}

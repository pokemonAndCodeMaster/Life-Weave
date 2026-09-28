import { onBeforeUnmount, readonly, shallowRef, watch, type Ref } from 'vue'
import { apiError } from '../api/lifeweave'
import { getWorkView, saveWorkPlan, type ItemWorkView, type WorkPlanInput } from '../api/workView'
import type { WorkspaceKind } from '../types'

export function useItemWorkView(workspace: Readonly<Ref<WorkspaceKind>>, itemId: Readonly<Ref<string>>) {
  const view = shallowRef<ItemWorkView | null>(null)
  const loading = shallowRef(false)
  const saving = shallowRef(false)
  const error = shallowRef('')
  const conflict = shallowRef(false)
  let generation = 0
  let loadEpoch = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false

  async function refresh(ticket = generation): Promise<boolean> {
    if (saving.value) return false
    const scope = workspace.value
    const id = itemId.value
    if (!id) return false
    const epoch = ++loadEpoch
    loading.value = !view.value
    try {
      const result = await getWorkView(scope, id)
      if (disposed || ticket !== generation || epoch !== loadEpoch || scope !== workspace.value || id !== itemId.value) return false
      view.value = result
      if (!conflict.value) error.value = ''
      return true
    } catch (caught) {
      if (!disposed && ticket === generation && epoch === loadEpoch && !conflict.value) error.value = apiError(caught).message
      return false
    } finally {
      if (!disposed && ticket === generation && epoch === loadEpoch) {
        loading.value = false
        clearTimeout(timer)
        timer = setTimeout(() => void refresh(ticket), 12000)
      }
    }
  }

  async function save(input: WorkPlanInput): Promise<boolean> {
    if (!view.value || saving.value) return false
    if (input.version !== view.value.itemVersion) {
      conflict.value = true
      error.value = '事项已有新版本，本次步骤未保存。请刷新并核对新版本后重新编辑。'
      return false
    }
    const scope = workspace.value
    const id = itemId.value
    const ticket = generation
    saving.value = true
    // A GET started before this write must not overwrite the returned version.
    ++loadEpoch
    clearTimeout(timer)
    error.value = ''
    conflict.value = false
    try {
      const result = await saveWorkPlan(scope, id, input)
      if (disposed || ticket !== generation || scope !== workspace.value || id !== itemId.value) return false
      view.value = result
      return true
    } catch (caught) {
      if (!disposed && ticket === generation) {
        const parsed = apiError(caught)
        conflict.value = parsed.status === 409
        error.value = conflict.value ? '事项已更新，本次步骤未保存。请刷新并核对新版本后重新编辑。' : parsed.message
      }
      return false
    } finally {
      if (!disposed && ticket === generation) {
        saving.value = false
        clearTimeout(timer)
        timer = setTimeout(() => void refresh(ticket), 12000)
      }
    }
  }

  function acceptSnapshot(result: ItemWorkView) {
    // A previous GET must not restore the version from before an overview edit.
    ++loadEpoch
    clearTimeout(timer)
    view.value = result
    error.value = ''
    conflict.value = false
    timer = setTimeout(() => void refresh(generation), 12000)
  }

  watch([workspace, itemId], () => {
    generation += 1
    loadEpoch += 1
    clearTimeout(timer)
    view.value = null
    error.value = ''
    conflict.value = false
    saving.value = false
    void refresh(generation)
  }, { immediate: true })
  onBeforeUnmount(() => { disposed = true; generation += 1; clearTimeout(timer) })
  // The fetched view is replaced as a whole; the route owns it and only sends
  // immutable snapshots to its children.
  return { view, loading: readonly(loading), saving: readonly(saving), error: readonly(error), conflict: readonly(conflict), refresh, save, acceptSnapshot }
}

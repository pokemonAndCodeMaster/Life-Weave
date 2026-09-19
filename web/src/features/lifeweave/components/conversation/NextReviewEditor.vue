<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { apiError, mutateWorkspace } from '../../api/lifeweave'
import type { WorkItem, WorkspaceKind } from '../../types'
const props = defineProps<{ workspace: WorkspaceKind; item: WorkItem }>()
const emit = defineEmits<{ saved: [] }>()
const nextReview = shallowRef(''); const saving = shallowRef(false); const error = shallowRef(''); const saved = shallowRef(false)
watch(() => [props.workspace, props.item.id, props.item.version], () => {
  const value = props.item.payload.nextReviewAt
  if (typeof value === 'string' && value) { const date = new Date(value); nextReview.value = Number.isNaN(date.getTime()) ? '' : new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16) } else nextReview.value = ''
  error.value = ''; saved.value = false
}, { immediate: true })
async function save() {
  if (saving.value) return
  const workspace = props.workspace; const id = props.item.id; saving.value = true; error.value = ''; saved.value = false
  try {
    await mutateWorkspace(workspace, `/items/${encodeURIComponent(id)}`, 'patch', { version: props.item.version, payload: { ...props.item.payload, nextReviewAt: nextReview.value ? new Date(nextReview.value).toISOString() : null } })
    if (workspace === props.workspace && id === props.item.id) { saved.value = true; emit('saved') }
  } catch (caught) { if (workspace === props.workspace && id === props.item.id) error.value = apiError(caught).message }
  finally { if (workspace === props.workspace && id === props.item.id) saving.value = false }
}
</script>
<template>
  <section class="lw-panel pad"><h2>下次讨论 / 审阅</h2><form @submit.prevent="save"><label class="lw-label">本地时间<input v-model="nextReview" type="datetime-local" class="lw-field" :disabled="saving" /></label><p class="lw-tiny lw-muted">记录你指定的时间，暂不发送提醒或占用日历。</p><button class="lw-btn sm" type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存安排' }}</button><p v-if="error" role="alert">{{ error }}</p><p v-if="saved" role="status">安排已保存。</p></form></section>
</template>

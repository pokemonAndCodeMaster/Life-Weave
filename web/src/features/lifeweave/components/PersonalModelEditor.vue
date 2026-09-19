<script setup lang="ts">
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { getPersonalModel, savePersonalModel } from '../api/conversations'
import { apiError } from '../api/lifeweave'
import type { WorkspaceKind } from '../types'
const props = defineProps<{ workspace: WorkspaceKind }>()
const goals = shallowRef(''); const preferences = shallowRef(''); const version = shallowRef<number | null>(null)
const loading = shallowRef(false); const saving = shallowRef(false); const error = shallowRef(''); const saved = shallowRef(false)
let generation = 0
async function load() {
  const ticket = ++generation; loading.value = true; error.value = ''
  try { const model = await getPersonalModel(props.workspace); if (ticket !== generation) return; goals.value = model.goals; preferences.value = model.preferences; version.value = model.version }
  catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) loading.value = false }
}
async function save() {
  if (version.value === null || saving.value) return
  const ticket = generation; saving.value = true; error.value = ''; saved.value = false
  try { const model = await savePersonalModel(props.workspace, { version: version.value, goals: goals.value, preferences: preferences.value }); if (ticket !== generation) return; version.value = model.version; saved.value = true }
  catch (caught) { if (ticket === generation) error.value = apiError(caught).status === 409 ? '当前方向或偏好已有更新。你的输入仍保留；请复制后重新读取，合并后再保存。' : apiError(caught).message }
  finally { if (ticket === generation) saving.value = false }
}
watch(() => props.workspace, () => { goals.value = ''; preferences.value = ''; version.value = null; saved.value = false; saving.value = false; void load() }, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>

<template>
  <details class="lw-panel personal-model"><summary>当前方向与明确偏好</summary>
    <p class="lw-small lw-muted">这里保存你亲自确认的要求，在本空间的后续研究中读取。单次对话中的临时要求仍留在当次对话。</p>
    <p v-if="loading" role="status">正在读取…</p><p v-if="error" role="alert">{{ error }}</p>
    <form @submit.prevent="save">
      <label class="lw-label">当前方向<textarea v-model="goals" class="lw-field" rows="3" maxlength="8000" placeholder="现在最想推进或理解什么？" :disabled="loading || saving || version === null"></textarea></label>
      <label class="lw-label">明确偏好<textarea v-model="preferences" class="lw-field" rows="3" maxlength="8000" placeholder="例如：先解释问题和动机，再展开公式，并明确来源与推断。" :disabled="loading || saving || version === null"></textarea></label>
      <div class="lw-between"><button class="lw-btn primary sm" type="submit" :disabled="loading || saving || version === null">{{ saving ? '正在保存…' : '确认并保存' }}</button><button class="lw-btn ghost sm" type="button" :disabled="loading || saving" @click="load">重新读取</button></div>
      <p v-if="saved" class="lw-small" role="status">已保存，后续研究会读取本空间当前方向与偏好。</p>
    </form>
  </details>
</template>

<style scoped>
.personal-model { padding: 16px; margin-top: 16px; }
.personal-model summary { cursor: pointer; font-weight: 600; }
.personal-model textarea { resize: vertical; }
</style>

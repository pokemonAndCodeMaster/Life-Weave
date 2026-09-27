<script setup lang="ts">
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError } from '../api/lifeweave'
import { checkDevelopmentIntegration, decideDevelopmentDelivery, downloadDevelopmentDelivery } from '../api/development'
import type { DevelopmentDelivery } from '../api/development'
import type { WorkspaceKind } from '../types'

const props = defineProps<{ workspace: WorkspaceKind; delivery: DevelopmentDelivery }>()
const emit = defineEmits<{ updated: [] }>()
const commit = shallowRef('')
const scope = shallowRef<'patch' | 'integrated'>('patch')
const reason = shallowRef('')
const requestId = shallowRef(crypto.randomUUID())
const busy = shallowRef(false)
const error = shallowRef('')
const copyFields = [
  { key: 'baseRevision', label: 'Git 基线提交', action: '复制完整基线' },
  { key: 'artifactSha256', label: '交付 ZIP SHA-256', action: '复制 ZIP 哈希' },
] as const
const copying = shallowRef<(typeof copyFields)[number]['key'] | null>(null)
const copyMessage = shallowRef('')
let copyRequest = 0

function invalidateCopy() {
  copyRequest += 1
  copyMessage.value = ''
  // A clipboard write already accepted by the browser cannot be cancelled.
  // Keep both buttons disabled until it settles, even across delivery changes.
}
watch([() => props.workspace, () => props.delivery.id, () => props.delivery.assignmentId,
  () => props.delivery.implementationRunId, () => props.delivery.baseRevision, () => props.delivery.artifactSha256],
invalidateCopy, { flush: 'sync' })
onBeforeUnmount(invalidateCopy)

async function copyVersion(field: (typeof copyFields)[number]) {
  if (copying.value) return
  const request = ++copyRequest
  const value = props.delivery[field.key]
  copying.value = field.key
  copyMessage.value = `正在复制${field.label}…`
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
    await navigator.clipboard.writeText(value)
    if (request === copyRequest) copyMessage.value = `已复制${field.label}`
  } catch {
    if (request === copyRequest) copyMessage.value = `${field.label}：无法自动复制，请选中完整值手动复制`
  } finally {
    copying.value = null
  }
}

async function download() {
  busy.value = true; error.value = ''
  try {
    const data = await downloadDevelopmentDelivery(props.workspace, props.delivery.assignmentId)
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url; link.download = `lifeweave-${props.delivery.assignmentId}.zip`
    document.body.append(link); link.click(); link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
async function checkCommit() {
  if (!commit.value.trim()) return
  busy.value = true; error.value = ''
  try { await checkDevelopmentIntegration(props.workspace, props.delivery.assignmentId, commit.value.trim()); emit('updated') }
  catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
async function decide(decision: 'accepted' | 'rejected') {
  if (decision === 'rejected' && !reason.value.trim()) { error.value = '请说明需要修改的原因'; return }
  busy.value = true; error.value = ''
  try {
    await decideDevelopmentDelivery(props.workspace, props.delivery.assignmentId, {
      requestId: requestId.value, artifactSha256: props.delivery.artifactSha256,
      decision, scope: scope.value, reason: reason.value.trim(),
    })
    requestId.value = crypto.randomUUID(); emit('updated')
  } catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="delivery" aria-label="固定代码交付">
    <strong>固定代码交付</strong>
    <dl class="delivery-versions">
      <div v-for="field in copyFields" :key="field.key" class="delivery-version">
        <dt class="lw-small">{{ field.label }}</dt>
        <dd><code class="lw-mono">{{ delivery[field.key] }}</code><button class="lw-btn ghost sm" type="button" :disabled="copying !== null" @click="copyVersion(field)">{{ field.action }}</button></dd>
      </div>
    </dl>
    <p class="copy-feedback lw-small" role="status" aria-live="polite" aria-atomic="true">{{ copyMessage }}</p>
    <p class="lw-small">{{ delivery.manifest.files.length }} 个文件。下载包含完整二进制补丁、文件清单和实施报告；页面实时差异仅供预览。</p>
    <button class="lw-btn ghost sm" type="button" :disabled="busy" @click="download">下载完整交付 ZIP</button>
    <details><summary>交付核验范围</summary><p class="lw-tiny lw-muted">文件路径、变更状态与单文件差异请在上方固定产物目录按需查看。服务已核对：差异格式、原基线补丁回放与文件树一致、采集期间工作树稳定。测试和页面结果仍需按实施 Run 的原始证据复核。</p><p class="lw-tiny lw-muted">{{ delivery.manifest.verificationBoundary }}</p><p v-if="delivery.manifest.excludedGenerated.length" class="lw-tiny lw-muted">已排除生成文件：{{ delivery.manifest.excludedGenerated.length }} 个生成文件。</p></details>
    <p v-if="delivery.integrationCommit" class="lw-small">目标提交 {{ delivery.integrationCommit.slice(0, 12) }} 的交付文件已核对{{ delivery.integrationCurrentHead ? '，核对时也是目标仓 HEAD' : '；核对时不是目标仓 HEAD' }}。这不代表远端已推送或当前服务已部署。</p>
    <form v-else class="lw-inline" @submit.prevent="checkCommit"><label class="lw-label">核对目标仓提交<input v-model="commit" class="lw-field" placeholder="完整 Git 提交 ID" minlength="40" maxlength="64" /></label><button class="lw-btn ghost sm" type="submit" :disabled="busy || commit.trim().length < 40">核对</button></form>
    <p v-if="delivery.decision" class="lw-small">{{ delivery.decision === 'accepted' ? '已接受' : '需要修改' }} · {{ delivery.decisionScope === 'integrated' ? '目标仓结果' : '补丁交付' }} · {{ delivery.decisionReason || '无说明' }}</p>
    <div v-else class="lw-stack"><label class="lw-label">接受范围<select v-model="scope" class="lw-field"><option value="patch">仅接受补丁交付</option><option value="integrated" :disabled="!delivery.integrationCommit">接受已核对的目标仓结果</option></select></label><label class="lw-label">验收说明或修改意见<textarea v-model="reason" class="lw-field" rows="2" /></label><div class="lw-inline"><button class="lw-btn primary sm" type="button" :disabled="busy || (scope === 'integrated' && !delivery.integrationCommit)" @click="decide('accepted')">接受这份交付</button><button class="lw-btn ghost sm" type="button" :disabled="busy" @click="decide('rejected')">需要修改</button></div><p class="lw-tiny lw-muted">接受代码交付不会自动完成整项事项；测试结果、远端发布和当前部署需分别核对。</p></div>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.delivery { display: grid; gap: 10px; border: 1px solid var(--lw-line, #dededb); border-radius: 10px; padding: 14px; min-width: 0; }
.delivery-versions { display: grid; gap: 12px; margin: 0; min-width: 0; }
.delivery-version { min-width: 0; }
.delivery-version dd { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin: 4px 0 0; min-width: 0; }
.delivery-version code { flex: 1 1 32ch; min-width: 0; overflow-wrap: anywhere; white-space: normal; user-select: text; }
.delivery-version button { flex: 0 0 auto; max-width: 100%; white-space: normal; }
.copy-feedback { min-height: 1.4em; margin: 0; overflow-wrap: anywhere; }
.delivery details { min-width: 0; }
.delivery summary { cursor: pointer; }
.delivery ul { padding-left: 18px; overflow-wrap: anywhere; }
.delivery .lw-inline { flex-wrap: wrap; }
.delivery .lw-label { min-width: min(100%, 280px); }
</style>

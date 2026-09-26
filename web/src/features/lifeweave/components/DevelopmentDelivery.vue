<script setup lang="ts">
import { shallowRef } from 'vue'
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
    <div class="lw-between"><strong>固定代码交付</strong><span class="lw-tiny lw-mono">{{ delivery.artifactSha256.slice(0, 12) }}</span></div>
    <p class="lw-small">{{ delivery.manifest.files.length }} 个文件，基于 Git {{ delivery.baseRevision.slice(0, 12) }}。下载包含完整二进制补丁、文件清单和实施报告；页面实时差异仅供预览。</p>
    <button class="lw-btn ghost sm" type="button" :disabled="busy" @click="download">下载完整交付 ZIP</button>
    <details><summary>交付文件与核验范围</summary><ul><li v-for="file in delivery.manifest.files" :key="file.path">{{ file.status }} · {{ file.path }}</li></ul><p class="lw-tiny lw-muted">服务已核对：差异格式、原基线补丁回放与文件树一致、采集期间工作树稳定。测试和页面结果仍需按实施 Run 的原始证据复核。</p><p class="lw-tiny lw-muted">{{ delivery.manifest.verificationBoundary }}</p><p v-if="delivery.manifest.excludedGenerated.length" class="lw-tiny lw-muted">已排除生成文件：{{ delivery.manifest.excludedGenerated.join('、') }}</p></details>
    <p v-if="delivery.integrationCommit" class="lw-small">目标提交 {{ delivery.integrationCommit.slice(0, 12) }} 的交付文件已核对{{ delivery.integrationCurrentHead ? '，核对时也是目标仓 HEAD' : '；核对时不是目标仓 HEAD' }}。这不代表远端已推送或当前服务已部署。</p>
    <form v-else class="lw-inline" @submit.prevent="checkCommit"><label class="lw-label">核对目标仓提交<input v-model="commit" class="lw-field" placeholder="完整 Git 提交 ID" minlength="40" maxlength="64" /></label><button class="lw-btn ghost sm" type="submit" :disabled="busy || commit.trim().length < 40">核对</button></form>
    <p v-if="delivery.decision" class="lw-small">{{ delivery.decision === 'accepted' ? '已接受' : '需要修改' }} · {{ delivery.decisionScope === 'integrated' ? '目标仓结果' : '补丁交付' }} · {{ delivery.decisionReason || '无说明' }}</p>
    <div v-else class="lw-stack"><label class="lw-label">接受范围<select v-model="scope" class="lw-field"><option value="patch">仅接受补丁交付</option><option value="integrated" :disabled="!delivery.integrationCommit">接受已核对的目标仓结果</option></select></label><label class="lw-label">验收说明或修改意见<textarea v-model="reason" class="lw-field" rows="2" /></label><div class="lw-inline"><button class="lw-btn primary sm" type="button" :disabled="busy || (scope === 'integrated' && !delivery.integrationCommit)" @click="decide('accepted')">接受这份交付</button><button class="lw-btn ghost sm" type="button" :disabled="busy" @click="decide('rejected')">需要修改</button></div><p class="lw-tiny lw-muted">接受代码交付不会自动完成整项事项；测试结果、远端发布和当前部署需分别核对。</p></div>
    <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.delivery { display: grid; gap: 10px; border: 1px solid var(--lw-line, #dededb); border-radius: 10px; padding: 14px; min-width: 0; }
.delivery details { min-width: 0; }
.delivery summary { cursor: pointer; }
.delivery ul { padding-left: 18px; overflow-wrap: anywhere; }
.delivery .lw-inline { flex-wrap: wrap; }
.delivery .lw-label { min-width: min(100%, 280px); }
</style>

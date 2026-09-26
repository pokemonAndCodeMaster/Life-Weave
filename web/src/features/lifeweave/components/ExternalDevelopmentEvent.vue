<script setup lang="ts">
import { shallowRef } from 'vue'
import { http } from '@/shared/api/http'
import type { Activity } from '../types'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import { apiError } from '../api/lifeweave'

const props = defineProps<{ activity: Activity }>()
const { activeWorkspace } = useLifeWeaveWorkspace()
const diff = shallowRef<{ patch: string; fileCount: number; truncated: boolean; scope: string } | null>(null)
const error = shallowRef('')
async function loadDiff() {
  if (!props.activity.itemId || !props.activity.payload?.sessionId) return
  try {
    const item = encodeURIComponent(props.activity.itemId)
    const session = encodeURIComponent(props.activity.payload.sessionId)
    diff.value = (await http.get(`/lifeweave/${activeWorkspace.value}/items/${item}/external-development/sessions/${session}/diff`)).data
    error.value = ''
  } catch (caught) { error.value = apiError(caught).message }
}
</script>

<template>
  <details v-if="activity.payload?.sessionId" class="lw-small lw-mt-8">
    <summary>{{ activity.payload.source === 'codex_hook' ? 'Codex 原生 Hook 事件' : '外部会话主动上报' }} · {{ activity.payload.phase }} · 查看版本与依据</summary>
    <p class="lw-muted">{{ activity.payload.source === 'codex_hook' ? 'Hook 只记录已绑定会话中受支持的工具/生命周期元数据，不保存原始命令或输出，也不能证明已捕获全部步骤。' : '阶段和检查由外部会话上报；下列 Git 状态由工作台在提交记录时读取。未开启 Hook 时不能看到该会话的内部步骤。' }}</p>
    <p v-if="activity.payload.source === 'codex_hook'" class="lw-mono lw-small">{{ activity.payload.toolName || activity.payload.phase }} · 模型 {{ activity.payload.model || '未报告' }} · {{ activity.payload.exitCode == null ? '退出码未报告' : `退出码 ${activity.payload.exitCode}` }} · Turn {{ activity.payload.turnId || '未知' }} · 输入哈希 {{ activity.payload.inputHash || '无' }}</p>
    <div v-if="activity.payload.observedGit" class="lw-mono lw-small">
      {{ activity.payload.observedGit.repositoryPath }}<br />
      Git {{ activity.payload.observedGit.revision.slice(0,12) }} · 已修改 {{ activity.payload.observedGit.changedCount }} 个文件 · 未跟踪 {{ activity.payload.observedGit.untrackedCount }} 个文件
      <ul v-if="activity.payload.observedGit.changedPaths.length || activity.payload.observedGit.untrackedPaths.length">
        <li v-for="path in activity.payload.observedGit.changedPaths" :key="`changed:${path}`">修改：{{ path }}</li>
        <li v-for="path in activity.payload.observedGit.untrackedPaths" :key="`untracked:${path}`">新增未跟踪：{{ path }}</li>
      </ul>
    </div>
    <ul v-if="activity.payload.declaredInputs?.length"><li v-for="entry in activity.payload.declaredInputs" :key="entry.id">登记材料：{{ entry.title }} · {{ entry.sourcePath }} · {{ entry.version.slice(0,12) }}</li></ul>
    <ul v-if="activity.payload.reportedChecks?.length"><li v-for="(check,index) in activity.payload.reportedChecks" :key="index">上报检查：{{ check }}</li></ul>
    <div v-if="activity.payload.phase === 'started'"><button type="button" class="lw-btn ghost sm" @click="loadDiff">查看当前 Git 差异</button><p v-if="error" class="lw-notice warning">{{ error }}</p><details v-if="diff" open><summary>{{ diff.fileCount }} 个文件{{ diff.truncated ? ' · 已截断' : '' }}</summary><p class="lw-muted">{{ diff.scope }}</p><pre class="lw-mono" style="white-space:pre-wrap;overflow:auto;max-height:440px">{{ diff.patch || '当前没有 Git 差异' }}</pre></details></div>
  </details>
</template>

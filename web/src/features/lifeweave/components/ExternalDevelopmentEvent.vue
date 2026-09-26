<script setup lang="ts">
import type { Activity } from '../types'

defineProps<{ activity: Activity }>()
</script>

<template>
  <details v-if="activity.payload?.sessionId" class="lw-small lw-mt-8">
    <summary>外部会话主动上报 · {{ activity.payload.phase }} · 查看版本与依据</summary>
    <p class="lw-muted">阶段和检查由外部会话上报；下列 Git 状态由工作台在提交记录时读取。这里不代表工作台捕获了该会话的全部内部步骤。</p>
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
  </details>
</template>

<script setup lang="ts">
import type { ConversationMode } from '../../api/conversations'
const body = defineModel<string>({ required: true })
const mode = defineModel<ConversationMode>('mode', { required: true })
const repositoryPath = defineModel<string>('repositoryPath', { required: true })
const acknowledgeExcludedChanges = defineModel<boolean>('acknowledgeExcludedChanges', { required: true })
defineProps<{ sending: boolean; uncertain: boolean; disabled?: boolean; processing?: boolean; anchor?: string }>()
defineEmits<{ send: []; clearQuote: [] }>()
</script>

<template>
  <form class="conversation-composer" @submit.prevent="$emit('send')">
    <div v-if="anchor" class="quoted"><span>针对成果：{{ anchor }}</span><button class="lw-text-btn" type="button" :disabled="sending || uncertain" @click="$emit('clearQuote')">取消引用</button></div>
    <label class="lw-label" for="conversation-body">说说你现在想做什么</label>
    <textarea id="conversation-body" v-model="body" class="lw-field conversation-input" rows="4" maxlength="20000" placeholder="问一个问题，留下想法，或说清楚想委托完成的事……" :disabled="sending || uncertain || disabled" required></textarea>
    <details :open="mode === 'execute' ? true : undefined" class="development-options"><summary>开发任务：指定项目仓库（可选）</summary><label class="lw-label">本次开发使用的 Git 项目目录<input v-model="repositoryPath" class="lw-field" autocomplete="off" placeholder="/home/用户名/project/项目" :disabled="sending || uncertain || disabled" /></label><label v-if="repositoryPath" class="lw-small"><input v-model="acknowledgeExcludedChanges" type="checkbox" :disabled="sending || uncertain || disabled" /> 若目录有未提交修改，我知道受管运行只包含当前提交</label><p class="lw-tiny lw-muted">明确委托开发并指定目录后，自动从只读方案开始；未指定时先登记事项，再到事项的“开发 Agent”页选择仓库。</p></details>
    <div class="composer-actions">
      <label class="mode-label">本次范围 <select v-model="mode" class="lw-field mode-select" :disabled="sending || uncertain || disabled"><option value="auto">按自然表达判断</option><option value="record">只记录</option><option value="discuss">仅讨论</option><option value="execute">明确委托</option></select></label>
      <button class="lw-btn primary" type="submit" :disabled="sending || disabled || (processing && !uncertain) || !body.trim()">{{ sending ? '正在发送…' : uncertain ? '核对并重试原请求' : processing ? '等待本次处理结束' : '发送' }}</button>
    </div>
    <p v-if="uncertain" class="lw-small" role="status">上次请求的结果尚未确认。重试会核对同一请求，避免重复创建或执行；原文已保留。</p>
    <p v-else class="lw-tiny lw-muted">普通问答可以直接开始。只有需要持续推进时才关联事项；运行进度以实际回执为准。</p>
  </form>
</template>

<style scoped>
.conversation-composer { border-top: 1px solid var(--lw-line, #dededb); padding-top: 18px; }
.conversation-input { resize: vertical; min-height: 112px; }
.composer-actions { display: flex; gap: 12px; justify-content: space-between; align-items: end; flex-wrap: wrap; margin-top: 10px; }
.mode-label { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.mode-select { width: auto; }
.quoted { margin-bottom: 12px; border-left: 3px solid #748975; padding: 8px 12px; font-size: 13px; max-height: 120px; overflow: auto; white-space: pre-wrap; }
.quoted span { display: block; margin-bottom: 6px; }
.development-options { margin-top: 10px; font-size: 12px; }
.development-options summary { cursor: pointer; }
.development-options .lw-label { margin-top: 10px; }
</style>

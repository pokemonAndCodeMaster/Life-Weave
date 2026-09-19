<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: string; tone?: string }>()
const toneClass = computed(() => props.tone ?? ({
  已计划: 'blue', 待确认: 'amber', 进行中: 'blue', 待验收: 'purple', 已完成: 'green', 已阻塞: 'red',
  running: 'blue', queued: 'amber', succeeded: 'green', failed: 'red', cancelled: '',
  在线: 'green', 离线: 'red', 已暂停: 'amber', 未验证: 'amber', 已证明: 'green',
  待补证: 'amber', 待发布: 'purple', 已发布: 'green', 已登记: 'blue',
}[props.value] ?? ''))
const label=computed(()=>({queued:'等待执行',claimed:'准备中',running:'执行中',succeeded:'执行完成',failed:'执行失败',cancelled:'已取消',cancelling:'正在取消',paused:'已暂停',pause_requested:'正在暂停',unavailable:'环境不可用',online:'在线',offline:'离线',draining:'完成后停用'}[props.value]??props.value))
</script>

<template>
  <span class="lw-tag" :class="toneClass"><slot>{{ label }}</slot></span>
</template>

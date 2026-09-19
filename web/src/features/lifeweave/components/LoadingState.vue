<script setup lang="ts">
defineProps<{ error?: string | null; empty?: string; loading?: boolean }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="loading" class="lw-panel lw-empty" role="status">正在读取经纬工作区…</div>
  <div v-else-if="error" class="lw-panel lw-empty" role="alert">
    <p>{{ error }}</p>
    <button class="lw-btn" type="button" @click="$emit('retry')">重新读取</button>
  </div>
  <div v-else class="lw-panel lw-empty">{{ empty ?? '这里还没有内容。' }}</div>
</template>

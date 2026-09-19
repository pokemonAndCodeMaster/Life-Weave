<script setup lang="ts">
defineProps<{ title: string; subtitle: string; eyebrow?: string }>()
</script>

<template>
  <header class="lw-page-head">
    <div>
      <div v-if="eyebrow" class="lw-eyebrow">{{ eyebrow }}</div>
      <h1>{{ title }}</h1>
      <div class="lw-subtitle">{{ subtitle }}</div>
    </div>
    <div class="lw-inline"><slot /></div>
  </header>
</template>

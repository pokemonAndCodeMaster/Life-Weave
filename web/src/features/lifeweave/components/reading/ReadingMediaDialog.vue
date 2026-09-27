<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, shallowRef } from 'vue'
const props = defineProps<{ title: string; image?: string; svg?: string }>()
const emit = defineEmits<{ close: [] }>()
const dialog = shallowRef<HTMLDialogElement | null>(null)
const zoom = shallowRef(100)
const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
const previousOverflow = document.body.style.overflow
onMounted(async () => { document.body.style.overflow='hidden'; await nextTick(); dialog.value?.showModal?.() })
onBeforeUnmount(() => { dialog.value?.close?.(); document.body.style.overflow=previousOverflow; if (previousFocus?.isConnected) previousFocus.focus() })
</script>
<template>
  <Teleport to="body">
    <dialog ref="dialog" class="reading-media-dialog" :aria-label="props.title" @cancel.prevent="emit('close')">
      <header class="media-toolbar"><strong>{{ title }}</strong><div class="media-actions"><button type="button" class="lw-btn sm" :disabled="zoom <= 50" aria-label="缩小" @click="zoom -= 25">−</button><button type="button" class="lw-btn sm" @click="zoom = 100">{{ zoom }}% · 适合窗口</button><button type="button" class="lw-btn sm" :disabled="zoom >= 400" aria-label="放大" @click="zoom += 25">+</button><button type="button" class="lw-btn sm" @click="emit('close')">关闭大图</button></div></header>
      <div class="media-viewport"><div class="media-content" :style="{ width: `${zoom}%` }"><img v-if="image" :src="image" :alt="title" /><div v-else-if="svg" class="media-svg" v-html="svg"></div></div></div>
    </dialog>
  </Teleport>
</template>
<style scoped>
.reading-media-dialog { width: min(1400px, 94vw); max-width: 94vw; max-height: 92vh; padding: 0; border: 1px solid #c4d2df; border-radius: 12px; background: #fff; color: #273e53; }
.reading-media-dialog::backdrop { background: #15293db3; }
.media-toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 14px 18px; border-bottom: 1px solid #e1e8ef; }
.media-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.media-viewport { overflow: auto; max-height: 75vh; padding: 20px; }
.media-content { min-width: 0; }
.media-content img,.media-svg :deep(svg) { display: block; width: 100%; max-width: none !important; height: auto; }
</style>

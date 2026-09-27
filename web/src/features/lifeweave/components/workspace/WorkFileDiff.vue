<script setup lang="ts">
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { apiError } from '../../api/lifeweave'
import { downloadOutputFile, getOutputAsset, getOutputFile } from '../../api/outputFiles'
import type { OutputCatalogFile, OutputFileContent } from '../../api/outputFiles'
import type { WorkspaceKind } from '../../types'
import { statusLabels } from './workOutputCatalog'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string; outputId: string; version: string; file: OutputCatalogFile }>()
const content = shallowRef<OutputFileContent | null>(null)
const loading = shallowRef(false)
const error = shallowRef('')
const imageUrl = shallowRef('')
const imageError = shallowRef('')
const downloading = shallowRef(false)
let generation = 0

function releaseImage() { if (imageUrl.value) URL.revokeObjectURL(imageUrl.value); imageUrl.value = '' }
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = filename; link.hidden = true
  document.body.append(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function load() {
  const ticket = ++generation
  content.value = null
  releaseImage()
  imageError.value = ''
  loading.value = true
  error.value = ''
  try {
    const result = await getOutputFile(props.workspace, props.itemId, props.outputId, props.file.path, props.version)
    if (ticket === generation) {
      content.value = result
      if (result.binary && result.contentType.startsWith('image/')) {
        try {
          const asset = await getOutputAsset(props.workspace, props.itemId, props.outputId, props.file.path, props.version)
          if (ticket === generation) imageUrl.value = URL.createObjectURL(asset)
        } catch (caught) { if (ticket === generation) imageError.value = apiError(caught).message }
      }
    }
  } catch (caught) {
    if (ticket === generation) error.value = apiError(caught).message
  } finally {
    if (ticket === generation) loading.value = false
  }
}
watch([() => props.workspace, () => props.itemId, () => props.outputId, () => props.version, () => props.file.path], load, { immediate: true })
onBeforeUnmount(() => { generation += 1; releaseImage() })
async function download() {
  downloading.value = true
  try {
    const blob = await downloadOutputFile(props.workspace, props.itemId, props.outputId, props.file.path, props.version)
    saveBlob(blob, props.file.path.split('/').at(-1) || 'output-file')
  } catch (caught) { error.value = apiError(caught).message }
  finally { downloading.value = false }
}
</script>

<template>
  <section class="file-detail" tabindex="-1" aria-label="所选文件差异">
    <header><div><span class="file-kind">{{ statusLabels[file.status] }}{{ file.binary ? ' · 二进制' : '' }}</span><h4>{{ file.path }}</h4><p v-if="file.previousPath">原路径：{{ file.previousPath }}</p></div><span class="file-count" v-if="!file.binary && (file.additions !== null || file.deletions !== null)">+{{ file.additions ?? 0 }} / −{{ file.deletions ?? 0 }}</span></header>
    <button type="button" class="lw-btn sm" :disabled="downloading" @click="download">{{ downloading ? '正在下载…' : '下载此固定版本文件' }}</button>
    <p v-if="loading" role="status">正在读取固定版本文件…</p>
    <p v-else-if="error" class="lw-notice warning" role="alert">{{ error }} <button type="button" class="lw-btn sm" @click="load">重新读取</button></p>
    <template v-else-if="content">
      <div v-if="content.binary || file.binary" class="binary-note"><p>二进制文件 · {{ file.contentType || content.contentType }} · {{ file.size }} 字节。此处没有可逐行展示的差异。</p><a v-if="imageUrl" :href="imageUrl" target="_blank" rel="noopener noreferrer" :aria-label="`查看大图：${file.path}`"><img :src="imageUrl" :alt="file.path" /></a><p v-else-if="imageError" role="status">图片预览不可用：{{ imageError }}。仍可下载固定版本文件。</p></div>
      <template v-else>
        <div v-if="content.diff !== null" class="text-section"><strong>本次差异</strong><pre>{{ content.diff || '没有文本差异' }}</pre></div>
        <div v-else-if="content.content !== null || content.after !== null || content.before !== null" class="text-section"><strong>{{ content.after === null && content.before !== null ? '变更前内容' : '固定版本内容' }}</strong><pre>{{ content.content ?? content.after ?? content.before }}</pre></div>
        <p v-else class="file-empty">此文件没有可读取的文本快照。</p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.file-detail { min-width: 0; padding: 16px; border: 1px solid #dce6ee; border-radius: 9px; background: #fff; }
header { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
h4 { margin: 3px 0 0; font-size: 15px; overflow-wrap: anywhere; }
header p,.file-kind,.file-count { margin: 5px 0 0; color: #647f93; font-size: 11px; overflow-wrap: anywhere; }
.file-count { flex: none; }
.text-section { min-width: 0; margin-top: 15px; }
.text-section strong { display: block; margin-bottom: 7px; color: #38526a; font-size: 12px; }
pre { max-height: min(56vh, 640px); overflow: auto; margin: 0; padding: 14px; border-radius: 7px; background: #172332; color: #edf3f9; font-size: 12px; line-height: 1.55; tab-size: 4; white-space: pre; }
.binary-note,.file-empty { color: #58748a; font-size: 13px; line-height: 1.6; }
.binary-note img { display: block; max-width: 100%; max-height: 45vh; margin-top: 10px; border: 1px solid #dae4ec; border-radius: 7px; object-fit: contain; }
</style>

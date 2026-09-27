<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { apiError } from '../../api/lifeweave'
import { downloadOutputBundle, getOutputCatalog } from '../../api/outputFiles'
import type { OutputCatalog, OutputCatalogFile, OutputDocumentRef, OutputFileStatus } from '../../api/outputFiles'
import type { WorkspaceKind } from '../../types'
import WorkFileDiff from './WorkFileDiff.vue'
import WorkFileTree from './WorkFileTree.vue'
import { buildFileTree, categories, fileTotals, statusLabels, uniqueCatalogFiles } from './workOutputCatalog'

const props = defineProps<{ workspace: WorkspaceKind; itemId: string; outputId: string; version?: string | null; selectedPath?: string | null }>()
const emit = defineEmits<{ selectFile: [path: string]; readDocument: [document: OutputDocumentRef] }>()
const container = ref<HTMLElement | null>(null)
const catalog = shallowRef<OutputCatalog | null>(null)
const loading = shallowRef(false)
const error = shallowRef('')
const downloading = shallowRef(false)
const search = ref('')
const status = ref<OutputFileStatus | 'all'>('all')
const expanded = ref<string[]>([])
const openCategories = ref<string[]>([])
let generation = 0
function storageKey(version: string) { return `lifeweave:output-tree:${props.workspace}:${props.itemId}:${props.outputId}:${version}` }
function restore(version: string) {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey(version)) || '{}') as Record<string, unknown>
    search.value = typeof saved.search === 'string' ? saved.search : ''
    status.value = typeof saved.status === 'string' && (saved.status === 'all' || saved.status in statusLabels) ? saved.status as OutputFileStatus | 'all' : 'all'
    expanded.value = Array.isArray(saved.expanded) ? saved.expanded.filter((value): value is string => typeof value === 'string') : []
    openCategories.value = Array.isArray(saved.openCategories) ? saved.openCategories.filter((value): value is string => typeof value === 'string') : []
  } catch { /* Private browsing may disable storage; the directory still works. */ }
}
function remember() {
  if (!catalog.value) return
  try { sessionStorage.setItem(storageKey(catalog.value.version), JSON.stringify({ search: search.value, status: status.value, expanded: expanded.value, openCategories: openCategories.value })) }
  catch { /* Preserve in-memory browsing when storage is unavailable. */ }
}
watch([search, status, expanded, openCategories], remember)
function revealSelected(path: string | null | undefined) {
  const file = catalog.value?.files.find(entry => entry.path === path)
  if (!file) return
  if (!openCategories.value.includes(file.category)) openCategories.value = [...openCategories.value, file.category]
  const parts = file.path.split('/').filter(Boolean)
  const folders = parts.slice(0, -1).map((_, index) => parts.slice(0, index + 1).join('/'))
  expanded.value = [...new Set([...expanded.value, ...folders])]
  void nextTick(() => {
    const selected = container.value?.querySelector<HTMLElement>(file.documentRef ? '.file-button.selected' : '.file-detail')
    if (!file.documentRef) selected?.focus({ preventScroll: true })
    selected?.scrollIntoView?.({ block: 'nearest' })
  })
}
watch(() => props.selectedPath, revealSelected)

async function load() {
  const ticket = ++generation
  catalog.value = null
  error.value = ''
  loading.value = true
  try {
    const result = await getOutputCatalog(props.workspace, props.itemId, props.outputId, props.version)
    if (ticket !== generation) return
    if (result.outputId !== props.outputId || (props.version && result.version !== props.version)) {
      error.value = '交付目录与所选成果版本不一致，请重新读取。'
      return
    }
    catalog.value = result
    restore(result.version)
    revealSelected(props.selectedPath)
  } catch (caught) { if (ticket === generation) error.value = apiError(caught).message }
  finally { if (ticket === generation) loading.value = false }
}
watch([() => props.workspace, () => props.itemId, () => props.outputId, () => props.version], () => {
  search.value = ''
  status.value = 'all'
  expanded.value = []
  openCategories.value = []
  void load()
}, { immediate: true })
onBeforeUnmount(() => { generation += 1 })

const allFiles = computed(() => uniqueCatalogFiles(catalog.value?.files || []))
const visibleFiles = computed(() => allFiles.value.filter(file =>
  (status.value === 'all' || file.status === status.value)
  && (!search.value.trim() || `${file.path} ${file.previousPath || ''}`.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase())),
))
const groups = computed(() => categories.map(category => {
  const files = allFiles.value.filter(file => file.category === category.id)
  const visible = visibleFiles.value.filter(file => file.category === category.id)
  return { ...category, files, visible, totals: fileTotals(files), tree: buildFileTree(visible) }
}).filter(group => group.files.length))
const selectedFile = computed(() => allFiles.value.find(file => file.path === props.selectedPath) || null)
const filtering = computed(() => !!search.value.trim() || status.value !== 'all')

function toggle(values: string[], key: string): string[] {
  return values.includes(key) ? values.filter(value => value !== key) : [...values, key]
}
function open(file: OutputCatalogFile) {
  if (file.documentRef) emit('readDocument', file.documentRef)
  else emit('selectFile', file.path)
}
async function downloadBundle() {
  if (!catalog.value) return
  downloading.value = true
  try {
    const data = await downloadOutputBundle(props.workspace, props.itemId, props.outputId, catalog.value.version)
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url; link.download = `lifeweave-${props.outputId.replace(/[^a-z0-9_-]/gi, '-')}.zip`; link.hidden = true
    document.body.append(link); link.click(); link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (caught) { error.value = apiError(caught).message }
  finally { downloading.value = false }
}
</script>

<template>
  <section ref="container" class="output-catalog" aria-label="固定产物目录">
    <div class="catalog-head"><div><h4>产物分类与目录</h4><p v-if="catalog">固定版本 {{ catalog.version.slice(0, 12) }} · {{ allFiles.length }} 个文件</p></div><button v-if="catalog" type="button" class="lw-btn sm" :disabled="downloading" @click="downloadBundle">{{ downloading ? '正在下载…' : '下载整份固定成果' }}</button></div>
    <p v-if="loading" role="status">正在读取完整产物目录…</p>
    <p v-else-if="error" class="lw-notice warning" role="alert">{{ error }} <button type="button" class="lw-btn sm" @click="load">重新读取</button></p>
    <template v-else-if="catalog">
      <p v-if="catalog.snapshotBoundary" class="catalog-boundary">{{ catalog.snapshotBoundary }}</p>
      <ul v-if="catalog.warnings?.length" class="catalog-warnings"><li v-for="warning in catalog.warnings" :key="warning">{{ warning }}</li></ul>
      <p v-if="!allFiles.length" class="empty">这份成果没有登记文件目录。</p>
      <template v-else>
        <div class="catalog-filter"><label>查找路径<input v-model="search" type="search" placeholder="文件名或目录" /></label><label>变更状态<select v-model="status"><option value="all">全部状态</option><option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option></select></label><span role="status">{{ filtering ? `找到 ${visibleFiles.length} / ${allFiles.length} 个文件` : `共 ${allFiles.length} 个文件` }}</span></div>
        <div class="category-list">
          <section v-for="group in groups" :key="group.id" class="category">
            <button type="button" class="category-button" :aria-expanded="openCategories.includes(group.id)" @click="openCategories = toggle(openCategories, group.id)"><strong>{{ group.label }}</strong><span>{{ group.totals.count }} 文件<template v-if="group.totals.additions || group.totals.deletions"> · +{{ group.totals.additions }} / −{{ group.totals.deletions }}</template><template v-if="group.totals.binary"> · {{ group.totals.binary }} 个二进制</template></span><span aria-hidden="true">{{ openCategories.includes(group.id) ? '▾' : '▸' }}</span></button>
            <div v-if="openCategories.includes(group.id)" class="category-content">
              <p v-if="!group.visible.length" class="empty">当前筛选下没有文件。</p>
              <ul v-else class="file-tree"><WorkFileTree v-for="entry in group.tree.children" :key="entry.path" :node="entry" :expanded="expanded" :force-open="!!search.trim()" :selected-path="selectedPath || null" @toggle="expanded = toggle(expanded, $event)" @open="open" /></ul>
            </div>
          </section>
        </div>
        <WorkFileDiff v-if="selectedFile && !selectedFile.documentRef" :workspace="workspace" :item-id="itemId" :output-id="outputId" :version="catalog.version" :file="selectedFile" />
      </template>
    </template>
  </section>
</template>

<style scoped>
.output-catalog { display: grid; gap: 13px; min-width: 0; }
.catalog-head { display: flex; align-items: start; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.catalog-head h4 { margin: 0; font-size: 15px; color: #29445e; }
.catalog-head p,.empty { margin: 5px 0 0; color: #667f92; font-size: 12px; }
.catalog-boundary { margin: 0; color: #607a8d; font-size: 12px; }
.catalog-warnings { margin: 0; padding-inline-start: 20px; color: #916135; font-size: 12px; }
.catalog-filter { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; }
.catalog-filter label { display: grid; gap: 4px; color: #526c81; font-size: 12px; }
.catalog-filter input,.catalog-filter select { min-height: 38px; max-width: min(100%, 250px); padding: 6px 9px; border: 1px solid #b9ccdc; border-radius: 7px; background: #fff; color: #243d53; font: inherit; }
.catalog-filter span { color: #607a8e; font-size: 12px; }
.category-list { display: grid; gap: 8px; min-width: 0; }
.category { min-width: 0; border: 1px solid #dbe6ef; border-radius: 9px; overflow: hidden; background: #fff; }
.category-button { width: 100%; min-height: 48px; display: flex; align-items: center; flex-wrap: wrap; gap: 7px 11px; padding: 10px 13px; border: 0; text-align: start; background: #f7fafc; color: #2e4b63; cursor: pointer; }
.category-button strong { font-size: 13px; }
.category-button span:nth-child(2) { margin-inline-end: auto; font-size: 11px; color: #5e788c; }
.category-button:hover,.category-button:focus-visible { outline: 2px solid #6398c5; outline-offset: -2px; background: #edf5fb; }
.category-content { padding: 8px 10px 12px; min-width: 0; }
.file-tree { margin: 0; padding: 0; max-height: min(42vh, 460px); overflow: auto; }
@media(max-width:720px){ .catalog-filter label,.catalog-filter input,.catalog-filter select { width: 100%; max-width: 100%; } }
</style>

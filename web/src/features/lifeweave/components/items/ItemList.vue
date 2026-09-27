<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import LifeWeaveIcon from '../LifeWeaveIcon.vue'
import StatusBadge from '../StatusBadge.vue'
import type { WorkItem, WorkspacePreferences } from '../../types'
import { allColumns, buildItemGroups, columnLabels, completedAt, itemTags, ownerLabel, priorityLabel, priorityLabels, restoreItemView, typeLabel, type Column, type ItemView } from './itemView'

const props = defineProps<{
  items: WorkItem[]
  actor: string
  workspace: string
  saved: WorkspacePreferences
  topicSelection?: { name: string } | null
  saveView: (view: Record<string, unknown>) => Promise<unknown>
}>()
const emit = defineEmits<{ peek: [item: WorkItem] }>()
const view = ref<ItemView>(restoreItemView(props.saved))
const expanded = ref(new Set<string>())
const filtersOpen = shallowRef(false)
const saving = shallowRef(false)
const saveMessage = shallowRef('')
watch(() => `${props.workspace}\u0000${JSON.stringify(props.saved)}`, () => {
  view.value = restoreItemView(props.saved)
  expanded.value = new Set()
}, { immediate: true })
watch(() => props.topicSelection, (selection) => { if (selection) { view.value.topic = selection.name; view.value.focus = 'all' } })

const statuses = computed(() => unique(props.items.map((item) => item.state)))
const types = computed(() => [...new Map(props.items.map((item) => [item.itemType || item.kind, typeLabel(item)])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'zh-CN')))
const tags = computed(() => unique(props.items.flatMap(itemTags)))
const domains = computed(() => unique(props.items.flatMap((item) => item.domains)))
const topics = computed(() => unique(props.items.flatMap((item) => item.topics)))
const owners = computed(() => unique(props.items.map((item) => ownerLabel(item.owner))))
const result = computed(() => buildItemGroups(props.items, view.value, props.actor, expanded.value))
const visibleColumns = computed(() => allColumns.filter((column) => view.value.columns.includes(column)))
const activeFilters = computed(() => {
  const current = view.value
  const labels: string[] = []
  if (current.query.trim()) labels.push(`搜索：${current.query.trim()}`)
  if (current.status) labels.push(`状态：${current.status}`)
  if (current.priority) labels.push(`优先级：${priorityLabels[Number(current.priority)] ?? current.priority}`)
  if (current.type) labels.push(`类型：${types.value.find(([key]) => key === current.type)?.[1] ?? current.type}`)
  if (current.tag) labels.push(`标签：${current.tag}`)
  if (current.domain) labels.push(`领域：${current.domain}`)
  if (current.topic) labels.push(`专题：${current.topic}`)
  if (current.owner) labels.push(`负责人：${current.owner}`)
  if (current.dateFrom || current.dateTo) {
    const field = { created: '创建时间', updated: '更新时间', due: '目标时间' }[current.dateField]
    labels.push(`${field}：${current.dateFrom || '起始不限'} 至 ${current.dateTo || '结束不限'}`)
  }
  return labels
})
function unique(values: string[]) { return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN')) }
function itemUrl(id: string) { return `/lifeweave/${props.workspace}/items/${encodeURIComponent(id)}/overview` }
function toggle(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}
function toggleColumn(column: Column) {
  view.value.columns = view.value.columns.includes(column)
    ? view.value.columns.filter((entry) => entry !== column)
    : [...view.value.columns, column]
}
function resetFilters() {
  Object.assign(view.value, { query: '', status: '', priority: '', type: '', tag: '', domain: '', topic: '', owner: '', dateFrom: '', dateTo: '' })
}
async function save() {
  saving.value = true
  saveMessage.value = ''
  try {
    await props.saveView({ ...view.value, columns: [...view.value.columns] })
    saveMessage.value = activeFilters.value.length ? `视图已保存，包含 ${activeFilters.value.length} 项筛选。` : '视图已保存。'
  } catch {
    saveMessage.value = '保存失败，请稍后重试。当前调整仍可继续使用。'
  } finally { saving.value = false }
}
function dateText(value: string | null | undefined) { return value ? value.slice(0, 10) : '—' }
</script>

<template>
  <div class="item-view">
    <div class="focus-bar" role="group" aria-label="事项范围">
      <button v-for="option in [{ key: 'active', label: '未完成' }, { key: 'all', label: '全部' }, { key: 'completed', label: '已完成' }, { key: 'mine', label: '待我处理' }]" :key="option.key" class="focus-button" :class="{ active: view.focus === option.key }" type="button" :aria-pressed="view.focus === option.key" @click="view.focus = option.key as ItemView['focus']">{{ option.label }}</button>
    </div>
    <div class="list-toolbar">
      <label class="search-field"><span class="sr-only">搜索事项</span><input v-model="view.query" placeholder="搜索标题、编号或进展" type="search" /></label>
      <label class="control"><span>状态</span><select v-model="view.status" aria-label="筛选状态"><option value="">全部状态</option><option v-for="entry in statuses" :key="entry">{{ entry }}</option></select></label>
      <button class="lw-btn" type="button" aria-controls="item-extra-filters" :aria-expanded="filtersOpen" @click="filtersOpen = !filtersOpen">{{ activeFilters.length ? `筛选（${activeFilters.length}）` : '筛选' }}</button>
    </div>
    <div v-show="filtersOpen" id="item-extra-filters" class="extra-filters">
      <div class="filter-fields">
      <label class="control"><span>优先级</span><select v-model="view.priority" aria-label="筛选优先级"><option value="">全部优先级</option><option v-for="(entry, index) in priorityLabels" :key="index" :value="String(index)">{{ entry }}</option></select></label>
      <label class="control"><span>类型</span><select v-model="view.type" aria-label="筛选类型"><option value="">全部类型</option><option v-for="[key, label] in types" :key="key" :value="key">{{ label }}</option></select></label>
      <label class="control"><span>标签</span><select v-model="view.tag" aria-label="筛选标签"><option value="">全部标签</option><option v-for="entry in tags" :key="entry">{{ entry }}</option></select></label>
      <label class="control"><span>领域</span><select v-model="view.domain" aria-label="筛选领域"><option value="">全部领域</option><option v-for="entry in domains" :key="entry">{{ entry }}</option></select></label>
      <label class="control"><span>专题</span><select v-model="view.topic" aria-label="筛选专题"><option value="">全部专题</option><option v-for="entry in topics" :key="entry">{{ entry }}</option></select></label>
      <label class="control"><span>负责人</span><select v-model="view.owner" aria-label="筛选负责人"><option value="">全部负责人</option><option v-for="entry in owners" :key="entry">{{ entry }}</option></select></label>
      </div>
      <div class="date-filters">
      <label class="control"><span>日期</span><select v-model="view.dateField" aria-label="日期字段"><option value="updated">更新时间</option><option value="created">创建时间</option><option value="due">目标时间</option></select></label>
      <label class="control"><span>从</span><input v-model="view.dateFrom" aria-label="开始日期" type="date" /></label>
      <label class="control"><span>到</span><input v-model="view.dateTo" aria-label="结束日期" type="date" /></label>
      </div>
    </div>
    <div v-if="activeFilters.length" class="filter-summary" role="status"><span>已启用 {{ activeFilters.length }} 项筛选：{{ activeFilters.join(' · ') }}</span><button class="lw-text-btn" type="button" @click="resetFilters">清除筛选</button></div>
    <div class="list-options">
      <label class="control"><span>分组</span><select v-model="view.group" aria-label="分组方式"><option value="none">不分组</option><option value="topic">专题</option><option value="domain">领域</option><option value="state">状态</option><option value="owner">负责人</option></select></label>
      <label class="control"><span>排序</span><select v-model="view.sort" aria-label="排序方式"><option value="updated">最近更新</option><option value="created">最近创建</option><option value="due">目标时间</option><option value="priority">优先级</option><option value="title">标题</option></select></label>
      <details class="column-menu"><summary class="lw-btn">显示列</summary><div class="column-options"><label v-for="column in allColumns" :key="column"><input type="checkbox" :checked="view.columns.includes(column)" @change="toggleColumn(column)" />{{ columnLabels[column] }}</label></div></details>
      <span class="list-spacer"></span>
      <span class="count" role="status">{{ result.count }} 项</span>
      <button class="lw-btn" type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存视图' }}</button>
      <RouterLink class="lw-btn" :to="`/lifeweave/${workspace}/meeting`"><LifeWeaveIcon name="meeting" />会议视图</RouterLink>
    </div>
    <p v-if="saveMessage" class="save-message" :role="saveMessage.startsWith('保存失败') ? 'alert' : 'status'">{{ saveMessage }}</p>
    <div class="lw-panel">
      <template v-for="group in result.groups" :key="group.label">
        <div v-if="view.group !== 'none'" class="lw-group-head"><strong>{{ group.label }}</strong><span class="lw-muted">{{ group.count }} 项</span></div>
        <div class="lw-table-wrap">
          <table class="lw-data-table item-table">
            <thead><tr><th scope="col">事项</th><th v-for="column in visibleColumns" :key="column" scope="col">{{ columnLabels[column] }}</th><th scope="col"><span class="sr-only">操作</span></th></tr></thead>
            <tbody>
              <tr v-for="row in group.rows" :key="`${group.label}-${row.item.id}`" :class="{ 'context-row': row.context }">
                <td class="title"><div class="item-title" :style="{ paddingLeft: `${Math.min(row.depth, 8) * 16}px` }"><button v-if="row.hasChildren" class="expand-button" type="button" :disabled="row.forcedOpen" :title="row.forcedOpen ? '筛选中保留子项' : undefined" :aria-label="row.forcedOpen ? '筛选中保留子项' : `${expanded.has(row.item.id) ? '收起' : '展开'} ${row.item.title}`" :aria-expanded="expanded.has(row.item.id) || row.forcedOpen" @click="toggle(row.item.id)">{{ expanded.has(row.item.id) || row.forcedOpen ? '▾' : '▸' }}</button><span v-else class="expand-placeholder"></span><div class="item-identity"><RouterLink class="lw-row-link" :to="itemUrl(row.item.id)">{{ row.item.title }}</RouterLink><span class="item-id" :title="row.item.id">{{ row.item.id }}</span><span v-if="row.context" class="path-label">上级路径</span></div></div></td>
                <td v-for="column in visibleColumns" :key="column" :class="{ progress: column === 'update' }">
                  <template v-if="column === 'update'">{{ row.item.update }}</template>
                  <template v-else-if="column === 'owner'">{{ ownerLabel(row.item.owner) || '—' }}</template>
                  <StatusBadge v-else-if="column === 'state'" :value="row.item.state" />
                  <template v-else-if="column === 'priority'">{{ priorityLabel(row.item) }}</template>
                  <template v-else-if="column === 'type'">{{ typeLabel(row.item) }}</template>
                  <template v-else-if="column === 'tag'">{{ itemTags(row.item).join('、') || '—' }}</template>
                  <template v-else-if="column === 'domain'">{{ row.item.domains.join('、') || '未关联' }}</template>
                  <template v-else-if="column === 'topic'">{{ row.item.topics.join('、') || '未关联' }}</template>
                  <template v-else-if="column === 'due'">{{ dateText(row.item.due) }}</template>
                  <template v-else-if="column === 'created'">{{ dateText(row.item.createdAt) }}</template>
                  <template v-else-if="column === 'updated'">{{ dateText(row.item.updatedAt) }}</template>
                  <template v-else-if="column === 'completed'">{{ dateText(completedAt(row.item)) }}</template>
                </td>
                <td><button class="lw-btn ghost icon-only" type="button" :aria-label="`速览 ${row.item.title}`" @click="emit('peek', row.item)"><LifeWeaveIcon name="eye" /></button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <div v-if="!result.groups.length" class="lw-empty">{{ items.length ? '没有符合条件的事项。可以清除筛选或切换范围。' : '这里还没有事项。点击“新建事项”开始。' }}</div>
      <div v-else class="lw-table-footer">{{ result.count }} 项事项<span v-if="view.group === 'topic' || view.group === 'domain'"> · 跨组事项按编号去重</span></div>
    </div>
  </div>
</template>

<style scoped>
.focus-bar,.list-toolbar,.date-filters,.list-options{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.focus-bar{margin-bottom:14px;border-bottom:1px solid var(--lw-line)}.focus-button{padding:9px 12px;border:0;border-bottom:2px solid transparent;background:none;color:var(--lw-sub);cursor:pointer}.focus-button.active{border-bottom-color:var(--lw-blue);color:var(--lw-blue);font-weight:600}.list-toolbar,.date-filters{margin-bottom:12px}.search-field{flex:1 1 210px}.search-field input,.control select,.control input{width:100%;min-height:34px;padding:6px 9px;border:1px solid #dce1e8;border-radius:5px;background:#fff;color:var(--lw-ink);font:inherit;font-size:12px}.control{display:flex;align-items:center;gap:5px;color:var(--lw-muted);font-size:11px}.control select{width:auto;max-width:145px}.control input{width:135px}.clear-button{white-space:nowrap}.list-options{margin-bottom:14px}.list-spacer{flex:1}.count,.save-message{color:var(--lw-muted);font-size:11px}.save-message{margin:0 0 9px}.column-menu{position:relative}.column-menu summary{list-style:none;cursor:pointer}.column-menu summary::-webkit-details-marker{display:none}.column-options{position:absolute;z-index:5;right:0;top:38px;display:grid;min-width:155px;padding:9px 12px;border:1px solid var(--lw-line);border-radius:5px;background:#fff;box-shadow:0 8px 20px #172b501a}.column-options label{display:flex;gap:8px;align-items:center;padding:4px;color:var(--lw-sub);font-size:12px;white-space:nowrap}.item-title{display:flex;align-items:flex-start;gap:5px}.expand-button,.expand-placeholder{flex:none;width:18px;min-height:23px;padding:0;border:0;background:transparent;color:var(--lw-blue);font-size:14px;cursor:pointer}.item-identity{min-width:0}.item-id{display:block;color:var(--lw-muted);font:10px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.path-label{color:var(--lw-muted);font-size:10px}.context-row{background:#fafbfc}.item-table td{padding:11px 14px}.item-table td:not(.title){white-space:nowrap}.item-table td.progress{white-space:normal}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:760px){.control{flex:1 1 130px;justify-content:space-between}.control select{max-width:none;flex:1;min-width:0}.control input{width:auto;min-width:0;flex:1}.list-options .control{flex:0 1 170px}.item-table td.title{min-width:210px}.item-table td.progress{min-width:160px}}
.extra-filters{margin-bottom:12px;padding:9px 0 3px;border-top:1px solid var(--lw-line);border-bottom:1px solid var(--lw-line)}.filter-fields{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.filter-summary{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px;color:var(--lw-sub);font-size:11px}.filter-summary span{overflow-wrap:anywhere}.extra-filters .date-filters{margin-top:10px;margin-bottom:8px}
@media(max-width:760px){.item-table th:first-child,.item-table td.title{position:sticky;left:0;z-index:1;background:#fff}.item-table th:first-child{z-index:2;background:#fbfcfd}.item-table .context-row td.title{background:#fafbfc}}
</style>

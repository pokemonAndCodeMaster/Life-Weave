<script setup lang="ts">
import type { OutputCatalogFile } from '../../api/outputFiles'
import type { FileTreeNode } from './workOutputCatalog'
import { statusLabels } from './workOutputCatalog'

const props = defineProps<{ node: FileTreeNode; expanded: string[]; forceOpen: boolean; selectedPath: string | null }>()
const emit = defineEmits<{ toggle: [path: string]; open: [file: OutputCatalogFile] }>()
const isOpen = () => props.forceOpen || props.expanded.includes(props.node.path)
</script>

<template>
  <li class="tree-entry">
    <template v-if="node.file">
      <button type="button" class="file-button" :class="{ selected: selectedPath === node.file.path }" :aria-current="selectedPath === node.file.path ? 'true' : undefined" @click="emit('open', node.file)">
        <span class="file-name">{{ node.name }}</span>
        <span class="file-meta">{{ statusLabels[node.file.status] }}<template v-if="node.file.status === 'renamed' && node.file.previousPath"> · 原 {{ node.file.previousPath }}</template><template v-if="node.file.binary"> · 二进制 · {{ node.file.size }} 字节</template><template v-else-if="node.file.additions !== null || node.file.deletions !== null"> · +{{ node.file.additions ?? 0 }} / −{{ node.file.deletions ?? 0 }}</template></span>
      </button>
    </template>
    <template v-else>
      <button type="button" class="folder-button" :aria-expanded="isOpen()" @click="emit('toggle', node.path)">
        <span aria-hidden="true">{{ isOpen() ? '▾' : '▸' }}</span><span class="folder-name">{{ node.name }}</span><small>{{ node.totals.count }} 文件<template v-if="node.totals.additions || node.totals.deletions"> · +{{ node.totals.additions }} / −{{ node.totals.deletions }}</template></small>
      </button>
      <ul v-if="isOpen()" class="tree-children">
        <WorkFileTree v-for="child in node.children" :key="child.path" :node="child" :expanded="expanded" :force-open="forceOpen" :selected-path="selectedPath" @toggle="emit('toggle', $event)" @open="emit('open', $event)" />
      </ul>
    </template>
  </li>
</template>

<style scoped>
.tree-entry { list-style: none; min-width: 0; }
.tree-children { margin: 0 0 0 13px; padding: 0 0 0 10px; border-inline-start: 1px solid #dce6ef; }
.folder-button,.file-button { width: 100%; display: flex; flex-wrap: wrap; align-items: baseline; gap: 5px 9px; padding: 7px 8px; border: 0; border-radius: 6px; text-align: start; background: none; color: #294860; cursor: pointer; min-width: 0; }
.folder-button:hover,.folder-button:focus-visible,.file-button:hover,.file-button:focus-visible { background: #edf5fb; outline: 2px solid #6398c5; outline-offset: -2px; }
.file-button.selected { background: #e9f3fb; }
.folder-name,.file-name { overflow-wrap: anywhere; font-size: 13px; }
.folder-name { font-weight: 650; }
.folder-button small,.file-meta { color: #607b91; font-size: 11px; overflow-wrap: anywhere; }
</style>

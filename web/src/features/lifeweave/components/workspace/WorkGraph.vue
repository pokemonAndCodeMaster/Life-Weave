<script setup lang="ts">
import { computed } from 'vue'
import type { WorkStep } from '../../api/workView'
import { layoutWorkGraph, stepStateLabel } from './workGraphLayout'

const props = defineProps<{ nodes: WorkStep[]; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: string] }>()
const layout = computed(() => layoutWorkGraph(props.nodes))
const titles = computed(() => new Map(props.nodes.map(node => [node.id, node.title])))
</script>

<template>
  <div class="graph-desktop" role="group" aria-label="工作步骤依赖图">
    <div class="graph-scroll">
      <div class="graph-canvas" :style="{ width: `${layout.width}px`, height: `${layout.height}px` }">
        <svg class="graph-lines" :width="layout.width" :height="layout.height" aria-hidden="true">
          <defs><marker id="lw-work-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" fill="#9db0c4" /></marker></defs>
          <path v-for="edge in layout.edges" :key="`${edge.from}:${edge.to}`" :d="edge.path" class="graph-line" marker-end="url(#lw-work-arrow)" />
        </svg>
        <button v-for="node in layout.nodes" :key="node.step.id" type="button" class="graph-node"
          :class="[{ selected: node.step.id === selectedId }, `state-${node.step.state}`]"
          :style="{ left: `${node.x}px`, top: `${node.y}px` }" :aria-pressed="node.step.id === selectedId"
          :aria-label="`${node.step.title}，${stepStateLabel[node.step.state]}${node.step.dependsOn.length ? `，依赖 ${node.step.dependsOn.map(id => titles.get(id) || id).join('、')}` : ''}`"
          @click="emit('select', node.step.id)">
          <span class="node-title" :title="node.step.title">{{ node.step.title }}</span><span class="node-state">{{ stepStateLabel[node.step.state] }}</span>
        </button>
      </div>
    </div>
  </div>
  <ol class="graph-mobile" aria-label="工作步骤与依赖">
    <li v-for="node in layout.nodes" :key="node.step.id">
      <button type="button" class="mobile-node" :class="{ selected: node.step.id === selectedId }" :aria-pressed="node.step.id === selectedId" @click="emit('select', node.step.id)">
        <span class="mobile-head"><strong>{{ node.step.title }}</strong><small>{{ stepStateLabel[node.step.state] }}</small></span>
        <span v-if="node.step.dependsOn.length" class="mobile-deps">依赖：{{ node.step.dependsOn.map(id => titles.get(id) || id).join('、') }}</span>
      </button>
    </li>
  </ol>
</template>

<style scoped>
.graph-desktop { min-width: 0; max-width: 100%; }
.graph-scroll { overflow: auto; border: 1px solid #e4e9ef; border-radius: 12px; background: #f9fbfd; }
.graph-canvas { position: relative; min-width: 100%; }
.graph-lines { position: absolute; inset: 0; pointer-events: none; }
.graph-line { fill: none; stroke: #9db0c4; stroke-width: 1.8; }
.graph-node { position: absolute; width: 248px; min-height: 76px; padding: 12px 14px; text-align: left; display: grid; gap: 4px; border: 1px solid #d8e1eb; border-left: 3px solid #7694b7; border-radius: 10px; background: #fff; color: #243446; cursor: pointer; box-shadow: 0 2px 8px #263b570d; }
.graph-node:hover,.graph-node:focus-visible,.mobile-node:hover,.mobile-node:focus-visible { outline: 2px solid #6f98c5; outline-offset: 2px; }
.graph-node.selected { border-color: #537da9; border-left-color: #376a9f; box-shadow: 0 0 0 2px #c5d9ed; }
.graph-node.state-succeeded { border-left-color: #5b9a86; }
.graph-node.state-failed { border-left-color: #ba706b; }
.graph-node.state-running { border-left-color: #537da9; }
.node-title { overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow-wrap: anywhere; font-size: 14px; font-weight: 680; line-height: 1.35; }
.node-state { color: #54708e; font-size: 11px; }
.graph-mobile { display: none; list-style: none; padding: 0; margin: 0; }
.graph-mobile li + li { margin-top: 10px; }
.mobile-node { width: 100%; padding: 12px 14px; text-align: left; display: grid; gap: 5px; border: 1px solid #d8e1eb; border-radius: 10px; background: #fff; }
.mobile-node.selected { border-color: #537da9; box-shadow: inset 3px 0 #537da9; }
.mobile-head { display: flex; justify-content: space-between; gap: 10px; }
.mobile-head strong { min-width: 0; overflow-wrap: anywhere; }
.mobile-head small { flex-shrink: 0; }
.mobile-deps { overflow-wrap: anywhere; }
.mobile-head small,.mobile-deps { font-size: 12px; color: #61758a; }
@media (max-width: 720px) { .graph-desktop { display: none; } .graph-mobile { display: block; } }
</style>

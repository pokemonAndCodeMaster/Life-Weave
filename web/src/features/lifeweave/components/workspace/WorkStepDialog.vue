<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, useTemplateRef, watch } from 'vue'
import type { WorkStep } from '../../api/workView'
import { stepStateLabel } from './workGraphLayout'

const props = defineProps<{ workspace: string; itemId: string; node: WorkStep; nodes: WorkStep[] }>()
const emit = defineEmits<{ close: []; select: [id: string] }>()
const panel = useTemplateRef<HTMLElement>('panel')
const closeButton = useTemplateRef<HTMLButtonElement>('closeButton')
const body = useTemplateRef<HTMLElement>('body')
const returnTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null
const previousOverflow = document.body.style.overflow
const focusableSelector = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
const predecessors = computed(() => props.nodes.filter(step => props.node.dependsOn.includes(step.id)))
const successors = computed(() => props.nodes.filter(step => step.dependsOn.includes(props.node.id)))

function focus() { closeButton.value?.focus({ preventScroll: true }) }
function scrollKey(id: string) { return `lifeweave:step-scroll:${props.workspace}:${props.itemId}:${id}` }
function rememberScroll(id: string) {
  if (!body.value) return
  try { sessionStorage.setItem(scrollKey(id), String(body.value.scrollTop)) }
  catch { /* Keep the current reading position while this view stays mounted. */ }
}
function restoreScroll(id: string) {
  if (!body.value) return
  try { body.value.scrollTop = Number(sessionStorage.getItem(scrollKey(id)) || 0) }
  catch { body.value.scrollTop = 0 }
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); emit('close'); return }
  if (event.key !== 'Tab' || !panel.value) return
  const controls = [...panel.value.querySelectorAll<HTMLElement>(focusableSelector)]
    .filter(element => element.getClientRects().length > 0 && !element.closest('[hidden]'))
  if (!controls.length) { event.preventDefault(); panel.value.focus(); return }
  const first = controls[0]!
  const last = controls.at(-1)!
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
watch(() => props.node.id, async (id, oldId) => { rememberScroll(oldId); await nextTick(); restoreScroll(id); focus() })
onMounted(async () => { document.body.style.overflow = 'hidden'; await nextTick(); restoreScroll(props.node.id); focus() })
onBeforeUnmount(() => {
  rememberScroll(props.node.id)
  document.body.style.overflow = previousOverflow
  if (returnTarget?.isConnected) returnTarget.focus({ preventScroll: true })
})
</script>

<template>
  <Teleport to="body">
    <div class="step-backdrop" role="presentation" @mousedown.self="emit('close')">
      <section id="work-step-detail" ref="panel" class="step-dialog" role="dialog" aria-modal="true" aria-labelledby="step-dialog-title" tabindex="-1" @keydown="onKeydown">
        <header class="step-dialog-head">
          <div class="step-title"><span>{{ stepStateLabel[node.state] }}</span><h2 id="step-dialog-title">{{ node.title }}</h2></div>
          <button ref="closeButton" class="lw-btn ghost sm" type="button" aria-label="关闭步骤详情" @click="emit('close')">关闭</button>
        </header>
        <nav v-if="predecessors.length || successors.length" class="step-relations" aria-label="相邻工作步骤">
          <div v-if="predecessors.length"><span>依赖步骤</span><button v-for="step in predecessors" :key="step.id" type="button" @click="emit('select', step.id)">{{ step.title }}</button></div>
          <div v-if="successors.length"><span>后续步骤</span><button v-for="step in successors" :key="step.id" type="button" @click="emit('select', step.id)">{{ step.title }}</button></div>
        </nav>
        <div ref="body" class="step-dialog-body" @scroll.passive="rememberScroll(node.id)"><slot /></div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.step-backdrop { position: fixed; inset: 0; z-index: 120; display: grid; place-items: center; padding: 18px; background: #182b40a8; }
.step-dialog { display: flex; flex-direction: column; width: min(1120px, 100%); max-height: min(90dvh, 950px); min-height: min(620px, 90dvh); overflow: hidden; border: 1px solid #bdd0df; border-radius: 14px; background: #fff; box-shadow: 0 25px 80px #10223550; }
.step-dialog:focus { outline: none; }
.step-dialog-head { flex: none; display: flex; justify-content: space-between; align-items: start; gap: 18px; padding: 16px 22px; border-bottom: 1px solid #dce6ee; background: #fff; }
.step-title { min-width: 0; }
.step-title span { color: #547b9a; font-size: 12px; }
.step-title h2 { margin: 3px 0 0; color: #233d52; font-size: clamp(18px, 2vw, 23px); overflow-wrap: anywhere; }
.step-relations { flex: none; display: flex; flex-wrap: wrap; gap: 5px 24px; padding: 8px 22px; border-bottom: 1px solid #e7eef4; background: #fafcfe; }
.step-relations div { display: flex; align-items: center; flex-wrap: wrap; gap: 5px 8px; }
.step-relations span { color: #637e92; font-size: 11px; }
.step-relations button { border: 0; border-radius: 5px; padding: 5px 7px; color: #315f85; background: #eaf3fa; font-size: 12px; cursor: pointer; }
.step-relations button:hover,.step-relations button:focus-visible { outline: 2px solid #5994c2; outline-offset: 1px; }
.step-dialog-body { flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; padding: 22px; }
@media(max-width:720px){ .step-backdrop { padding: 0; } .step-dialog { width: 100%; max-height: 100dvh; min-height: 100dvh; border-radius: 0; border: 0; } .step-dialog-head { padding: 14px 16px; } .step-relations { padding: 8px 16px; } .step-dialog-body { padding: 16px; } }
</style>

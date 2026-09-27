<script setup lang="ts">
import { computed, nextTick, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import LoadingState from '../components/LoadingState.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ItemContextTab from '../components/ItemContextTab.vue'
import ItemActivityTab from '../components/ItemActivityTab.vue'
import ItemRetroTab from '../components/ItemRetroTab.vue'
import WorkContinuationPanel from '../components/WorkContinuationPanel.vue'
import NextReviewEditor from '../components/conversation/NextReviewEditor.vue'
import DevelopmentPanel from '../components/DevelopmentPanel.vue'
import WorkGraph from '../components/workspace/WorkGraph.vue'
import WorkNodeDetail from '../components/workspace/WorkNodeDetail.vue'
import WorkPlanEditor from '../components/workspace/WorkPlanEditor.vue'
import WorkspaceOutputs from '../components/workspace/WorkspaceOutputs.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import { useItemWorkView } from '../composables/useItemWorkView'
import type { WorkStep } from '../api/workView'
import type { ItemTab } from '../types'

const route = useRoute()
const router = useRouter()
const { activeWorkspace, loading, error, itemDetails, rootOf, loadItem, openModal, notify } = useLifeWeaveWorkspace()
const itemId = computed(() => String(route.params.itemId ?? ''))
const item = computed(() => itemDetails.value[itemId.value])
const rootItem = computed(() => item.value ? rootOf(item.value) : undefined)
const tab = computed<ItemTab>(() => (['overview', 'context', 'outputs', 'activity', 'retro', 'development'].includes(String(route.params.tab)) ? route.params.tab : 'overview') as ItemTab)
const secondary = computed(() => !['overview', 'outputs'].includes(tab.value))
const { view, loading: viewLoading, error: viewError, saving, conflict, refresh: refreshWork, save: saveWork } = useItemWorkView(activeWorkspace, itemId)
const selectedNodeId = computed(() => typeof route.query.step === 'string' ? route.query.step : null)
const graph = shallowRef<InstanceType<typeof WorkGraph> | null>(null)
const nodeDetail = shallowRef<InstanceType<typeof WorkNodeDetail> | null>(null)
const selectedOutputId = shallowRef<string | null>(null)
const editingPlan = shallowRef(false)
const planEditor = shallowRef<InstanceType<typeof WorkPlanEditor> | null>(null)
const editorReset = shallowRef(0)
const selectedNode = computed<WorkStep | null>(() => view.value?.plan.nodes.find(node => node.id === selectedNodeId.value) || null)
const primaryOutput = computed(() => view.value?.outputs[0] || null)
function shortSummary(value: string | null | undefined): string {
  const plain = (value || '').replace(/!?(\[[^\]]*\])\([^)]*\)/g, '$1').replace(/[*`#]/g, '').replace(/\s+/g, ' ').trim()
  return plain.length > 120 ? `${plain.slice(0, 120)}…` : plain
}
function providerLabel(provider: string): string {
  return ({ manual: '人工', research: '研究方法', development: '开发 Agent', observed: '实际记录' } as Record<string, string>)[provider] || provider
}

watch([() => activeWorkspace.value, itemId], ([, id]) => {
  selectedOutputId.value = null
  editingPlan.value = false
  if (id) void loadDetail(id)
}, { immediate: true })
watch(() => view.value?.outputs, outputs => {
  if (!outputs?.length) { selectedOutputId.value = null; return }
  if (!outputs.some(output => output.id === selectedOutputId.value)) selectedOutputId.value = outputs[0]!.id
})

async function loadDetail(id: string) {
  const workspace = activeWorkspace.value
  const detail = await loadItem(id)
  if (workspace !== activeWorkspace.value || id !== itemId.value) return
  if (detail?.parentId && !itemDetails.value[detail.parentId]) await loadItem(detail.parentId, true)
}
function setTab(value: ItemTab) {
  void router.push({ path: '/lifeweave/' + activeWorkspace.value + '/items/' + encodeURIComponent(itemId.value) + '/' + value, query: route.query })
}
async function selectNode(id: string) {
  await router.push({ query: { ...route.query, step: id } })
  await nextTick()
  nodeDetail.value?.focus()
}
async function closeNode() {
  const id = selectedNodeId.value
  const { step: _step, ...query } = route.query
  await router.push({ query })
  await nextTick()
  if (id) graph.value?.focusNode(id)
}
async function editSelectedNode() {
  editingPlan.value = true
  await nextTick()
  if (selectedNodeId.value) planEditor.value?.focusStep(selectedNodeId.value)
}
function delegateCurrentItem() {
  if (!item.value || !rootItem.value) return
  if (rootItem.value.context.established) openModal('delegate', { item: item.value })
  else openModal('context-establish', { item: rootItem.value })
}
function quoteForConversation(quote: { text: string; runId: string | null; anchor: string }) {
  try { sessionStorage.setItem('lifeweave:quote:' + activeWorkspace.value + ':' + itemId.value, JSON.stringify(quote)) }
  catch { notify('浏览器未能保存引用，请复制段落后打开对话继续。'); return }
  void router.push({ path: '/lifeweave/' + activeWorkspace.value + '/conversation', query: { itemId: itemId.value, mode: 'discuss' } })
}
function selectOutput(id: string) { selectedOutputId.value = id; setTab('outputs') }
async function savePlan(value: { version: number; title: string; provider: string; nodes: WorkStep[] }) {
  if (await saveWork(value)) { editingPlan.value = false; await loadDetail(itemId.value) }
}
async function reloadEditor() { if (await refreshWork()) editorReset.value += 1 }
async function refreshAll() { await Promise.all([loadDetail(itemId.value), refreshWork()]) }
</script>

<template>
  <LoadingState v-if="!item" :loading="loading" :error="error?.message" empty="找不到这个事项。" @retry="loadDetail(itemId)" />
  <div v-else-if="rootItem" class="item-workspace">
    <PageHeader :title="item.title" subtitle="" :eyebrow="'事项 · ' + item.kind">
      <RouterLink class="lw-btn primary" :to="{ path: '/lifeweave/' + activeWorkspace + '/conversation', query: { itemId } }">继续讨论</RouterLink>
      <button type="button" class="lw-btn" @click="delegateCurrentItem">{{ rootItem.context.established ? '委托 AI' : '先建立上下文' }}</button>
    </PageHeader>
    <div class="workspace-meta"><span>事项状态 <StatusBadge :value="item.state" /></span><span>{{ item.owner === 'local-user' ? '我' : item.owner }}</span><span v-if="item.due">目标 {{ item.due }}</span><span v-if="item.parentId">子事项 · 继承上层背景</span><button type="button" class="meta-action" @click="openModal('relations', { item })">关系</button></div>
    <details v-if="item.goal" class="item-description"><summary>事项说明</summary><p>{{ item.goal }}</p></details>
    <nav class="workspace-nav" aria-label="事项内容"><button type="button" :class="{ active: tab === 'overview' }" :aria-current="tab === 'overview' ? 'page' : undefined" @click="setTab('overview')">概览</button><button type="button" :class="{ active: tab === 'outputs' }" :aria-current="tab === 'outputs' ? 'page' : undefined" @click="setTab('outputs')">成果 <span v-if="view?.outputs.length">{{ view.outputs.length }}</span></button><details class="secondary-nav" :open="secondary || undefined"><summary>背景与历史</summary><div class="secondary-links"><button type="button" :class="{ active: tab === 'context' }" @click="setTab('context')">背景</button><button type="button" :class="{ active: tab === 'activity' }" @click="setTab('activity')">过程记录</button><button type="button" :class="{ active: tab === 'retro' }" @click="setTab('retro')">复盘</button><button v-if="item.itemType === 'requirement' || item.itemType === 'fix'" type="button" :class="{ active: tab === 'development' }" @click="setTab('development')">开发配置与历史</button></div></details><button type="button" class="refresh-action" @click="refreshAll">刷新</button></nav>
    <main class="workspace-main">
      <template v-if="tab === 'overview'">
        <p v-if="viewError" role="alert" class="lw-notice warning">{{ viewError }} <button type="button" class="lw-btn sm" @click="refreshWork()">重试</button></p>
        <div v-if="viewLoading && !view" class="loading-block" role="status">正在读取当前工作…</div>
        <template v-else-if="view">
          <section class="current-situation" aria-label="当前局面"><div class="situation-head"><div><span class="section-kicker">当前局面</span><h2>{{ view.current.label }}</h2></div></div><p v-if="view.current.summary && view.current.summary !== view.current.label">{{ shortSummary(view.current.summary) }}</p><span v-if="view.current.updatedAt" class="updated-at">更新于 {{ new Date(view.current.updatedAt).toLocaleString('zh-CN') }}</span></section>
          <section class="work-section" aria-label="工作步骤"><div class="section-head"><div><span class="section-kicker">步骤图</span><h2>{{ view.plan.title || '工作步骤' }}</h2><p v-if="view.plan.source !== 'empty'">{{ view.plan.source === 'observed' ? '来自实际记录' : '已声明计划' }}<template v-if="view.plan.provider !== 'observed'"> · {{ providerLabel(view.plan.provider) }}</template></p></div><button type="button" class="lw-btn sm" @click="editingPlan = !editingPlan">{{ editingPlan ? '收起编辑' : view.plan.source === 'observed' ? '另存为可编辑计划' : '编辑步骤' }}</button></div>
            <div v-if="view.plan.nodes.length" class="graph-and-detail"><WorkGraph ref="graph" :nodes="view.plan.nodes" :selected-id="selectedNodeId" @select="selectNode" /><p v-if="!selectedNode" class="graph-hint">点击步骤，展开本步内容与产物。</p><WorkNodeDetail v-if="selectedNode" ref="nodeDetail" :workspace="activeWorkspace" :item-id="itemId" :node="selectedNode" :nodes="view.plan.nodes" :outputs="view.outputs" :observed="view.plan.source === 'observed'" @output="selectOutput" @run="openModal('run-detail', { runId: $event })" @edit="editSelectedNode" @close="closeNode" @select="selectNode" @context="setTab('context')" @updated="refreshAll" @quote="quoteForConversation" /></div>
            <div v-else class="empty-plan"><strong>还没有步骤记录</strong><p>可以登记一两步当前真正要做的事；页面不会据此自动启动 Agent。</p><button type="button" class="lw-btn sm" @click="editingPlan = true">添加第一步</button></div>
            <WorkPlanEditor v-if="editingPlan" ref="planEditor" :view="view" :outputs="view.outputs" :saving="saving" :error="viewError" :conflict="conflict" :reset-key="editorReset" @save="savePlan" @cancel="editingPlan = false" @reload="reloadEditor" />
          </section>
          <section class="current-output" aria-label="主要成果"><div><span class="section-kicker">主要成果</span><h2>{{ primaryOutput?.title || '尚无成果' }}</h2><p>{{ shortSummary(primaryOutput?.summary) || '人工工作与 AI 委托的成果会在同一目录中出现。' }}</p></div><button type="button" class="lw-btn sm" @click="primaryOutput ? selectOutput(primaryOutput.id) : setTab('outputs')">{{ primaryOutput ? '阅读成果' : '登记或查看成果' }}</button></section>
          <details v-if="view.warnings.length" class="workspace-background"><summary>记录边界与提醒（{{ view.warnings.length }}）</summary><ul><li v-for="warning in view.warnings" :key="warning">{{ warning }}</li></ul></details>
        </template>
      </template>
      <template v-else-if="tab === 'outputs'"><p v-if="viewError" role="alert" class="lw-notice warning">{{ viewError }} <button type="button" class="lw-btn sm" @click="refreshWork()">重试</button></p><div v-if="viewLoading && !view" class="loading-block">正在读取成果目录…</div><WorkspaceOutputs v-else-if="view" :key="activeWorkspace + ':' + itemId" :workspace="activeWorkspace" :item="item" :view="view" :selected-id="selectedOutputId" @select="selectedOutputId = $event" @updated="refreshAll" @quote="quoteForConversation" /></template>
      <template v-else-if="tab === 'context'"><ItemContextTab :item="item" :root-item="rootItem" /><details class="secondary-section"><summary>安排下一步</summary><WorkContinuationPanel :workspace="activeWorkspace" :item-id="itemId" @saved="loadDetail(itemId)" /><NextReviewEditor :workspace="activeWorkspace" :item="item" @saved="loadDetail(itemId)" /></details></template>
      <ItemActivityTab v-else-if="tab === 'activity'" :item="item" :root-item="rootItem" />
      <ItemRetroTab v-else-if="tab === 'retro'" :item="item" :root-item="rootItem" />
      <DevelopmentPanel v-else :key="activeWorkspace + ':' + itemId + ':development'" :workspace="activeWorkspace" :item-id="itemId" :initial-instruction="item.goal" />
    </main>
  </div>
</template>

<style scoped>
.item-workspace { min-width: 0; }
.workspace-meta { display: flex; align-items: center; gap: 11px; flex-wrap: wrap; margin: 2px 0 16px; color: #677a8e; font-size: 12px; }
.item-description { margin: -5px 0 16px; color: #61758b; font-size: 12px; }
.item-description summary { cursor: pointer; width: fit-content; }
.item-description p { max-width: 90ch; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.meta-action { border: 0; background: none; color: #476d94; cursor: pointer; padding: 4px 0; }
.workspace-nav { display: flex; gap: 5px; align-items: center; border-bottom: 1px solid #dce5ed; margin-bottom: 20px; }
.workspace-nav > button,.secondary-nav summary,.secondary-links button { border: 0; background: none; padding: 12px 15px; color: #61758b; cursor: pointer; font-size: 13px; white-space: nowrap; }
.workspace-nav > button.active,.secondary-links button.active { color: #285b8d; box-shadow: inset 0 -2px #4c83b6; font-weight: 650; }
.workspace-nav > button:hover,.secondary-nav summary:hover,.secondary-links button:hover { color: #285b8d; }
.workspace-nav .refresh-action { margin-left: auto; font-size: 12px; }
.secondary-nav { position: relative; }
.secondary-nav summary { list-style: none; }
.secondary-nav summary::-webkit-details-marker { display: none; }
.secondary-nav summary::after { content: '⌄'; margin-left: 7px; }
.secondary-links { position: absolute; z-index: 5; top: 100%; left: 0; min-width: 170px; display: grid; padding: 5px; border: 1px solid #dce5ed; border-radius: 9px; background: #fff; box-shadow: 0 10px 25px #2334491a; }
.secondary-links button { text-align: left; border-radius: 5px; padding: 10px 11px; }
.secondary-links button.active { box-shadow: inset 3px 0 #4c83b6; }
.workspace-main { max-width: 1380px; display: grid; gap: 19px; min-width: 0; }
.loading-block { padding: 32px; color: #60758b; border: 1px solid #e0e7ed; border-radius: 10px; }
.current-situation,.work-section,.current-output { border: 1px solid #e1e8ee; background: #fff; border-radius: 12px; padding: 21px 23px; min-width: 0; }
.current-situation { border-left: 4px solid #648eb7; }
.situation-head,.section-head,.current-output { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.section-kicker { color: #597b9d; font-size: 11px; letter-spacing: .04em; }
.situation-head h2,.section-head h2,.current-output h2 { margin: 5px 0 0; font-size: 19px; color: #263a4f; }
.current-situation p,.current-output p { margin: 11px 0 0; line-height: 1.65; color: #35495e; white-space: pre-wrap; }
.section-head p,.updated-at { display: block; margin-top: 6px; color: #748497; font-size: 11px; }
.graph-hint { margin: 0; color: #6c8295; font-size: 12px; }
.graph-and-detail { display: grid; gap: 14px; margin-top: 16px; min-width: 0; }
.empty-plan { margin-top: 16px; padding: 22px; border: 1px dashed #cbd9e6; border-radius: 9px; background: #f9fbfd; }
.empty-plan p { color: #62788d; font-size: 13px; }
.work-section :deep(.plan-editor) { margin-top: 16px; }
.current-output { align-items: center; }
.current-output h2 { font-size: 16px; }
.workspace-background,.secondary-section { padding: 14px 18px; border: 1px solid #e2e9f0; border-radius: 10px; background: #fff; }
.workspace-background summary,.secondary-section summary { cursor: pointer; color: #537391; font-size: 12px; }
.secondary-section { display: grid; gap: 15px; }
@media(max-width:720px){ .workspace-nav { overflow-x: auto; } .workspace-nav > button,.secondary-nav summary { padding: 11px 9px; } .current-situation,.work-section,.current-output { padding: 16px; } .current-output,.section-head { flex-wrap: wrap; } .secondary-links { position: fixed; top: auto; left: 20px; right: 20px; } }
</style>

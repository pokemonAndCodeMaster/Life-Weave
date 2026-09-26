<script setup lang="ts">
import { computed, watch, shallowRef, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import ItemActivityTab from '../components/ItemActivityTab.vue'
import ItemContextTab from '../components/ItemContextTab.vue'
import ItemOutputsTab from '../components/ItemOutputsTab.vue'
import ItemOverviewTab from '../components/ItemOverviewTab.vue'
import ItemRetroTab from '../components/ItemRetroTab.vue'
import LoadingState from '../components/LoadingState.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import WorkContinuationPanel from '../components/WorkContinuationPanel.vue'
import ResearchOutputPanel from '../components/ResearchOutputPanel.vue'
import ResearchKnowledgeReview from '../components/ResearchKnowledgeReview.vue'
import NextReviewEditor from '../components/conversation/NextReviewEditor.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import {listRuns} from '../api/lifeweave'
import type {LifeWeaveRun} from '../types'
import type { ItemTab } from '../types'

const route = useRoute()
const router = useRouter()
const { activeWorkspace, loading, error, itemDetails, rootOf, loadItem, openModal, notify } = useLifeWeaveWorkspace()
const itemId = computed(() => String(route.params.itemId ?? ''))
const item = computed(() => itemDetails.value[itemId.value])
const rootItem = computed(() => item.value ? rootOf(item.value) : undefined)
const tab = computed(() => (['overview', 'context', 'outputs', 'activity', 'retro'].includes(String(route.params.tab)) ? route.params.tab : 'overview') as ItemTab)
const tabs: Array<{ key: ItemTab; label: string }> = [
  { key: 'overview', label: '概览' }, { key: 'context', label: '共享上下文' }, { key: 'outputs', label: '成果与验证' }, { key: 'activity', label: '推进记录' }, { key: 'retro', label: '复盘与成长' },
]
const itemRuns=shallowRef<LifeWeaveRun[]>([])
const researchRefresh = shallowRef(0)
function quoteForConversation(quote: { text: string; runId: string | null; anchor: string }) {
  try { sessionStorage.setItem(`lifeweave:quote:${activeWorkspace.value}:${itemId.value}`, JSON.stringify(quote)) }
  catch { notify('浏览器未能保存引用，请复制段落后打开对话继续。'); return }
  void router.push({ path: `/lifeweave/${activeWorkspace.value}/conversation`, query: { itemId: itemId.value } })
}
let runTimer:ReturnType<typeof setTimeout>|undefined;let mounted=true;let runGeneration=0
async function refreshItemRuns(ticket:number){
 const workspace=activeWorkspace.value;const id=itemId.value
 try{const rows=await listRuns(workspace,{itemId:id,limit:100});if(mounted&&ticket===runGeneration)itemRuns.value=rows}catch{/* The global API error remains visible; retry on next poll. */}
 if(mounted&&ticket===runGeneration)runTimer=setTimeout(()=>void refreshItemRuns(ticket),4000)
}
onBeforeUnmount(()=>{mounted=false;runGeneration++;clearTimeout(runTimer)})

async function loadDetail(id: string) {
  const detail = await loadItem(id)
  if (detail?.parentId && !itemDetails.value[detail.parentId]) await loadItem(detail.parentId, true)
}

function setTab(value: string) {
  router.push(`/lifeweave/${activeWorkspace.value}/items/${encodeURIComponent(itemId.value)}/${value}`)
}

function delegateCurrentItem() {
  if (!item.value || !rootItem.value) return
  if (rootItem.value.context.established) openModal('delegate', { item: item.value })
  else openModal('context-establish', { item: rootItem.value })
}

watch([itemId,activeWorkspace], ([id]) => {runGeneration++;clearTimeout(runTimer);itemRuns.value=[];if(id){void loadDetail(id);void refreshItemRuns(runGeneration)}}, { immediate: true })
watch(() => itemRuns.value.map(run => `${run.id}:${run.state}`).join('|'), (value, previous) => { if (value !== previous) researchRefresh.value++ })
</script>

<template>
  <LoadingState v-if="!item" :loading="loading" :error="error?.message" empty="找不到这个事项。" @retry="loadDetail(itemId)" />
  <template v-else-if="rootItem">
    <PageHeader :title="item.title" :subtitle="item.goal" :eyebrow="`${item.id} / ${item.kind}`">
      <RouterLink class="lw-btn primary" :to="{ path: `/lifeweave/${activeWorkspace}/conversation`, query: { itemId } }"><LifeWeaveIcon name="message" />继续讨论这件事</RouterLink>
      <button class="lw-btn primary" type="button" @click="delegateCurrentItem"><LifeWeaveIcon :name="rootItem.context.established ? 'spark' : 'layers'" />{{ rootItem.context.established ? '委托 AI' : '先建立上下文' }}</button>
      <RouterLink class="lw-btn" :to="{ path: `/lifeweave/${activeWorkspace}/conversation`, query: { itemId, mode: 'discuss' } }"><LifeWeaveIcon name="message" />就地讨论</RouterLink>
      <button class="lw-btn" type="button" @click="openModal('discussion', { item: rootItem })">记录讨论笔记</button>
    </PageHeader>
    <div class="lw-detail-meta"><StatusBadge :value="item.state" /><span class="lw-owner"><span class="lw-avatar" :class="{ me: item.owner === '我' }">{{ item.owner.slice(-1) }}</span>{{ item.owner }}</span><span>责任人</span><span>·</span><span>目标 {{ item.due || '未安排' }}</span><StatusBadge v-for="domain in item.domains" :key="domain" :value="domain" /><StatusBadge :value="`上下文 v${rootItem.context.revision}`" tone="blue" /><StatusBadge v-if="item.parentId" :value="`继承 ${rootItem.id} 的共同背景`" tone="purple" /><span class="lw-spacer"></span><button class="lw-btn ghost sm" type="button" @click="openModal('relations', { item })">编辑关系</button></div>
    <div class="lw-tabs">
      <button class="lw-tab" type="button" @click="loadDetail(itemId)">刷新记录</button>
      <button v-for="entry in tabs" :key="entry.key" class="lw-tab" :class="{ active: tab === entry.key }" type="button" @click="setTab(entry.key)">{{ entry.label }}<StatusBadge v-if="entry.key === 'context' && rootItem.context.proposals.length" :value="String(rootItem.context.proposals.length)" tone="amber" /></button>
    </div>
    <div class="lw-detail-layout">
      <section class="lw-detail-main" aria-label="事项内容">
        <ItemOverviewTab v-if="tab === 'overview'" :item="item" :root-item="rootItem" @tab="setTab" @feedback="openModal('feedback', { item, anchor: $event })" />
        <ItemContextTab v-else-if="tab === 'context'" :item="item" :root-item="rootItem" />
        <ItemOutputsTab v-else-if="tab === 'outputs'" :item="item" :runs="itemRuns" />
        <ItemActivityTab v-else-if="tab === 'activity'" :item="item" :root-item="rootItem" />
        <ItemRetroTab v-else :item="item" :root-item="rootItem" />
        <ResearchOutputPanel v-if="tab === 'overview' || tab === 'outputs'" :key="`${activeWorkspace}:${itemId}:output`" :workspace="activeWorkspace" :item-id="itemId" :refresh-key="researchRefresh" @quote="quoteForConversation" @feedback-saved="researchRefresh++" @candidate-created="researchRefresh++" />
        <ResearchKnowledgeReview v-if="tab === 'outputs'" :key="`${activeWorkspace}:${itemId}:knowledge`" :workspace="activeWorkspace" :item-id="itemId" :refresh-key="researchRefresh" @changed="researchRefresh++" />
        <WorkContinuationPanel v-if="tab === 'overview'" :workspace="activeWorkspace" :item-id="itemId" @saved="loadDetail(itemId)" />
      </section>
      <aside class="lw-detail-aside">
        <NextReviewEditor :key="`${activeWorkspace}:${itemId}:review`" :workspace="activeWorkspace" :item="item" @saved="loadDetail(itemId)" />
        <section class="lw-panel pad">
          <div class="lw-between"><h2>工作关系</h2><button class="lw-btn ghost icon-only" type="button" aria-label="编辑工作关系" @click="openModal('relations', { item })"><LifeWeaveIcon name="edit" /></button></div>
          <div class="lw-prop"><span>协调责任</span><div>{{ item.owner }}</div></div><div class="lw-prop"><span>参与者</span><div>{{ item.participants.join('、') || '未登记' }}</div></div><div class="lw-prop"><span>关联专题</span><div class="lw-chips"><StatusBadge v-for="topic in item.topics" :key="topic" :value="topic" /><span v-if="!item.topics.length" class="lw-muted">不要求关联</span></div></div><div class="lw-prop"><span>所属领域</span><div>{{ item.domains.join('、') || '未登记' }}</div></div><div class="lw-prop"><span>影响资产</span><div>{{ item.assets.join('、') || '未登记' }}</div></div>
          <div class="lw-link-capability">关系用于定位与汇总；同步与外部操作以连接能力为准。</div>
        </section>
        <section class="lw-panel pad"><h2>本事项的运行</h2><div v-for="run in itemRuns" :key="run.id" class="lw-note-card"><div class="lw-between"><span class="lw-mono">{{ run.id }}</span><StatusBadge :value="run.state" /></div><p>{{ run.instruction || run.result || '本次委托' }}</p><div class="lw-tiny lw-muted">{{ run.engine }} · {{ run.machine || '等待分配' }}<br />使用上下文 v{{ run.rev }}<span v-if="run.staleContext"> · 有新共识待决定</span></div><button class="lw-text-btn lw-mt-8" type="button" @click="openModal('run-detail', { runId: run.id })">查看运行与环境</button></div><p v-if="!itemRuns.length" class="lw-small lw-muted">尚未启动运行。记录与讨论不要求创建容器。</p></section>
        <section class="lw-panel pad"><h2>这不是一个共享聊天窗口</h2><p class="lw-small lw-sub">不同人和 Agent 使用自己的会话，共享当前确认的工作事实。候选经过采纳后才成为新共识。</p><button class="lw-btn ghost sm" type="button" @click="setTab('context')">查看上下文结构</button></section>
      </aside>
    </div>
  </template>
</template>

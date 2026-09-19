<script setup lang="ts">
import LifeWeaveIcon from './LifeWeaveIcon.vue'
import StatusBadge from './StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkItem } from '../types'

defineProps<{ item: WorkItem; rootItem: WorkItem }>()
const { openModal, decideProposal } = useLifeWeaveWorkspace()
</script>

<template>
  <div v-if="!rootItem.context.established" class="lw-notice warning lw-mb-18"><LifeWeaveIcon name="flag" /><div><strong>这个历史事项尚未建立共享上下文</strong><br />当前目标只是事项字段，不是已版本化共识。<button class="lw-btn sm lw-mt-8" type="button" @click="openModal('context-establish', { item: rootItem })">确认并建立 v1</button></div></div>
  <div v-else class="lw-notice lw-mb-18"><LifeWeaveIcon name="layers" /><div><strong>{{ rootItem.id }} 的持续上下文 · 当前 v{{ rootItem.context.revision }}</strong><br />人和 Agent 共同消费这些记录；各自会话只取本次需要的部分。</div></div>
  <article v-if="rootItem.context.established" class="lw-panel lw-article">
    <div class="lw-between"><h2>当前确认的理解</h2><button class="lw-btn" type="button" @click="openModal('proposal-create', { item: rootItem })"><LifeWeaveIcon name="edit" />提出修订</button></div>
    <div class="lw-fact-card"><div class="lw-fact-top"><h3>要解决的问题与目标</h3><StatusBadge value="当前共识" tone="green" /></div><p>{{ rootItem.context.goal }}</p><div class="lw-source-line">来源：本事项当前目标 · 版本历史保留形成依据</div></div>
    <div class="lw-fact-card"><div class="lw-fact-top"><h3>当前范围</h3><StatusBadge value="当前共识" tone="green" /></div><p>{{ rootItem.context.scope || '范围尚未说明。' }}</p></div>
    <div v-for="decision in rootItem.context.decisions" :key="decision.id ?? decision.title" class="lw-fact-card"><div class="lw-fact-top"><h3>{{ decision.title }}</h3><StatusBadge value="已确认" tone="green" /></div><p>{{ decision.body }}</p><div class="lw-between"><div class="lw-source-line">依据：{{ decision.source }}</div><button class="lw-text-btn" type="button" @click="openModal('feedback', { item: rootItem, anchor: decision.title })">就此讨论</button></div></div>
    <div class="lw-fact-card"><div class="lw-fact-top"><h3>仍然未知 / 尚未决定</h3><StatusBadge value="不伪装成事实" tone="amber" /></div><p v-for="unknown in rootItem.context.unknowns" :key="unknown" class="lw-small">{{ unknown }}</p><p v-if="!rootItem.context.unknowns.length" class="lw-small lw-muted">当前没有登记的未知项。</p></div>
  </article>
  <template v-if="rootItem.context.established">
    <div class="lw-section-title"><h2>待采纳的上下文变化</h2><StatusBadge :value="`${rootItem.context.proposals.length} 项`" tone="amber" /></div>
    <section v-for="proposal in rootItem.context.proposals" :key="proposal.id" class="lw-panel pad lw-mb-14">
      <div class="lw-between"><h3>{{ proposal.title }}</h3><StatusBadge value="候选" tone="amber" /></div>
      <div class="lw-diff-block"><div class="lw-diff-minus">− {{ proposal.old }}</div><div class="lw-diff-plus">+ {{ proposal.text }}</div></div>
      <div class="lw-source-line">{{ proposal.by }} · 根据 {{ proposal.source }}</div>
      <div class="lw-between lw-mt-14"><span class="lw-tiny lw-sub">采纳后形成 v{{ rootItem.context.revision + 1 }}，旧运行依据不会被改写。</span><div class="lw-inline"><button class="lw-btn sm" type="button" @click="decideProposal(rootItem, proposal.id, 'reject')">暂不采纳</button><button class="lw-btn primary sm" type="button" @click="decideProposal(rootItem, proposal.id, 'accept')">采纳此修改</button></div></div>
    </section>
    <div v-if="!rootItem.context.proposals.length" class="lw-panel lw-empty">没有待采纳修改。新的意见仍可继续进入讨论。</div>
  </template>
  <div class="lw-section-title"><h2>本次可引用的背景</h2></div>
  <div class="lw-panel pad">
    <div v-for="asset in rootItem.assets" :key="asset" class="lw-resource"><LifeWeaveIcon name="link" /><div class="lw-grow"><h3>{{ asset }}</h3><p>关联用于定位；读取和操作能力以连接状态为准。</p></div><StatusBadge value="关联" /></div>
    <div class="lw-resource"><LifeWeaveIcon name="history" /><div class="lw-grow"><h3>上下文版本与形成依据</h3><p>工作完成后仍保留，后续任务只引用相关部分。</p></div><button class="lw-btn sm" type="button" :disabled="!rootItem.context.established" @click="openModal('context-history', { item: rootItem })">版本历史</button></div>
  </div>
  <div class="lw-section-title"><h2>这个上下文如何被使用</h2></div>
  <div class="lw-context-map"><span>工作区 / 领域知识</span><b>→</b><span class="current">{{ rootItem.id }} · {{ rootItem.context.established ? `当前共识 v${rootItem.context.revision}` : '上下文未建立' }}</span><b>→</b><span>子工作关注点</span><b>→</b><span>一次运行的只读依据</span></div>
</template>

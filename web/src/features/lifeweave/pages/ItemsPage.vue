<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import ItemList from '../components/items/ItemList.vue'
import ItemOrganizationPanel from '../components/items/ItemOrganizationPanel.vue'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkItem } from '../types'

const { activeWorkspace, rootItems, state, actorName, openModal, savePreferences, load } = useLifeWeaveWorkspace()
const topicSelection = shallowRef<{ name: string } | null>(null)
const managingTopics = shallowRef(false)
const organizing = shallowRef(false)
const items = computed(() => state.value?.items ?? [])

function selectTopic(name: string) {
  topicSelection.value = { name }
  managingTopics.value = false
}
function peek(item: WorkItem) { openModal('peek', { item }) }
</script>

<template>
  <PageHeader title="工作事项" subtitle="跟进事项、查看子工作和关联专题。">
    <button class="lw-btn primary" type="button" @click="openModal('item-create')"><LifeWeaveIcon name="plus" />新建事项</button>
  </PageHeader>
  <div class="page-utility"><button class="lw-text-btn" type="button" :aria-expanded="organizing" @click="organizing = !organizing">{{ organizing ? '收起整理' : '整理事项' }}</button><button class="lw-text-btn" type="button" :aria-expanded="managingTopics" @click="managingTopics = !managingTopics">{{ managingTopics ? '收起专题管理' : '管理专题' }}</button></div>
  <ItemOrganizationPanel v-if="organizing" :workspace="activeWorkspace" @updated="load(activeWorkspace)" />
  <section v-if="managingTopics" class="topic-management" aria-label="专题管理">
    <div class="topic-heading"><h2>专题</h2><button class="lw-btn sm" type="button" @click="openModal('entity-create', { entityType: 'topic' })"><LifeWeaveIcon name="plus" />新建专题</button></div>
    <div v-if="state?.topics.length" class="topic-list">
      <div v-for="topic in state?.topics" :key="topic.id ?? topic.name" class="topic-row">
        <div class="topic-detail"><strong>{{ topic.name }}</strong><span>{{ topic.goal }}</span><span v-if="topic.endCondition">结束条件：{{ topic.endCondition }}</span><small>{{ topic.owner }} · 目标 {{ topic.due || '未安排' }} · {{ rootItems.filter((item) => item.topics.includes(topic.name)).length }} 项关联事项</small></div>
        <StatusBadge :value="topic.state || '进行中'" />
        <button class="lw-text-btn" type="button" @click="selectTopic(topic.name)">查看事项</button>
        <button class="lw-text-btn" type="button" @click="openModal('topic-edit', { topic })">编辑</button>
      </div>
    </div>
    <div v-else class="lw-empty">尚未建立专题。</div>
  </section>
  <ItemList :items="items" :actor="actorName" :workspace="activeWorkspace" :saved="state?.preferences ?? {}" :topic-selection="topicSelection" :save-view="savePreferences" @peek="peek" />
</template>

<style scoped>
.page-utility{display:flex;justify-content:flex-end;margin:-8px 0 10px}.topic-management{margin-bottom:18px;border:1px solid var(--lw-line);border-radius:6px;background:#fff}.topic-heading,.topic-row{display:flex;align-items:center;gap:13px;padding:12px 15px;border-bottom:1px solid var(--lw-line)}.topic-heading{justify-content:space-between;background:#fafbfd}.topic-heading h2{margin:0;font-size:13px}.topic-row:last-child{border-bottom:0}.topic-detail{display:grid;gap:3px;flex:1;min-width:0;font-size:12px}.topic-detail span{color:var(--lw-sub)}.topic-detail small{color:var(--lw-muted)}@media(max-width:760px){.topic-row{align-items:flex-start;flex-wrap:wrap}.topic-detail{flex-basis:100%}}
</style>

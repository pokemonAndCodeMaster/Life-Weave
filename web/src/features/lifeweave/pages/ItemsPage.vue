<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import type { WorkItem } from '../types'

const { activeWorkspace, rootItems, state, actorName, openModal, savePreferences } = useLifeWeaveWorkspace()
const view = shallowRef<'items' | 'topics'>('items')
const kind = shallowRef<'all' | 'mine'>(state.value?.preferences.kind ?? 'all')
const filter = shallowRef(state.value?.preferences.filter ?? '')
const group = shallowRef<'none' | 'topic' | 'domain'>(state.value?.preferences.group ?? 'none')
const query = shallowRef('')
const isTeam = computed(() => activeWorkspace.value === 'team')

const filtered = computed(() => rootItems.value.filter((item) => {
  if (kind.value === 'mine' && item.owner !== actorName.value) return false
  if (filter.value && !item.domains.includes(filter.value) && !item.topics.includes(filter.value)) return false
  const haystack = `${item.id} ${item.title} ${item.update}`.toLocaleLowerCase()
  return haystack.includes(query.value.trim().toLocaleLowerCase())
}))

const groups = computed(() => {
  const result = new Map<string, WorkItem[]>()
  for (const item of filtered.value) {
    const keys = group.value === 'topic' ? item.topics.length ? item.topics : ['未关联专题'] : group.value === 'domain' ? item.domains.length ? item.domains : ['未关联领域'] : ['全部事项']
    for (const key of keys) result.set(key, [...(result.get(key) ?? []), item])
  }
  return [...result.entries()]
})

const contributions = computed(() => (state.value?.items ?? []).filter((item) => item.parentId && item.owner === actorName.value))
const options = computed(() => [...(state.value?.domains ?? []), ...(state.value?.topics ?? []).map((topic) => topic.name)])

function itemUrl(id: string) {
  return `/lifeweave/${activeWorkspace.value}/items/${encodeURIComponent(id)}/overview`
}

function selectTopic(name: string) {
  view.value = 'items'
  filter.value = name
  group.value = 'none'
}
</script>

<template>
  <PageHeader title="工作事项" subtitle="事项只维护一份。专题表达阶段成果，领域表达长期关注范围。">
    <button class="lw-btn primary" type="button" @click="openModal('item-create')"><LifeWeaveIcon name="plus" />新建事项</button>
  </PageHeader>
  <div class="lw-tabs">
    <button class="lw-tab" :class="{ active: view === 'items' }" type="button" @click="view = 'items'">事项</button>
    <button class="lw-tab" :class="{ active: view === 'topics' }" type="button" @click="view = 'topics'">专题</button>
  </div>

  <template v-if="view === 'topics'">
    <div class="lw-notice neutral lw-mb-20"><LifeWeaveIcon name="flag" /><div>专题有一个阶段结果，也允许结束。长期关注范围属于领域。</div><span class="lw-spacer"></span><button class="lw-btn sm" type="button" @click="openModal('entity-create', { entityType: 'topic' })"><LifeWeaveIcon name="plus" />新建专题</button></div>
    <div class="lw-stack">
      <section v-for="topic in state?.topics" :key="topic.id ?? topic.name" class="lw-panel pad">
        <div class="lw-between">
          <div><div class="lw-eyebrow">阶段性项目 / 专题</div><h2>{{ topic.name }}</h2><p class="lw-small lw-sub">{{ topic.goal }}</p><p v-if="topic.endCondition" class="lw-tiny lw-muted">结束条件：{{ topic.endCondition }}</p></div>
          <div class="lw-inline">
            <button class="lw-btn sm" type="button" @click="openModal('topic-edit', { topic })"><LifeWeaveIcon name="edit" />编辑</button>
            <button class="lw-btn" type="button" @click="selectTopic(topic.name)">查看关联事项 <LifeWeaveIcon name="arrow" /></button>
          </div>
        </div>
        <div class="lw-inline lw-tiny lw-sub"><span class="lw-avatar">{{ topic.owner.slice(-1) }}</span><span>{{ topic.owner }}</span><span>目标 {{ topic.due || '未安排' }}</span><StatusBadge :value="topic.state || '进行中'" /><StatusBadge :value="`${rootItems.filter((item) => item.topics.includes(topic.name)).length} 个关联结果`" /></div>
      </section>
      <div v-if="!state?.topics.length" class="lw-panel lw-empty">尚未建立专题。</div>
    </div>
  </template>

  <template v-else>
    <div class="lw-toolbar">
      <div class="lw-segmented"><button :class="{ active: kind === 'all' }" type="button" @click="kind = 'all'">{{ isTeam ? '团队结果' : '我的全部' }}</button><button :class="{ active: kind === 'mine' }" type="button" @click="kind = 'mine'">我负责的</button></div>
      <input v-model="query" aria-label="搜索事项" placeholder="搜索标题或 ID" />
      <select v-model="filter" aria-label="筛选领域或专题"><option value="">全部领域 / 专题</option><option v-for="option in options" :key="option">{{ option }}</option></select>
      <span class="lw-spacer"></span><span class="lw-caption">分组</span>
      <select v-model="group" aria-label="分组方式"><option value="none">不分组</option><option value="topic">专题</option><option value="domain">领域</option></select>
      <button class="lw-btn" type="button" @click="savePreferences({ group, filter, kind })">保存此呈现</button>
      <RouterLink class="lw-btn" :to="`/lifeweave/${activeWorkspace}/meeting`"><LifeWeaveIcon name="meeting" />会议呈现</RouterLink>
    </div>
    <div v-if="group === 'topic'" class="lw-notice neutral lw-mb-14"><LifeWeaveIcon name="layers" /><span>跨专题事项仍是同一个 ID。分组允许重复出现；本页总数按事项去重。</span></div>
    <div class="lw-panel">
      <template v-for="([label, items]) in groups" :key="label">
        <div v-if="group !== 'none'" class="lw-group-head"><LifeWeaveIcon :name="group === 'topic' ? 'flag' : 'layers'" /><strong>{{ label }}</strong><span class="lw-muted">{{ items.length }} 项</span></div>
        <div class="lw-table-wrap">
          <table class="lw-data-table">
            <thead><tr><th>工作事项 / 本轮结果</th><th>最新进展</th><th>责任人</th><th>状态</th><th>目标时间</th><th></th></tr></thead>
            <tbody>
              <tr v-for="item in items" :key="`${label}-${item.id}`">
                <td class="title"><div class="lw-id">{{ item.id }} · {{ item.kind }}</div><RouterLink class="lw-row-link" :to="itemUrl(item.id)">{{ item.title }}</RouterLink><div class="lw-chips"><StatusBadge v-for="domain in item.domains" :key="domain" :value="domain" /><StatusBadge v-if="item.topics.length > 1" :value="`关联 ${item.topics.length} 个专题`" tone="blue" /></div></td>
                <td class="progress">{{ item.update }}</td><td><span class="lw-owner"><span class="lw-avatar" :class="{ me: item.owner === actorName }">{{ item.owner.slice(-1) }}</span>{{ item.owner }}</span></td><td><StatusBadge :value="item.state" /></td><td class="lw-mono">{{ item.due || '未安排' }}</td>
                <td><button class="lw-btn ghost icon-only" type="button" :aria-label="`速览 ${item.title}`" @click="openModal('peek', { item })"><LifeWeaveIcon name="eye" /></button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <div v-if="!groups.length" class="lw-empty">没有符合当前条件的事项。</div>
      <div class="lw-table-footer">去重后 {{ filtered.length }} 项成果 · 子工作默认收起</div>
    </div>
    <template v-if="isTeam">
      <div class="lw-section-title"><h2>我的具体贡献</h2></div>
      <div class="lw-panel"><div v-for="item in contributions" :key="item.id" class="lw-list-row"><div class="lw-grow"><RouterLink class="lw-text-btn lw-list-title" :to="itemUrl(item.id)">{{ item.title }}</RouterLink><div class="lw-list-sub">属于 {{ item.parentId }}</div></div><StatusBadge :value="item.state" /></div><div v-if="!contributions.length" class="lw-empty">当前没有单独分派给我的子工作。</div></div>
    </template>
  </template>
</template>

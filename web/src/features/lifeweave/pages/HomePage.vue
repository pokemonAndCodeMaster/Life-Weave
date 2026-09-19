<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'

const router = useRouter()
const quickIdea = shallowRef('')
const { activeWorkspace, rootItems, runs, state, openModal, createIdea } = useLifeWeaveWorkspace()
const needsAttention = computed(() => rootItems.value.filter((item) => item.attention))
const activeItems = computed(() => rootItems.value.filter((item) => !['已完成','accepted','已取消'].includes(item.state)))
const activeRuns = computed(() => runs.value.filter((run) => ['queued', 'claimed', 'running', 'pause_requested'].includes(run.state)))
const isTeam = computed(() => activeWorkspace.value === 'team')

function itemUrl(id: string, tab = 'overview') {
  return `/lifeweave/${activeWorkspace.value}/items/${encodeURIComponent(id)}/${tab}`
}

async function saveQuickIdea() {
  const body = quickIdea.value.trim()
  if (!body) return
  await createIdea({ body, scope: activeWorkspace.value === 'team' ? '团队' : '个人' })
  quickIdea.value = ''
}
</script>

<template>
  <PageHeader
    title="我的日常"
    subtitle="工作、学习与生活中的计划，在这里接着推进。"
    eyebrow="FOCUS / 把注意力留给真正需要你的事"
  >
    <RouterLink class="lw-btn primary" :to="`/lifeweave/${activeWorkspace}/conversation`"><LifeWeaveIcon name="message" />与经纬对话</RouterLink>
    <button class="lw-btn" type="button" @click="router.push(`/lifeweave/${activeWorkspace}/meeting`)">
      <LifeWeaveIcon name="meeting" />{{ isTeam ? '打开组会' : '打开周回顾' }}
    </button>
  </PageHeader>

  <div class="lw-two-cols">
    <div>
      <div class="lw-summary-line">
        <div><strong>{{ needsAttention.length }}</strong><span>项需要判断</span></div>
        <div><strong>{{ activeItems.length }}</strong><span>项正在推进</span></div>
        <div><strong>{{ activeRuns.length }}</strong><span>个委托运行</span></div>
      </div>

      <div class="lw-section-title"><h2>需要我处理</h2><StatusBadge value="先看变化，再作决定" tone="blue" /></div>
      <div class="lw-panel">
        <div v-for="item in needsAttention" :key="item.id" class="lw-action-row">
          <span class="lw-badge-icon"><LifeWeaveIcon :name="item.state === '已阻塞' ? 'flag' : 'message'" /></span>
          <div class="lw-row-main">
            <div class="lw-inline"><span class="lw-mono lw-muted">{{ item.id }}</span><StatusBadge :value="item.state === '已阻塞' ? '补充条件' : item.state === '待验收' ? '审阅结果' : item.context.proposals.length ? '有新提案' : '需要判断'" tone="amber" /></div>
            <h3>{{ item.title }}</h3>
            <p>{{ item.update }}</p>
            <span class="lw-tiny lw-muted">{{ item.context.proposals.length ? '候选修改保留原文与来源，采纳后更新共享上下文。' : '这项决定属于你，不需要重新描述全部背景。' }}</span>
          </div>
          <RouterLink class="lw-btn" :to="itemUrl(item.id, item.context.proposals.length ? 'context' : 'overview')">
            {{ item.context.proposals.length ? '查看上下文变化' : '打开事项' }}
          </RouterLink>
        </div>
        <div v-if="!needsAttention.length" class="lw-empty">当前没有待你判断的事项。</div>
      </div>

      <div class="lw-section-title">
        <h2>我关注的结果</h2>
        <RouterLink class="lw-btn ghost sm" :to="`/lifeweave/${activeWorkspace}/items`">查看全部 <LifeWeaveIcon name="arrow" /></RouterLink>
      </div>
      <div class="lw-panel">
        <div v-for="item in activeItems" :key="item.id" class="lw-list-row">
          <span class="lw-mono lw-muted">{{ item.id }}</span>
          <div class="lw-grow">
            <RouterLink class="lw-text-btn lw-list-title" :to="itemUrl(item.id)">{{ item.title }}</RouterLink>
            <div class="lw-list-sub">{{ item.update }}</div>
          </div>
          <StatusBadge :value="item.state" />
          <button class="lw-btn ghost icon-only" type="button" :aria-label="`速览 ${item.title}`" @click="openModal('peek', { item })"><LifeWeaveIcon name="eye" /></button>
        </div>
        <div v-if="!activeItems.length" class="lw-empty">当前没有正在推进的事项。</div>
      </div>

      <div class="lw-section-title"><h2>回来后，不必再从头解释</h2></div>
      <div class="lw-notice"><LifeWeaveIcon name="layers" /><div><strong>每件工作有自己的持续上下文。</strong><br />目标、共识、材料、未决问题与成果都留在事项里。</div></div>
    </div>

    <aside class="lw-stack">
      <section class="lw-panel pad">
        <h2 class="lw-small-heading">先把想法留下来</h2>
        <textarea v-model="quickIdea" class="lw-capture" aria-label="随手记录" placeholder="一句灵感、一个问题，或一段反馈……"></textarea>
        <div class="lw-between lw-mt-10"><span class="lw-tiny lw-muted">仅保存，不启动 AI</span><button class="lw-btn primary sm" type="button" @click="saveQuickIdea">记下来</button></div>
      </section>
      <section v-if="rootItems[0]" class="lw-panel pad">
        <h2 class="lw-small-heading">最近的共同理解</h2>
        <div class="lw-note-card">
          <div class="lw-inline"><StatusBadge :value="rootItems[0].context.revision ? `共识 v${rootItems[0].context.revision}` : '打开查看上下文'" tone="blue" /><span class="lw-tiny lw-muted">{{ rootItems[0].id }}</span></div>
          <p>{{ rootItems[0].scope }}</p>
          <RouterLink class="lw-text-btn" :to="itemUrl(rootItems[0].id, 'context')">查看依据与未决问题 <LifeWeaveIcon name="arrow" /></RouterLink>
        </div>
      </section>
      <section class="lw-panel pad">
        <span class="lw-tiny lw-muted">当前工作环境</span>
        <h3 class="lw-environment-title">{{ isTeam ? '团队工作空间' : 'Codex / OpenCode + 这台电脑' }}</h3>
        <p class="lw-small lw-sub">{{ isTeam ? '团队内容单独保存；当前仍由本机用户管理。' : '个人事项也可以没有代码仓、容器和研发流程。' }}</p>
      </section>
      <section v-if="!state?.items.length" class="lw-notice neutral">当前空间没有数据，可从“记录”开始建立真实内容。</section>
    </aside>
  </div>
</template>

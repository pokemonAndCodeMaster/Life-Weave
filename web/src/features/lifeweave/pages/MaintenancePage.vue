<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue'
import { apiError, listCapabilities } from '../api/lifeweave'
import LifeWeaveIcon from '../components/LifeWeaveIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'

interface Capability { id: string; title: string; target: string; status: string; desiredBehavior?: string; validationPlan?: string; version?: number | string; sourceItemId?: string }
const tabs = { abilities: '能力与成长', machines: '执行机', runs: '运行记录', connections: '连接与空间' } as const
const tab = shallowRef<keyof typeof tabs>('abilities')
const capabilities = shallowRef<Capability[]>([])
const capabilityError = shallowRef('')
const { activeWorkspace, state, runs, machines, runtimeLoading, loadRuntime, openModal, setMachineEnabled } = useLifeWeaveWorkspace()
const isTeam = computed(() => activeWorkspace.value === 'team')
const improvements = computed(() => [...new Map([...(state.value?.improvements ?? []), ...(state.value?.items ?? []).flatMap((item) => item.improvements.map((entry) => ({ ...entry, itemId: item.id })))].map((entry) => [entry.id, entry])).values()])

async function loadCapabilities() {
  try { const result = await listCapabilities(activeWorkspace.value); capabilities.value = result.items ?? [] }
  catch (caught) { capabilityError.value = apiError(caught).message }
}
onMounted(() => { void loadRuntime(); void loadCapabilities(); window.addEventListener('lifeweave-capabilities-changed', loadCapabilities) })
onBeforeUnmount(() => window.removeEventListener('lifeweave-capabilities-changed', loadCapabilities))
</script>

<template>
  <PageHeader title="维护中心" subtitle="面向能力与环境维护者。普通成员在事项中委托工作，无须挑选 Agent 编队。" />
  <div class="lw-tabs"><button v-for="(label, key) in tabs" :key="key" class="lw-tab" :class="{ active: tab === key }" type="button" @click="tab = key">{{ label }}</button></div>

  <div v-if="tab === 'abilities'" class="lw-two-cols"><div>
    <section class="lw-panel"><header class="lw-panel-head"><h2>能力改进候选</h2><StatusBadge value="验证与发布必须有真实证据" tone="amber" /></header><div v-for="candidate in capabilities" :key="candidate.id" class="lw-list-row"><LifeWeaveIcon name="spark" /><div class="lw-grow"><div class="lw-list-title">{{ candidate.title }}</div><div class="lw-list-sub">{{ candidate.desiredBehavior || candidate.validationPlan }}</div><div class="lw-tiny lw-muted lw-mt-5">{{ candidate.target }} · v{{ candidate.version ?? 1 }}</div></div><StatusBadge :value="candidate.status" /><button class="lw-btn sm" type="button" @click="openModal('capability-detail', { capabilityId: candidate.id })">查看</button></div><div v-if="capabilityError" class="lw-empty">{{ capabilityError }}</div><div v-else-if="!capabilities.length" class="lw-empty">尚无可验证的能力候选。</div></section>
    <div class="lw-section-title"><h2>从工作中形成的原始建议</h2><StatusBadge :value="`${improvements.length} 项`" /></div><article v-for="entry in improvements" :key="entry.id" class="lw-retro-row"><div class="lw-between"><StatusBadge :value="entry.kind" /><StatusBadge :value="entry.state" /></div><h3>{{ entry.title }}</h3><p>{{ entry.body }}</p><button class="lw-btn sm" type="button" @click="openModal('improvement-detail', { improvement: entry })">查看边界</button></article><div v-if="!improvements.length" class="lw-panel lw-empty">事项 → 复盘与成长 → 形成改进建议</div>
  </div><aside class="lw-panel pad"><h2>能力变化必须经过真实验证</h2><p class="lw-small lw-sub">改进建议先进入候选；只有绑定成功 Run 与人工接受证据，才能通过验证并发布。</p><hr class="lw-rule" /><h3>一种能力应说清楚</h3><p class="lw-small lw-sub">适用问题、输入、知识与工具、输出、停止条件与代表性案例。</p><h3>不同空间分别发布</h3><p class="lw-small lw-sub">个人与团队共享产品代码，不自动搬运公司数据或凭证。</p></aside></div>

  <template v-else-if="tab === 'machines'">
    <div class="lw-notice neutral lw-mb-20"><LifeWeaveIcon name="server" /><div>{{ isTeam ? '中心机统一派发，成员工作站承载运行。' : '个人 WSL 可以同时承载控制服务与本地执行端。' }} 状态来自真实执行端。</div></div>
    <div class="lw-maintenance-grid"><article v-for="machine in machines" :key="machine.id" class="lw-machine"><div class="lw-between"><LifeWeaveIcon name="server" /><StatusBadge :value="machine.status" /></div><h3>{{ machine.name }}</h3><span class="lw-mono lw-muted">{{ machine.id }}</span><div class="lw-machine-info">环境：{{ machine.image || '原生环境' }}<br />容量：{{ machine.used }} / {{ machine.capacity }} 个运行槽位<br />最后心跳：{{ machine.lastSeenAt || '未报告' }}</div><div class="lw-load-bar"><i :style="{ width: `${Math.min(100, machine.used / Math.max(1, machine.capacity) * 100)}%` }"></i></div><div class="lw-between"><span class="lw-tiny lw-muted">停止接单不终止已有运行</span><button class="lw-btn sm" type="button" :disabled="machine.status === 'offline'" @click="setMachineEnabled(machine.id, !machine.enabled)">{{ machine.enabled === false ? '恢复接单' : '暂停接单' }}</button></div></article><div v-if="!machines.length && !runtimeLoading" class="lw-panel lw-empty">尚未登记执行机。</div></div>
  </template>

  <section v-else-if="tab === 'runs'" class="lw-panel"><div class="lw-table-wrap"><table class="lw-run-table"><thead><tr><th>运行 / 所属工作</th><th>执行器与原生会话</th><th>执行位置</th><th>上下文</th><th>状态</th><th></th></tr></thead><tbody><tr v-for="run in runs" :key="run.id"><td><strong class="lw-mono">{{ run.id }}</strong><br /><RouterLink class="lw-text-btn" :to="`/lifeweave/${activeWorkspace}/items/${encodeURIComponent(run.itemId)}/activity`">{{ run.itemId }}</RouterLink></td><td>{{ run.engine }}<div class="lw-mono lw-muted">{{ run.session || '尚未建立' }}</div></td><td>{{ run.machine || '等待分配' }}<br /><span class="lw-tiny lw-muted">{{ run.branch || '无分支' }}</span></td><td>v{{ run.rev }}<StatusBadge v-if="run.staleContext" value="有新共识" tone="amber" /></td><td><StatusBadge :value="run.state" /></td><td><button class="lw-btn sm" type="button" @click="openModal('run-detail', { runId: run.id })">打开</button></td></tr></tbody></table></div><div v-if="!runs.length" class="lw-empty">尚未启动运行。</div></section>

  <div v-else class="lw-two-cols"><article class="lw-panel lw-article"><h2>{{ isTeam ? '团队部署' : '个人部署' }}的接入边界</h2><div v-for="resource in state?.resources" :key="resource.id" class="lw-resource"><LifeWeaveIcon :name="resource.kind === 'knowledge' ? 'book' : resource.kind === 'runtime' ? 'spark' : 'link'" /><div class="lw-grow"><h3>{{ resource.name }}</h3><p>{{ resource.description || resource.uri || '已登记资源' }}</p><span class="lw-tiny lw-muted">更新时间：{{ resource.updatedAt || '未报告' }}</span></div><StatusBadge :value="resource.state || resource.capability || '已登记'" /></div><div v-if="!state?.resources.length" class="lw-empty">当前空间尚未登记连接。</div><h3>共享产品，不共享公司数据</h3><p>数据库、凭证、知识、执行机与运行记录按空间分离。</p></article><aside class="lw-panel pad"><h2>连接能力分三层</h2><p class="lw-small lw-sub">关联定位、状态读取、动作执行分别显示。保存一个链接不会自动获得编辑权限。</p></aside></div>
</template>

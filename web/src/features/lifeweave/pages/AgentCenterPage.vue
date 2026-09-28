<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import AgentRegistry from '../components/agents/AgentRegistry.vue'
import AgentLaunch from '../components/agents/AgentLaunch.vue'
import ExecutionList from '../components/agents/ExecutionList.vue'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'

const route = useRoute(), router = useRouter()
const { activeWorkspace, state } = useLifeWeaveWorkspace()
const tab = computed(() => route.query.tab === 'executions' ? 'executions' : 'agents')
const itemId = shallowRef('')
const launching = shallowRef(false)
watch(() => route.query.itemId, value => { itemId.value = typeof value === 'string' ? value : ''; launching.value = !!itemId.value }, { immediate: true })
function setTab(value: string) { void router.replace({ query: { ...route.query, tab: value } }) }
</script>

<template>
  <PageHeader title="Agent 中心" subtitle="管理可调用的 Agent，查看真实执行及已采集轨迹。"><RouterLink class="lw-btn" :to="{ path:`/lifeweave/${activeWorkspace}/knowledge`, query:{ source:'lifeweave-project', path:'docs/agent-workflow.md' } }">阅读开发流程</RouterLink></PageHeader>
  <div class="agent-center">
    <nav class="agent-tabs" aria-label="Agent 中心栏目"><button type="button" :class="{ active: tab === 'agents' }" :aria-current="tab === 'agents' ? 'page' : undefined" @click="setTab('agents')">Agents</button><button type="button" :class="{ active: tab === 'executions' }" :aria-current="tab === 'executions' ? 'page' : undefined" @click="setTab('executions')">执行记录</button></nav>
    <template v-if="tab === 'agents'"><div class="launch-control"><label class="lw-label">给事项派任务<select v-model="itemId" class="lw-field"><option value="">选择事项</option><option v-for="item in state?.items" :key="item.id" :value="item.id">{{ item.title }} · {{ item.id }}</option></select></label><button type="button" class="lw-btn primary" :disabled="!itemId" @click="launching = !launching">{{ launching ? '收起派发' : '派任务' }}</button></div><AgentLaunch v-if="launching && itemId" :workspace="activeWorkspace" :item-id="itemId" @close="launching = false" /><AgentRegistry :workspace="activeWorkspace" /></template>
    <ExecutionList v-else :workspace="activeWorkspace" :initial-agent-id="typeof route.query.agentId === 'string' ? route.query.agentId : ''" />
  </div>
</template>

<style scoped>
.agent-center{display:grid;gap:17px}.agent-tabs{display:flex;border-bottom:1px solid #dce5ed}.agent-tabs button{border:0;background:none;color:#63798d;padding:11px 16px;cursor:pointer}.agent-tabs button.active{color:#285b8d;border-bottom:2px solid #4c83b6;font-weight:650}.launch-control{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.launch-control label{flex:1 1 300px}
</style>

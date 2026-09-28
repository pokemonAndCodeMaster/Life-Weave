<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import { apiError, listMethods } from '../../api/lifeweave'
import { createAgent, listAgents, updateAgent, type AgentCatalog, type AgentDefinition } from '../../api/agents'
import type { WorkspaceKind } from '../../types'

const props = defineProps<{ workspace: WorkspaceKind }>()
const catalog = shallowRef<AgentCatalog | null>(null)
const methods = shallowRef<Array<{id:string;title:string}>>([])
const loading = shallowRef(false)
const busy = shallowRef(false)
const error = shallowRef('')
const message = shallowRef('')
const editing = shallowRef(false)
const isNew = shallowRef(false)
const form = reactive({ id:'', name:'', description:'', capability:'general' as AgentDefinition['capability'], pluginId:'', methodId:'', engine:'codex' as AgentDefinition['engine'], model:'', runtime:'native' as 'native'|'docker', permission:'read-only' as 'read-only'|'workspace-write', enabled:true, version:0 })
const capabilityPlugins: Record<AgentDefinition['capability'], string> = { development:'lifeweave.development', research:'lifeweave.research', general:'lifeweave.general', organization:'lifeweave.item-organization' }
const capabilityLabels: Record<AgentDefinition['capability'], string> = { development:'开发', research:'研究', general:'通用任务', organization:'事项整理' }
const engineLabels: Record<AgentDefinition['engine'], string> = { codex:'Codex', opencode:'OpenCode', builtin:'内置规则执行' }
const selectedEngine = computed(() => catalog.value?.engines.find(engine => engine.id === form.engine))
function methodName(id?: string | null) { return id ? methods.value.find(method => method.id === id)?.title ?? '已绑定方法' : '默认方法' }

watch(() => props.workspace, () => { void load() }, { immediate: true })
watch(() => form.capability, capability => { form.pluginId = capabilityPlugins[capability]; if (capability === 'organization') form.engine = 'builtin' })
async function load() {
  loading.value = true; error.value = ''
  try {
    const [agents, methodRows] = await Promise.all([listAgents(props.workspace), listMethods(props.workspace).catch(() => ({items:[]}))])
    catalog.value = agents; methods.value = methodRows.items
  } catch (caught) { error.value = apiError(caught).message }
  finally { loading.value = false }
}
function open(agent?: AgentDefinition) {
  isNew.value = !agent; editing.value = true; error.value = ''; message.value = ''
  Object.assign(form, agent ? {id:agent.id,name:agent.name,description:agent.description,capability:agent.capability,pluginId:agent.pluginId,methodId:agent.methodId ?? '',engine:agent.engine,model:agent.model ?? '',runtime:agent.runtime ?? 'native',permission:agent.permission ?? 'read-only',enabled:agent.enabled,version:agent.version} : {id:'',name:'',description:'',capability:'general',pluginId:capabilityPlugins.general,methodId:'',engine:'codex',model:'',runtime:'native',permission:'read-only',enabled:true,version:0})
}
async function save() {
  if (busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    const body = { name:form.name.trim(), description:form.description.trim(), methodId:form.methodId || null, engine:form.engine, model:form.model.trim() || null, runtime:form.runtime, permission:form.permission, enabled:form.enabled }
    if (isNew.value) await createAgent(props.workspace, { id:form.id.trim(), capability:form.capability, ...body })
    else await updateAgent(props.workspace, form.id, { version:form.version, ...body })
    editing.value = false; message.value = 'Agent 配置已保存。'; await load()
  } catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="agent-registry">
    <div class="lw-between"><p class="lw-small lw-sub">Agent 绑定已有能力、方法与执行环境；每次触发都会固定当时的配置。</p><button type="button" class="lw-btn primary" @click="open()">注册 Agent</button></div>
    <p v-if="loading" role="status">正在读取 Agent 目录…</p><p v-if="error" role="alert" class="lw-notice warning">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <div v-if="catalog" class="agent-grid"><article v-for="agent in catalog.items" :key="agent.id" class="lw-panel pad agent-card"><div class="lw-between"><h2>{{ agent.name }}</h2><span class="lw-small" :class="agent.available ? 'ready' : 'unavailable'">{{ agent.available ? '可用' : '不可用' }}</span></div><p>{{ agent.description }}</p><p class="lw-tiny lw-muted">{{ capabilityLabels[agent.capability] }} · {{ engineLabels[agent.engine] }}{{ agent.model ? ` / ${agent.model}` : '' }} · {{ methodName(agent.methodId) }}</p><p v-if="!agent.available" class="lw-notice warning">{{ agent.reason || '运行环境尚未就绪。' }}</p><div class="agent-actions"><button type="button" class="lw-btn sm" @click="open(agent)">编辑配置</button><RouterLink class="lw-btn sm" :to="`/lifeweave/${workspace}/agents?tab=executions&agentId=${encodeURIComponent(agent.id)}`">执行记录</RouterLink></div><details class="technical"><summary>技术标识</summary><code>Agent {{ agent.id }}<br />方法 {{ agent.methodId || '默认' }}<br />插件 {{ agent.pluginId }}</code></details></article></div>
    <form v-if="editing" class="lw-panel pad agent-editor" @submit.prevent="save"><div class="lw-between"><h2>{{ isNew ? '注册 Agent' : '编辑 Agent' }}</h2><button type="button" class="lw-btn ghost sm" @click="editing = false">关闭</button></div><div class="editor-grid"><label v-if="isNew" class="lw-label">稳定 ID<input v-model="form.id" class="lw-field" required pattern="[a-z0-9][a-z0-9_-]*" /></label><label class="lw-label">名称<input v-model="form.name" class="lw-field" required /></label><label class="lw-label">能力<select v-model="form.capability" class="lw-field" :disabled="!isNew"><option value="development">开发</option><option value="research">研究</option><option value="general">通用任务</option><option value="organization">事项整理</option></select></label><label class="lw-label">已有能力插件<input v-model="form.pluginId" class="lw-field" readonly /></label><label class="lw-label">默认方法<select v-model="form.methodId" class="lw-field"><option value="">使用能力默认方法</option><option v-for="method in methods" :key="method.id" :value="method.id">{{ method.title }}</option></select></label><label class="lw-label">执行器<select v-model="form.engine" class="lw-field"><option v-if="form.capability === 'organization' || form.engine === 'builtin'" value="builtin">内置规则执行</option><option v-for="engine in catalog?.engines" :key="engine.id" :value="engine.id" :disabled="!engine.available && engine.id !== form.engine">{{ engine.label }}{{ engine.available ? '' : '（不可用）' }}</option></select></label><label class="lw-label">默认模型<input v-model="form.model" class="lw-field" placeholder="留空使用执行器默认模型" /></label><label class="lw-label">运行环境<select v-model="form.runtime" class="lw-field"><option value="native">本机</option><option value="docker">容器</option></select></label><label class="lw-label">默认权限<select v-model="form.permission" class="lw-field"><option value="read-only">只读</option><option value="workspace-write">工作目录可写</option></select></label></div><label class="lw-label">用途说明<textarea v-model="form.description" class="lw-field" rows="3" /></label><label class="lw-small"><input v-model="form.enabled" type="checkbox" /> 启用</label><p v-if="selectedEngine && !selectedEngine.available" class="lw-notice warning">{{ selectedEngine.reason }}</p><p class="lw-tiny lw-muted">认证信息由运行环境管理，不写入 Agent 配置。</p><button type="submit" class="lw-btn primary" :disabled="busy">{{ busy ? '保存中…' : '保存配置' }}</button></form>
  </section>
</template>

<style scoped>
.agent-registry{display:grid;gap:16px}.agent-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:13px}.agent-card{display:grid;gap:8px}.agent-card h2,.agent-editor h2{font-size:15px;margin:0}.agent-card p{margin:0;font-size:12px;line-height:1.5}.agent-actions{display:flex;gap:8px;flex-wrap:wrap}.ready{color:#247454}.unavailable{color:#a14736}.agent-editor{display:grid;gap:13px}.editor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}@media(max-width:700px){.editor-grid{grid-template-columns:1fr}}
.technical{font-size:11px;color:#71869a}.technical summary{cursor:pointer}.technical code{display:block;margin-top:5px;white-space:normal;overflow-wrap:anywhere}
</style>

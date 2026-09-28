<script setup lang="ts">
import { computed, reactive, ref, shallowRef, watch } from 'vue'
import { apiError } from '../../api/lifeweave'
import { applyOrganizationProposal, createOrganizationProposal, getOrganizationCatalog, getOrganizationProposal, saveOrganizationRules, undoOrganizationProposal, type OrganizationCatalog, type OrganizationProposal, type OrganizationRule } from '../../api/itemOrganization'
import type { WorkspaceKind } from '../../types'

const props = defineProps<{ workspace: WorkspaceKind }>()
const emit = defineEmits<{ updated: [] }>()
const catalog = shallowRef<OrganizationCatalog | null>(null)
const proposal = shallowRef<OrganizationProposal | null>(null)
const ruleItemIds = ref<string[]>([])
const groupItemIds = ref<string[]>([])
const groupQuery = shallowRef('')
const rules = ref<OrganizationRule[]>([])
const form = reactive({ itemId:'', topicIds:[] as string[], domainIds:[] as string[], parentId:'', reason:'', groupTitle:'', groupGoal:'' })
const busy = shallowRef(false)
const error = shallowRef('')
const message = shallowRef('')
const selected = computed(() => catalog.value?.items.find(item => item.id === form.itemId))
const groupCandidates = computed(() => {
  const query = groupQuery.value.trim().toLocaleLowerCase()
  return (catalog.value?.items ?? []).filter(item => !query || `${item.title} ${item.id}`.toLocaleLowerCase().includes(query))
})
const groupMembers = computed(() => groupItemIds.value.map(id => catalog.value?.items.find(item => item.id === id)).filter((item): item is NonNullable<typeof item> => !!item))
function names(ids: string[], kind: 'topics'|'domains') { return ids.map(id => catalog.value?.[kind].find(entity => entity.id === id)?.title ?? id).join('、') || '未关联' }
function parentName(id: string | null) { return id ? catalog.value?.items.find(item => item.id === id)?.title ?? id : '无上级' }
watch(() => props.workspace, () => { proposal.value = null; ruleItemIds.value = []; groupItemIds.value = []; groupQuery.value = ''; void load() }, { immediate:true })
watch(selected, item => { form.topicIds = [...item?.topicIds ?? []]; form.domainIds = [...item?.domainIds ?? []]; form.parentId = item?.parentId ?? ''; form.reason = '' })
async function load() {
  try { catalog.value = await getOrganizationCatalog(props.workspace); rules.value = structuredClone(catalog.value.rules); error.value = '' }
  catch (caught) { error.value = apiError(caught).message }
}
async function act(operation: () => Promise<OrganizationProposal>, success: string) {
  if (busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  try { proposal.value = await operation(); message.value = success; await load(); emit('updated') }
  catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
function automatic() { void act(() => createOrganizationProposal(props.workspace, {requestId:crypto.randomUUID(), itemIds:ruleItemIds.value.length ? ruleItemIds.value : undefined, reason:'按已维护规则和父项继承生成分类建议'}), '建议已生成；请核对差异再应用。') }
function explicit() {
  if (!selected.value || !form.reason.trim()) { error.value = '请选事项并填写调整理由。'; return }
  void act(() => createOrganizationProposal(props.workspace, {requestId:crypto.randomUUID(), changes:[{itemId:selected.value!.id,itemVersion:selected.value!.version,topicIds:form.topicIds,domainIds:form.domainIds,parentId:form.parentId || null,reason:form.reason.trim()}],reason:form.reason.trim()}), '分类建议已生成；请核对差异再应用。')
}
function aggregate() {
  if (!form.groupTitle.trim() || !form.groupGoal.trim() || !groupItemIds.value.length) { error.value = '请填写聚合事项名称、共同目标，并选择至少一个事项。'; return }
  void act(() => createOrganizationProposal(props.workspace, {requestId:crypto.randomUUID(), groups:[{key:crypto.randomUUID(),title:form.groupTitle.trim(),goal:form.groupGoal.trim(),itemIds:groupItemIds.value}],reason:'保留原事项及成果，在共同一级事项下聚合'}), '聚合建议已生成；请核对差异再应用。')
}
function removeGroupMember(id: string) { groupItemIds.value = groupItemIds.value.filter(value => value !== id) }
function addRule() { rules.value = [...rules.value, {id:`rule-${crypto.randomUUID()}`,title:'',terms:[],topicIds:[],domainIds:[],enabled:true}] }
async function saveRules() {
  if (!catalog.value || busy.value) return
  busy.value = true; error.value = ''
  try { await saveOrganizationRules(props.workspace, {...(catalog.value.rulesVersion == null ? {} : {version:catalog.value.rulesVersion}),rules:rules.value}); message.value = '分类规则已保存。'; await load() }
  catch (caught) { error.value = apiError(caught).message }
  finally { busy.value = false }
}
async function openProposal(id: string) {
  try { proposal.value = await getOrganizationProposal(props.workspace, id); error.value = '' }
  catch (caught) { error.value = apiError(caught).message }
}
</script>

<template>
  <section class="organization" aria-label="整理事项">
    <div class="lw-between"><div><h2>整理事项</h2><p class="lw-small lw-sub">先预览专题、领域与父子关系变化，再应用；撤销只恢复本批组织关系。</p></div><button type="button" class="lw-btn sm" @click="load">刷新</button></div>
    <p v-if="error" role="alert" class="lw-notice warning">{{ error }}</p><p v-if="message" role="status" class="lw-small">{{ message }}</p>
    <template v-if="catalog">
      <div class="organization-layout"><div class="organize-card"><h3>按规则建议</h3><p class="lw-small lw-sub">{{ catalog.unorganizedItems.length }} 项待整理；仅使用已维护的明确规则和父项继承。</p><div class="item-choices"><label v-for="item in catalog.unorganizedItems" :key="item.id"><input v-model="ruleItemIds" type="checkbox" :value="item.id" /> {{ item.title }}</label></div><button type="button" class="lw-btn" :disabled="busy || !catalog.unorganizedItems.length" @click="automatic">{{ ruleItemIds.length ? '预览所选事项' : '预览全部待整理项' }}</button></div>
      <div class="organize-card"><h3>明确分类或移组</h3><label class="lw-label">事项<select v-model="form.itemId" class="lw-field"><option value="">请选择</option><option v-for="item in catalog.items" :key="item.id" :value="item.id">{{ item.title }}</option></select></label><template v-if="selected"><label class="lw-label">专题<select v-model="form.topicIds" class="lw-field" multiple size="3"><option v-for="topic in catalog.topics" :key="topic.id" :value="topic.id">{{ topic.title }}</option></select></label><label class="lw-label">领域<select v-model="form.domainIds" class="lw-field" multiple size="3"><option v-for="domain in catalog.domains" :key="domain.id" :value="domain.id">{{ domain.title }}</option></select></label><label class="lw-label">上级事项<select v-model="form.parentId" class="lw-field"><option value="">无上级</option><option v-for="item in catalog.items.filter(candidate => candidate.id !== form.itemId)" :key="item.id" :value="item.id">{{ item.title }}</option></select></label><label class="lw-label">调整理由<textarea v-model="form.reason" class="lw-field" rows="2" required /></label><button type="button" class="lw-btn" :disabled="busy" @click="explicit">预览分类变化</button></template></div>
      <div class="organize-card"><h3>聚合相关事项</h3><p class="lw-small lw-sub">从全部事项中选择成员，建立共同的一级事项；原事项和历史保留。</p><details class="group-picker"><summary>选择聚合成员 · {{ groupItemIds.length }} 项</summary><label class="lw-label">搜索聚合事项<input v-model="groupQuery" class="lw-field" type="search" placeholder="标题或编号" /></label><div class="item-choices" role="group" aria-label="聚合成员候选"><label v-for="item in groupCandidates" :key="item.id"><input v-model="groupItemIds" type="checkbox" :value="item.id" /> <span>{{ item.title }} <small>{{ item.id }}</small></span></label><p v-if="!groupCandidates.length" class="lw-small lw-sub">没有匹配的事项。</p></div></details><div v-if="groupMembers.length" class="group-members" aria-label="已选聚合成员"><div v-for="item in groupMembers" :key="item.id"><span>{{ item.title }}</span><button type="button" class="lw-text-btn" :aria-label="`移除 ${item.title}`" @click="removeGroupMember(item.id)">移除</button></div></div><label class="lw-label">聚合事项名称<input v-model="form.groupTitle" class="lw-field" /></label><label class="lw-label">共同目标<textarea v-model="form.groupGoal" class="lw-field" rows="2" /></label><button type="button" class="lw-btn" :disabled="busy" @click="aggregate">预览聚合</button></div></div>
      <section v-if="proposal" class="proposal" aria-label="整理差异预览"><div class="lw-between"><h3>整理差异 · {{ proposal.status }}</h3><span class="lw-tiny lw-muted">{{ proposal.id }}</span></div><p>{{ proposal.reason }}</p><ul v-if="proposal.warnings?.length" class="lw-notice warning"><li v-for="warning in proposal.warnings" :key="warning">{{ warning }}</li></ul><div v-for="change in proposal.changes" :key="change.itemId" class="change"><strong>{{ change.title }}</strong><span>专题：{{ names(change.before.topicIds, 'topics') }} → {{ names(change.after.topicIds, 'topics') }}</span><span>领域：{{ names(change.before.domainIds, 'domains') }} → {{ names(change.after.domainIds, 'domains') }}</span><span>上级：{{ parentName(change.before.parentId) }} → {{ parentName(change.after.parentId) }}</span><small>{{ change.reason }}</small></div><div v-for="group in proposal.groups" :key="group.key" class="change"><strong>新聚合：{{ group.title }}</strong><span>{{ group.goal }}</span><small>{{ group.itemIds.length }} 个原事项保留并关联</small></div><div class="proposal-actions"><button v-if="proposal.status === 'proposed'" type="button" class="lw-btn primary" :disabled="busy" @click="act(() => applyOrganizationProposal(workspace, proposal!.id), '整理已应用。')">应用这批变更</button><button v-if="proposal.status === 'applied'" type="button" class="lw-btn" :disabled="busy" @click="act(() => undoOrganizationProposal(workspace, proposal!.id), '组织关系已撤销。')">撤销这批变更</button></div></section>
      <details class="rules"><summary>维护分类规则 · {{ rules.length }} 条</summary><p class="lw-small lw-sub">关键词只用于确定性分类，不据此自动改变已有父子关系。</p><div v-for="(rule, index) in rules" :key="rule.id" class="rule"><label class="lw-label">规则名<input v-model="rule.title" class="lw-field" /></label><label class="lw-label">匹配词（逗号分隔）<input class="lw-field" :value="rule.terms.join('，')" @change="rule.terms = ($event.target as HTMLInputElement).value.split(/[,，]/).map(term => term.trim()).filter(Boolean)" /></label><label class="lw-label">专题<select v-model="rule.topicIds" class="lw-field" multiple size="3"><option v-for="topic in catalog.topics" :key="topic.id" :value="topic.id">{{ topic.title }}</option></select></label><label class="lw-label">领域<select v-model="rule.domainIds" class="lw-field" multiple size="3"><option v-for="domain in catalog.domains" :key="domain.id" :value="domain.id">{{ domain.title }}</option></select></label><label><input v-model="rule.enabled" type="checkbox" /> 启用</label><button type="button" class="lw-text-btn" @click="rules.splice(index, 1)">移除</button></div><div class="proposal-actions"><button type="button" class="lw-btn" @click="addRule">添加规则</button><button type="button" class="lw-btn primary" :disabled="busy" @click="saveRules">保存规则</button></div></details>
      <details class="history"><summary>历史整理批次 · {{ catalog.proposals.length }} 条</summary><ul><li v-for="entry in catalog.proposals" :key="entry.id"><button type="button" class="lw-text-btn" @click="openProposal(entry.id)">{{ entry.reason || entry.id }} · {{ entry.status }}</button></li></ul></details>
    </template>
  </section>
</template>

<style scoped>
.organization{display:grid;gap:15px;border:1px solid var(--lw-line);border-radius:8px;background:#fff;padding:17px;margin-bottom:18px}.organization h2{margin:0 0 5px;font-size:16px}.organization h3{font-size:13px;margin:0 0 10px}.organization-layout{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.organize-card{display:grid;align-content:start;gap:10px;border:1px solid #e2e8ef;border-radius:8px;padding:13px}.organize-card p{margin:0}.item-choices{max-height:150px;overflow:auto;display:grid;gap:5px;font-size:11px}.item-choices label{display:flex;gap:5px;align-items:baseline}.proposal,.rules,.history{border-top:1px solid #e2e8ef;padding-top:14px}.proposal p{font-size:12px}.change{display:grid;gap:4px;border:1px solid #e5ebf1;border-radius:6px;padding:10px;margin:7px 0;font-size:11px}.change strong{font-size:12px}.change small{color:#6e8296}.proposal-actions{display:flex;gap:8px;margin-top:12px}.rules summary,.history summary{cursor:pointer;font-size:12px;font-weight:600}.rule{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;border-bottom:1px solid #e5ebf1;padding:12px 0}.history ul{font-size:12px}@media(max-width:900px){.organization-layout{grid-template-columns:1fr 1fr}}@media(max-width:650px){.organization-layout,.rule{grid-template-columns:1fr}}
.group-picker{border:1px solid #e2e8ef;border-radius:6px;padding:9px}.group-picker summary{cursor:pointer;font-size:12px;color:#426b93}.group-picker .lw-label{margin:10px 0}.group-picker small{color:#73879a}.group-members{display:grid;gap:4px;font-size:11px}.group-members div{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
</style>

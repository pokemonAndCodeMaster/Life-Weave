<script setup lang="ts">
import {computed,shallowRef,watch} from 'vue'
import {http} from '@/shared/api/http'
import {apiError} from '../api/lifeweave'
import {useLifeWeaveWorkspace} from '../composables/useLifeWeaveWorkspace'
import PageHeader from '../components/PageHeader.vue'
import MarkdownBody from '../components/MarkdownBody.vue'
interface Issue{id:string;identifier:string;title:string;description:string|null;url:string;state:{name:string};team:{name:string}}
interface Binding{issue_id:string;item_id:string;remote_snapshot:Issue}
const {activeWorkspace,load}=useLifeWeaveWorkspace()
const issues=shallowRef<Issue[]>([]);const bindings=shallowRef<Binding[]>([]);const selected=shallowRef<Issue|null>(null)
const query=shallowRef('');const after=shallowRef<string|null>(null);const hasNext=shallowRef(false)
const busy=shallowRef(false);const error=shallowRef('');const message=shallowRef('')
const endpoint=()=>`/lifeweave/${activeWorkspace.value}`
const visible=computed(()=>issues.value.filter(i=>`${i.identifier} ${i.title}`.toLowerCase().includes(query.value.toLowerCase())))
const binding=computed(()=>bindings.value.find(b=>b.issue_id===selected.value?.id))
async function action(fn:()=>Promise<void>){busy.value=true;error.value='';message.value='';try{await fn()}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
async function refresh(more=false){await action(async()=>{bindings.value=(await http.get<Binding[]>(`${endpoint()}/linear/bindings`)).data;const result=(await http.get<{nodes:Issue[];pageInfo:{endCursor:string;hasNextPage:boolean}}>(`${endpoint()}/linear/issues`,{params:{after:more?after.value:undefined}})).data;issues.value=more?[...issues.value,...result.nodes]:result.nodes;after.value=result.pageInfo.endCursor;hasNext.value=result.pageInfo.hasNextPage})}
async function importIssue(){if(!selected.value)return;await action(async()=>{const result=(await http.post(`${endpoint()}/linear/import`,{issueId:selected.value!.id})).data;await load(activeWorkspace.value,true);bindings.value=(await http.get<Binding[]>(`${endpoint()}/linear/bindings`)).data;message.value=result.created?'已建立关联工作，可在工作台继续推进。':'来源快照已刷新，本地工作内容保持不变。'})}
watch(activeWorkspace,()=>{selected.value=null;void refresh()},{immediate:true})
</script>
<template>
<PageHeader title="Linear 历史事项" subtitle="读取既有事项与来源；新知识和成果转向 Notion。"><button class="lw-btn" :disabled="busy" @click="refresh()">刷新</button></PageHeader>
<p v-if="error" class="lw-notice warning" role="alert">{{error}}</p><p v-if="message" class="lw-notice" role="status">{{message}}</p>
<div class="lw-toolbar"><input v-model="query" class="lw-grow" aria-label="筛选已加载 Linear 事项" placeholder="查找已加载的事项"/><span class="lw-small lw-muted">{{issues.length}} 项已加载</span></div>
<div class="lw-knowledge-grid"><aside class="lw-panel lw-knowledge-nav"><button v-for="issue in visible" :key="issue.id" class="lw-knowledge-link" :class="{active:selected?.id===issue.id}" @click="selected=issue"><span>{{issue.title}}<small>{{issue.identifier}} · {{issue.state.name}}</small></span></button><button v-if="hasNext" class="lw-btn" :disabled="busy" @click="refresh(true)">加载更多</button><p v-if="!issues.length" class="lw-empty">连接 Linear 后可读取分配给你的事项。</p></aside><article class="lw-panel lw-article"><template v-if="selected"><div class="lw-between"><span class="lw-small lw-muted">{{selected.identifier}} · {{selected.team.name}}</span><a class="lw-text-btn" :href="selected.url" target="_blank" rel="noopener noreferrer">在 Linear 打开 ↗</a></div><h2>{{selected.title}}</h2><MarkdownBody :content="selected.description||'此事项还没有正文。'"/><div class="lw-inline lw-mt-20"><button class="lw-btn primary" :disabled="busy" @click="importIssue">{{binding?'刷新来源快照':'引入工作台'}}</button><RouterLink v-if="binding" class="lw-btn" :to="`/lifeweave/${activeWorkspace}/items/${binding.item_id}/overview`">打开关联工作</RouterLink></div><p class="lw-tiny lw-muted">引入后，本地安排与原事项状态分别维护。刷新来源不会覆盖本地修改。</p></template><div v-else class="lw-empty">选择一条事项，阅读完整背景。</div></article></div>
</template>

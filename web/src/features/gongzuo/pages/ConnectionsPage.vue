<script setup lang="ts">
import {computed,reactive,shallowRef,watch} from 'vue'
import {http} from '@/shared/api/http'
import {apiError} from '../api/gongzuo'
import {useGongzuoWorkspace} from '../composables/useGongzuoWorkspace'
import PageHeader from '../components/PageHeader.vue'
import MarkdownBody from '../components/MarkdownBody.vue'
interface Issue{id:string;identifier:string;title:string;description:string|null;url:string;state:{name:string};team:{name:string}}
interface Binding{issue_id:string;item_id:string;remote_snapshot:Issue}
interface Publication{id:string;body:string;status:string;item_id:string}
const {activeWorkspace,load}=useGongzuoWorkspace()
const issues=shallowRef<Issue[]>([]);const bindings=shallowRef<Binding[]>([]);const selected=shallowRef<Issue|null>(null)
const query=shallowRef('');const after=shallowRef<string|null>(null);const hasNext=shallowRef(false)
const busy=shallowRef(false);const error=shallowRef('');const message=shallowRef('')
const publication=shallowRef<Publication|null>(null);const form=reactive({itemId:'',body:''})
const endpoint=()=>`/gongzuo/${activeWorkspace.value}`
const visible=computed(()=>issues.value.filter(i=>`${i.identifier} ${i.title}`.toLowerCase().includes(query.value.toLowerCase())))
const binding=computed(()=>bindings.value.find(b=>b.issue_id===selected.value?.id))
async function action(fn:()=>Promise<void>){busy.value=true;error.value='';message.value='';try{await fn()}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
async function refresh(more=false){await action(async()=>{bindings.value=(await http.get<Binding[]>(`${endpoint()}/linear/bindings`)).data;const result=(await http.get<{nodes:Issue[];pageInfo:{endCursor:string;hasNextPage:boolean}}>(`${endpoint()}/linear/issues`,{params:{after:more?after.value:undefined}})).data;issues.value=more?[...issues.value,...result.nodes]:result.nodes;after.value=result.pageInfo.endCursor;hasNext.value=result.pageInfo.hasNextPage})}
async function importIssue(){if(!selected.value)return;await action(async()=>{const result=(await http.post(`${endpoint()}/linear/import`,{issueId:selected.value!.id})).data;await load(activeWorkspace.value,true);bindings.value=(await http.get<Binding[]>(`${endpoint()}/linear/bindings`)).data;message.value=result.created?'已建立关联工作，可在工作台继续推进。':'来源快照已刷新，本地工作内容保持不变。'})}
async function prepare(){await action(async()=>{publication.value=(await http.post<Publication>(`${endpoint()}/linear/publications`,form)).data})}
async function publish(){if(!publication.value)return;await action(async()=>{publication.value=(await http.post<Publication>(`${endpoint()}/linear/publications/${publication.value!.id}/publish`)).data;message.value='已发送到原 Linear 事项，正文回读一致。'})}
watch(activeWorkspace,()=>{selected.value=null;publication.value=null;void refresh()},{immediate:true})
</script>
<template>
<PageHeader title="Linear 事项" subtitle="引入已有工作，查看来源，在发送成果前确认正文。"><RouterLink class="gz-btn" :to="`/gongzuo/${activeWorkspace}/settings`">连接设置</RouterLink><button class="gz-btn" :disabled="busy" @click="refresh()">刷新</button></PageHeader>
<p v-if="error" class="gz-notice warning" role="alert">{{error}}</p><p v-if="message" class="gz-notice" role="status">{{message}}</p>
<div class="gz-toolbar"><input v-model="query" class="gz-grow" aria-label="筛选已加载 Linear 事项" placeholder="查找已加载的事项"/><span class="gz-small gz-muted">{{issues.length}} 项已加载</span></div>
<div class="gz-knowledge-grid"><aside class="gz-panel gz-knowledge-nav"><button v-for="issue in visible" :key="issue.id" class="gz-knowledge-link" :class="{active:selected?.id===issue.id}" @click="selected=issue"><span>{{issue.title}}<small>{{issue.identifier}} · {{issue.state.name}}</small></span></button><button v-if="hasNext" class="gz-btn" :disabled="busy" @click="refresh(true)">加载更多</button><p v-if="!issues.length" class="gz-empty">连接 Linear 后可读取分配给你的事项。</p></aside><article class="gz-panel gz-article"><template v-if="selected"><div class="gz-between"><span class="gz-small gz-muted">{{selected.identifier}} · {{selected.team.name}}</span><a class="gz-text-btn" :href="selected.url" target="_blank" rel="noopener noreferrer">在 Linear 打开 ↗</a></div><h2>{{selected.title}}</h2><MarkdownBody :content="selected.description||'此事项还没有正文。'"/><div class="gz-inline gz-mt-20"><button class="gz-btn primary" :disabled="busy" @click="importIssue">{{binding?'刷新来源快照':'引入工作台'}}</button><RouterLink v-if="binding" class="gz-btn" :to="`/gongzuo/${activeWorkspace}/items/${binding.item_id}/overview`">打开关联工作</RouterLink></div><p class="gz-tiny gz-muted">引入后，本地安排与原事项状态分别维护。刷新来源不会覆盖本地修改。</p></template><div v-else class="gz-empty">选择一条事项，阅读完整背景。</div></article></div>
<section class="gz-panel pad gz-mt-20"><h2>把成果发回原事项</h2><p class="gz-small gz-sub">先预览，再发送为原事项的一条评论；不改写原来的目标或状态。</p><form class="gz-stack" @submit.prevent="prepare"><label class="gz-label">关联工作<select v-model="form.itemId" class="gz-field" required><option value="">选择工作</option><option v-for="entry in bindings" :key="entry.item_id" :value="entry.item_id">{{entry.remote_snapshot.identifier}} · {{entry.remote_snapshot.title}}</option></select></label><label class="gz-label">成果与下一步<textarea v-model="form.body" class="gz-field" rows="5" required placeholder="完成了什么、证据在哪里、还有哪些未完成……"></textarea></label><button class="gz-btn" :disabled="busy">生成发布预览</button></form><div v-if="publication" class="gz-publication-preview"><h3>发送到 {{bindings.find(b=>b.item_id===publication?.item_id)?.remote_snapshot.identifier||'关联事项'}} 的固定正文</h3><MarkdownBody :content="publication.body"/><button v-if="publication.status!=='confirmed'" class="gz-btn primary" :disabled="busy" @click="publish">确认发送到原事项</button><p v-else class="gz-small">已发送并回读确认。</p></div></section>
</template>

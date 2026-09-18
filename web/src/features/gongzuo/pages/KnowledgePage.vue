<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as library from '../api/library'
import { apiError } from '../api/gongzuo'
import { useGongzuoWorkspace } from '../composables/useGongzuoWorkspace'
import PageHeader from '../components/PageHeader.vue'
import MarkdownBody from '../components/MarkdownBody.vue'
import { resolveKnowledgePath } from '../utils/knowledgeLinks'
import { downloadText } from '../utils/download'
const { activeWorkspace } = useGongzuoWorkspace()
const route = useRoute(); const router = useRouter()
const entries = shallowRef<library.Document[]>([]); const selected = shallowRef<library.Document|null>(null)
const changes = shallowRef<library.Revision[]>([]); const selectedChange = shallowRef<library.Revision|null>(null)
const query = shallowRef(''); const tab = shallowRef<'documents'|'revisions'>('documents')
const editing = shallowRef(false); const busy = shallowRef(false); const error = shallowRef(''); const message = shallowRef('')
const form = reactive({path:'',content:'',reason:''})
const pending = computed(() => changes.value.filter(r => r.status === 'draft').length)
async function action(fn:()=>Promise<void>) { busy.value=true;error.value='';message.value=''; try { await fn() } catch(e) { error.value=apiError(e).message } finally { busy.value=false } }
async function refresh() {
 const scope=activeWorkspace.value
 const [catalog,revisions] = await Promise.all([library.documents(activeWorkspace.value,query.value),library.revisions(activeWorkspace.value)])
 if(scope!==activeWorkspace.value)return
 entries.value=catalog.items;changes.value=revisions
 if(catalog.unavailableSources.length) error.value=`来源暂不可用：${catalog.unavailableSources.join('、')}`
}
async function read(doc:Pick<library.Document,'path'|'sourceId'>) { await action(async()=> { const scope=activeWorkspace.value;const document=await library.document(scope,doc.path,doc.sourceId);if(scope!==activeWorkspace.value)return;selected.value=document;editing.value=false; await router.replace({query:{path:doc.path,source:doc.sourceId}}) }) }
function edit(create=false) { if(create) selected.value=null;form.path=selected.value?.path??'';form.content=selected.value?.content??'# 新的知识\n\n';form.reason='';editing.value=true }
async function save() { await action(async()=> { selectedChange.value=await library.propose(activeWorkspace.value,{...form,sourceId:selected.value?.sourceId??'local',baseVersion:selected.value?.version??'new'});editing.value=false;tab.value='revisions';await refresh();message.value='修订已保存。查看差异后，再决定是否接受。' }) }
async function decide(accept:boolean) { if(!selectedChange.value)return;await action(async()=> { selectedChange.value=await library.decide(activeWorkspace.value,selectedChange.value!.id,accept);await refresh();selected.value=null;message.value=accept?'已接受修订，知识原文已更新。':'已拒绝修订，原文保持不变。' }) }
function follow(event:MouseEvent) {
 const anchor=(event.target as HTMLElement).closest('a'); if(!anchor||!selected.value)return
 const href=anchor.getAttribute('href')??''
 if(href.startsWith('#'))return
 if(/^[a-z]+:/i.test(href)){anchor.target='_blank';anchor.rel='noopener noreferrer';return}
 if(href.split('#')[0]?.endsWith('.md')) { event.preventDefault();const path=resolveKnowledgePath(selected.value.path,href);if(path)void read({path,sourceId:selected.value.sourceId});else error.value='此链接超出了所选知识目录。' }
}
watch([activeWorkspace,()=>route.query.path,()=>route.query.source],()=> { selected.value=null;selectedChange.value=null;editing.value=false;void action(async()=> { await refresh();const path=String(route.query.path??'');if(path) selected.value=await library.document(activeWorkspace.value,path,String(route.query.source??'local')) }) },{immediate:true})
</script>
<template>
 <PageHeader title="知识与材料" subtitle="读完整正文，把有用的发现留成下一次能用的知识。"><button class="gz-btn primary" @click="tab='documents';edit(true)">新建知识</button></PageHeader>
 <div class="gz-tabs"><button class="gz-tab" :class="{active:tab==='documents'}" @click="tab='documents'">知识库</button><button class="gz-tab" :class="{active:tab==='revisions'}" @click="tab='revisions'">修订与历史 <span v-if="pending">{{ pending }}</span></button></div>
 <p v-if="error" class="gz-notice warning" role="alert">{{ error }}</p><p v-if="message" class="gz-notice" role="status">{{ message }}</p>
 <template v-if="tab==='documents'">
  <form class="gz-toolbar" @submit.prevent="action(refresh)"><input v-model="query" class="gz-grow" aria-label="搜索知识全文" placeholder="搜索标题、路径或正文"/><button class="gz-btn" :disabled="busy">搜索</button><RouterLink class="gz-text-btn" :to="`/gongzuo/${activeWorkspace}/settings`">管理知识来源</RouterLink></form>
  <div class="gz-knowledge-grid">
   <aside class="gz-panel gz-knowledge-nav"><button v-for="doc in entries" :key="doc.sourceId+doc.path" class="gz-knowledge-link" :class="{active:selected?.path===doc.path&&selected?.sourceId===doc.sourceId}" @click="read(doc)"><span>{{ doc.title }}<small>{{ doc.sourceTitle }} · {{ doc.path }}</small></span></button><div v-if="!entries.length" class="gz-empty">还没有知识。新建一篇，或在设置中接入已有目录。</div></aside>
   <article class="gz-panel gz-article">
    <form v-if="editing" class="gz-stack" @submit.prevent="save"><label class="gz-label">文件路径<input v-model="form.path" class="gz-field" placeholder="学习/阅读笔记.md" :readonly="!!selected" required/></label><label class="gz-label">Markdown 正文<textarea v-model="form.content" class="gz-field gz-large-textarea" rows="18" required></textarea></label><label class="gz-label">修改说明<input v-model="form.reason" class="gz-field" placeholder="这次补充或修正了什么" required/></label><div class="gz-inline"><button class="gz-btn primary" :disabled="busy">保存修订，查看差异</button><button type="button" class="gz-btn" @click="editing=false">取消</button></div></form>
    <template v-else-if="selected"><div class="gz-between"><span class="gz-small gz-muted">{{ selected.sourceTitle }} · {{ selected.writable?'工作台管理':'外部只读来源' }}</span><div class="gz-inline"><button class="gz-btn sm" @click="downloadText(selected!.content,selected!.path.split('/').pop()||'知识.md')">下载</button><button class="gz-btn sm" @click="edit()">提出修订</button></div></div><div @click="follow"><MarkdownBody :content="selected.content"/></div><p class="gz-tiny gz-muted">{{ selected.path }} · 版本 {{ selected.version.slice(0,12) }}</p></template>
    <div v-else class="gz-empty"><h2>给下一次工作留一点积累</h2><p>选择左侧文章阅读全文，或新建一篇笔记。</p><button class="gz-btn primary" @click="edit(true)">写第一篇知识</button></div>
   </article>
  </div>
 </template>
 <div v-else class="gz-knowledge-grid"><aside class="gz-panel gz-knowledge-nav"><button v-for="revision in changes" :key="revision.id" class="gz-knowledge-link" :class="{active:selectedChange?.id===revision.id}" @click="selectedChange=revision"><span>{{ revision.path }}<small>{{ {draft:'等待审阅',accepted:'已接受',rejected:'已拒绝'}[revision.status] }} · {{ revision.reason }}</small></span></button><p v-if="!changes.length" class="gz-empty">还没有修订。打开知识后可以提出修改。</p></aside><article class="gz-panel gz-article"><template v-if="selectedChange"><div class="gz-between"><h2>{{ selectedChange.path }}</h2><button class="gz-btn sm" @click="downloadText(selectedChange!.content,selectedChange!.path.split('/').pop()||'修订.md')">下载建议正文</button></div><p>{{ selectedChange.reason }}</p><pre class="gz-diff">{{ selectedChange.diff || '正文没有变化' }}</pre><details><summary>阅读建议全文</summary><MarkdownBody :content="selectedChange.content"/></details><div v-if="selectedChange.status==='draft'" class="gz-inline gz-mt-20"><button v-if="selectedChange.source_id==='local'" class="gz-btn primary" :disabled="busy" @click="decide(true)">接受并更新原文</button><span v-else class="gz-small gz-sub">外部来源请下载修订，在原知识库受审发布。</span><button class="gz-btn" :disabled="busy" @click="decide(false)">拒绝修订</button></div></template><div v-else class="gz-empty">选择一份修订，比较修改前后的正文。</div></article></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as library from '../api/library'
import { apiError } from '../api/lifeweave'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import PageHeader from '../components/PageHeader.vue'
import MarkdownBody from '../components/MarkdownBody.vue'
import KnowledgeRelations from '../components/KnowledgeRelations.vue'
import KnowledgeNotionMirror from '../components/KnowledgeNotionMirror.vue'
import KnowledgeSemanticRelations from '../components/KnowledgeSemanticRelations.vue'
import { resolveKnowledgePath } from '../utils/knowledgeLinks'
import { safeReadingReturn } from '../utils/readingNavigation'
import { downloadText } from '../utils/download'
import { readingHtml } from '../utils/readingExport'
const { activeWorkspace } = useLifeWeaveWorkspace()
const route = useRoute(); const router = useRouter()
const artifactMode = computed(() => !!route.query.output || !!route.query.item)
const returnPath = computed(() => safeReadingReturn(route.query.returnTo, activeWorkspace.value))
const queryText = (value: unknown) => typeof value === 'string' ? value : ''
let readingGeneration = 0
let catalogGeneration = 0
const entries = shallowRef<library.Document[]>([]); const selected = shallowRef<library.Document|null>(null)
const availableSources = shallowRef<library.Source[]>([]); const sourceFilter = shallowRef('all')
const changes = shallowRef<library.Revision[]>([]); const selectedChange = shallowRef<library.Revision|null>(null)
const query = shallowRef(''); const tab = shallowRef<'documents'|'revisions'>('documents')
const editing = shallowRef(false); const busy = shallowRef(false); const error = shallowRef(''); const message = shallowRef('')
const readingBody = shallowRef<HTMLElement|null>(null)
const bundleUrl = computed(() => selected.value?.kind === 'artifact' && selected.value.itemId && selected.value.outputId
 ? `/api/lifeweave/${activeWorkspace.value}/items/${encodeURIComponent(selected.value.itemId)}/outputs/bundle?${new URLSearchParams({ outputId:selected.value.outputId,version:selected.value.version })}` : null)
function exportReading(){if(readingBody.value&&selected.value)downloadText(readingHtml(readingBody.value,activeWorkspace.value,selected.value.path,selected.value.sourceId),'知识阅读版.html','text/html;charset=utf-8')}
const form = reactive({path:'',content:'',reason:''})
const pending = computed(() => changes.value.filter(r => r.status === 'draft').length)
async function action(fn:()=>Promise<void>) { busy.value=true;error.value='';message.value=''; try { await fn() } catch(e) { error.value=apiError(e).message } finally { busy.value=false } }
async function refresh() {
 const scope=activeWorkspace.value;const ticket=++catalogGeneration
 const [catalog,revisions,sources] = await Promise.all([library.documents(scope,query.value,sourceFilter.value==='all'?undefined:sourceFilter.value),library.revisions(scope),library.sources(scope)])
 if(scope!==activeWorkspace.value || ticket!==catalogGeneration)return
 entries.value=catalog.items;changes.value=revisions;availableSources.value=sources
 if(catalog.unavailableSources.length) error.value=`来源暂不可用：${catalog.unavailableSources.join('、')}`
}
async function read(doc:Pick<library.Document,'path'|'sourceId'>) {
 await router.push({ query:{path:doc.path,source:doc.sourceId,...(returnPath.value ? {returnTo:returnPath.value} : {})} })
}
function currentOriginal() { if(selected.value?.currentSource) void read(selected.value.currentSource) }
async function loadRoute() {
 const ticket=++readingGeneration;const scope=activeWorkspace.value
 catalogGeneration++
 const item=queryText(route.query.item),output=queryText(route.query.output),path=queryText(route.query.path),version=queryText(route.query.version)
 const source=queryText(route.query.source) || queryText(route.query.sourceId) || 'local'
 const artifact=artifactMode.value
 selected.value=null;selectedChange.value=null;editing.value=false;error.value='';message.value='';busy.value=true
 try {
  if(artifact) {
   tab.value='documents'
   if(!item || !output || !version) throw new Error('工作产物链接缺少事项、产物或固定版本，请返回原步骤重新打开。')
   const doc=await library.workOutputDocument(scope,item,output,path,version)
   if(ticket===readingGeneration && scope===activeWorkspace.value) selected.value=doc
  } else {
   const [doc]=await Promise.all([path ? library.document(scope,path,source) : Promise.resolve(null),refresh()])
   if(ticket===readingGeneration && scope===activeWorkspace.value) selected.value=doc
  }
 } catch(caught) { if(ticket===readingGeneration && scope===activeWorkspace.value) error.value=apiError(caught).message }
 finally { if(ticket===readingGeneration) busy.value=false }
}
function edit(create=false) { if(create) selected.value=null;form.path=selected.value?.path??'';form.content=selected.value?.content??'# 新的知识\n\n';form.reason='';editing.value=true }
async function save() { await action(async()=> { selectedChange.value=await library.propose(activeWorkspace.value,{...form,sourceId:selected.value?.sourceId??'local',baseVersion:selected.value?.version??'new'});editing.value=false;tab.value='revisions';await refresh();message.value='修订已保存。查看差异后，再决定是否接受。' }) }
async function decide(accept:boolean) { if(!selectedChange.value)return;await action(async()=> { selectedChange.value=await library.decide(activeWorkspace.value,selectedChange.value!.id,accept);await refresh();selected.value=null;message.value=accept?'已接受修订，知识原文已更新。':'已拒绝修订，原文保持不变。' }) }
function follow(event:MouseEvent) {
 const anchor=(event.target as HTMLElement).closest('a'); if(!anchor||!selected.value)return
 const href=anchor.getAttribute('href')??''
 if(href.startsWith('#'))return
 if(artifactMode.value && href.startsWith(`/lifeweave/${activeWorkspace.value}/knowledge?`)) {
  const target=new URL(href,location.origin)
  if(target.searchParams.get('item')===selected.value.itemId && target.searchParams.get('output')===selected.value.outputId && target.searchParams.get('version')===selected.value.version){
   event.preventDefault();if(returnPath.value)target.searchParams.set('returnTo',returnPath.value)
   void router.push(target.pathname+target.search)
  }
  return
 }
 if(artifactMode.value && href.startsWith(`/api/lifeweave/${activeWorkspace.value}/items/`)) {
  const link=new URL(href,location.origin)
  const match=link.pathname.match(/^\/api\/lifeweave\/(personal|team)\/items\/([^/]+)\/outputs\/document$/)
  if(match && match[1]===activeWorkspace.value && decodeURIComponent(match[2]!)===selected.value.itemId) {
   event.preventDefault();void router.push({query:{item:selected.value.itemId,output:link.searchParams.get('outputId') || selected.value.outputId,path:link.searchParams.get('path') || '',version:link.searchParams.get('version') || selected.value.version,...(returnPath.value?{returnTo:returnPath.value}:{})}})
  }
  return
 }
 if(href.startsWith('/api/'))return
 if(/^[a-z]+:/i.test(href)){anchor.target='_blank';anchor.rel='noopener noreferrer';return}
 if(href.split('#')[0]?.endsWith('.md')) {
  if(artifactMode.value) {event.preventDefault();error.value='此相对文档没有登记到该固定产物，请返回目录选择可读取文件。';return}
  const path=resolveKnowledgePath(selected.value.path,href)
  if(!path){event.preventDefault();error.value='此链接超出了所选知识目录。';return}
  const source=availableSources.value.find(row=>row.id===selected.value?.sourceId)
  const archivePath=path.startsWith('docs/history/')||path.startsWith('docs/evidence/')
  if(source?.archiveBaseUrl && source.includedPaths && !source.includedPaths.includes(path) && archivePath){
   anchor.href=`${source.archiveBaseUrl.replace(/\/$/,'')}/${path.split('/').map(encodeURIComponent).join('/')}`
   anchor.target='_blank';anchor.rel='noopener noreferrer';return
  }
  event.preventDefault();void read({path,sourceId:selected.value.sourceId})
 }
}
onBeforeUnmount(()=>{readingGeneration++;catalogGeneration++})
watch(activeWorkspace,()=>{sourceFilter.value='all'})
watch([activeWorkspace,()=>route.query.path,()=>route.query.source,()=>route.query.sourceId,()=>route.query.item,()=>route.query.output,()=>route.query.version],()=> { void loadRoute() },{immediate:true})
</script>
<template>
 <PageHeader :title="artifactMode ? '工作产物阅读' : '知识与材料'" :subtitle="artifactMode ? '读取所选交付的固定版本；阅读不会发布为正式知识。' : '读完整正文，把有用的发现留成下一次能用的知识。'"><RouterLink v-if="returnPath" class="lw-btn" :to="returnPath">返回原步骤</RouterLink><button v-if="!artifactMode" class="lw-btn primary" @click="tab='documents';edit(true)">新建知识</button></PageHeader>
 <div v-if="!artifactMode" class="lw-tabs"><button class="lw-tab" :class="{active:tab==='documents'}" @click="tab='documents'">知识库</button><button class="lw-tab" :class="{active:tab==='revisions'}" @click="tab='revisions'">修订与历史 <span v-if="pending">{{ pending }}</span></button></div>
 <p v-if="error" class="lw-notice warning" role="alert">{{ error }}</p><p v-if="message" class="lw-notice" role="status">{{ message }}</p>
 <template v-if="tab==='documents'">
  <form v-if="!artifactMode" class="lw-toolbar" @submit.prevent="action(refresh)"><label class="lw-label">知识范围<select v-model="sourceFilter" class="lw-field" @change="action(refresh)"><option value="all">全部来源</option><option v-for="source in availableSources" :key="source.id" :value="source.id">{{ source.title }}</option></select></label><input v-model="query" class="lw-grow" aria-label="搜索知识全文" placeholder="搜索标题、路径或正文"/><button class="lw-btn" :disabled="busy">搜索</button><RouterLink class="lw-text-btn" :to="`/lifeweave/${activeWorkspace}/settings`">管理知识来源</RouterLink></form>
  <div class="lw-knowledge-grid" :class="{ 'artifact-reading': artifactMode }">
   <aside v-if="!artifactMode" class="lw-panel lw-knowledge-nav"><button v-for="doc in entries" :key="doc.sourceId+doc.path" class="lw-knowledge-link" :class="{active:selected?.path===doc.path&&selected?.sourceId===doc.sourceId}" @click="read(doc)"><span>{{ doc.title }}<small>{{ doc.sourceTitle }} · {{ doc.path }}</small></span></button><div v-if="!entries.length" class="lw-empty">还没有知识。新建一篇，或在设置中接入已有目录。</div></aside>
   <article class="lw-panel lw-article">
    <form v-if="editing" class="lw-stack" @submit.prevent="save"><label class="lw-label">文件路径<input v-model="form.path" class="lw-field" placeholder="学习/阅读笔记.md" :readonly="!!selected" required/></label><label class="lw-label">Markdown 正文<textarea v-model="form.content" class="lw-field lw-large-textarea" rows="18" required></textarea></label><label class="lw-label">修改说明<input v-model="form.reason" class="lw-field" placeholder="这次补充或修正了什么" required/></label><div class="lw-inline"><button class="lw-btn primary" :disabled="busy">保存修订，查看差异</button><button type="button" class="lw-btn" @click="editing=false">取消</button></div></form>
    <template v-else-if="selected"><div class="lw-between"><span class="lw-small lw-muted">{{ selected.sourceTitle }} · {{ artifactMode ? '工作产物 · 固定版本' : selected.writable?'工作台管理':'外部只读来源' }}</span><div class="lw-inline"><button class="lw-btn sm" @click="downloadText(selected!.content,selected!.path.split('/').pop()||'知识.md')">下载原文</button><button class="lw-btn sm" @click="exportReading">下载阅读版（需连接工作台）</button><a v-if="bundleUrl" class="lw-btn sm" :href="bundleUrl" download>下载完整包（含资源）</a><button v-if="selected.currentSource" class="lw-btn sm" @click="currentOriginal">查看当前原文</button><button v-if="!artifactMode" class="lw-btn sm" @click="edit()">提出修订</button></div></div><p class="document-identity">{{ selected.path }} · 版本 <code>{{ selected.version }}</code></p><div ref="readingBody" class="document-body" @click="follow"><MarkdownBody :content="selected.content" :references="selected.references" :workspace="activeWorkspace" :plain-text="selected.contentType !== 'text/markdown' && !/\.(md|markdown)$/i.test(selected.path)" outline /></div><p class="lw-tiny lw-muted">{{ selected.path }} · 版本 {{ selected.version.slice(0,12) }}</p><KnowledgeRelations v-if="!artifactMode" :workspace="activeWorkspace" :source-id="selected.sourceId" :path="selected.path" :version="selected.version" /><KnowledgeSemanticRelations v-if="!artifactMode" :workspace="activeWorkspace" :source-id="selected.sourceId" :path="selected.path" :version="selected.version" /><KnowledgeNotionMirror v-if="!artifactMode" :workspace="activeWorkspace" :document="selected" /></template>
    <p v-else-if="busy" role="status" class="lw-muted">正在读取文档…</p><p v-else-if="artifactMode" class="lw-empty">此固定产物尚不可读。请核对链接版本或返回原步骤选择其他文件。</p><div v-else class="lw-empty"><h2>给下一次工作留一点积累</h2><p>选择左侧文章阅读全文，或新建一篇笔记。</p><button class="lw-btn primary" @click="edit(true)">写第一篇知识</button></div>
   </article>
  </div>
 </template>
 <div v-else class="lw-knowledge-grid"><aside class="lw-panel lw-knowledge-nav"><button v-for="revision in changes" :key="revision.id" class="lw-knowledge-link" :class="{active:selectedChange?.id===revision.id}" @click="selectedChange=revision"><span>{{ revision.path }}<small>{{ {draft:'等待审阅',accepted:'已接受',rejected:'已拒绝'}[revision.status] }} · {{ revision.reason }}</small></span></button><p v-if="!changes.length" class="lw-empty">还没有修订。打开知识后可以提出修改。</p></aside><article class="lw-panel lw-article"><template v-if="selectedChange"><div class="lw-between"><h2>{{ selectedChange.path }}</h2><button class="lw-btn sm" @click="downloadText(selectedChange!.content,selectedChange!.path.split('/').pop()||'修订.md')">下载建议正文</button></div><p>{{ selectedChange.reason }}</p><pre class="lw-diff">{{ selectedChange.diff || '正文没有变化' }}</pre><details><summary>阅读建议全文</summary><MarkdownBody :content="selectedChange.content" :references="selectedChange.references" :workspace="activeWorkspace"/></details><div v-if="selectedChange.status==='draft'" class="lw-inline lw-mt-20"><button v-if="selectedChange.source_id==='local'" class="lw-btn primary" :disabled="busy" @click="decide(true)">接受并更新原文</button><span v-else class="lw-small lw-sub">外部来源请下载修订，在原知识库受审发布。</span><button class="lw-btn" :disabled="busy" @click="decide(false)">拒绝修订</button></div></template><div v-else class="lw-empty">选择一份修订，比较修改前后的正文。</div></article></div>
</template>

<style scoped>
.artifact-reading { display:block; }
.artifact-reading .lw-article { max-width:1100px; margin:0 auto; }
.document-body { max-width:940px; margin:24px auto; min-width:0; }
.document-identity { margin-top:18px;color:#657b91;font-size:12px;overflow-wrap:anywhere; }
.document-identity code { white-space:normal; }
</style>

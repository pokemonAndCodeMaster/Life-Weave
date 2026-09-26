<script setup lang="ts">
import { reactive, shallowRef, watch } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
import * as library from '../api/library'
import { useLifeWeaveWorkspace } from '../composables/useLifeWeaveWorkspace'
import ResearchArchiveSettings from '../components/ResearchArchiveSettings.vue'
import PageHeader from '../components/PageHeader.vue'
const {activeWorkspace}=useLifeWeaveWorkspace()
interface Settings { localWorker:{enabled:boolean;running:boolean}; executors:Record<string,{available:boolean;version?:string;reason?:string}>;linearConfigured:boolean;existingCredentialAvailable:boolean;identityMode:string }
const settings=shallowRef<Settings|null>(null);const sources=shallowRef<library.Source[]>([])
const error=shallowRef('');const message=shallowRef('');const busy=shallowRef(false)
const methodRoot=shallowRef('');const methodCatalog=shallowRef<{roots:string[];items:{id:string;title:string}[]}>({roots:[],items:[]})
const source=reactive({title:'',root:''});const connection=reactive({token:'',credentialFile:''})
const endpoint=()=>`/lifeweave/${activeWorkspace.value}`
async function action(fn:()=>Promise<void>){error.value='';message.value='';busy.value=true;try{await fn()}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
async function load(){const [s,r]=await Promise.all([http.get<Settings>(`${endpoint()}/settings`),library.sources(activeWorkspace.value)]);settings.value=s.data;sources.value=r;methodCatalog.value=(await http.get(`${endpoint()}/methods`)).data}
async function connect(){await action(async()=>{const result=await http.post(`${endpoint()}/connections/linear`,connection);connection.token='';message.value=`已连接 ${result.data.organization.name} · ${result.data.viewer.name}`;await load()})}
async function addSource(){await action(async()=>{await http.post(`${endpoint()}/library/sources`,source);source.title='';source.root='';await load();message.value='已接入知识目录，原文件保持只读。'})}
async function configureWorker(enabled:boolean){await action(async()=>{await http.put(`${endpoint()}/settings/local-worker`,{enabled,useLocalAccount:enabled});await load();message.value=enabled?'本机执行已启用，使用这台电脑当前的 CLI 账号。':'本机执行已停用。'})}
async function addMethods(){await action(async()=>{await http.post(`${endpoint()}/methods/roots`,{root:methodRoot.value});methodRoot.value='';await load();message.value='已接入工作方法，委托时可以按需选择。'})}
watch(activeWorkspace,()=>void action(load),{immediate:true})
</script>
<template>
<PageHeader title="设置与连接" subtitle="把已有知识、执行工具和工作系统接进来。"/>
<p v-if="error" class="lw-notice warning" role="alert">{{error}}</p><p v-if="message" class="lw-notice" role="status">{{message}}</p>
<div class="lw-settings-grid">
<section class="lw-panel pad"><h2>知识来源</h2><p class="lw-small lw-sub">工作台知识可以受审修改。已有项目的知识目录只读接入，保留原来的维护位置。</p><div v-for="entry in sources" :key="entry.id" class="lw-source-row"><strong>{{entry.title}}</strong><span class="lw-small">{{entry.writable?'工作台管理':'只读'}}</span><code>{{entry.root}}</code></div><form class="lw-stack lw-mt-20" @submit.prevent="addSource"><label class="lw-label">来源名称<input v-model="source.title" class="lw-field" placeholder="例如：我的项目知识" required/></label><label class="lw-label">本机 Markdown 目录<input v-model="source.root" class="lw-field" placeholder="/path/to/knowledge" required/></label><button class="lw-btn" :disabled="busy">接入知识目录</button></form></section>
<section class="lw-panel pad"><h2>Linear</h2><p class="lw-small lw-sub">{{settings?.linearConfigured?'已保存连接配置。':'尚未连接。'}} 按需导入已有事项，在发送成果前查看发布预览。</p><form class="lw-stack" @submit.prevent="connect"><label class="lw-label">个人 API Key<input v-model="connection.token" class="lw-field" type="password" autocomplete="new-password" placeholder="只保存在这台电脑，不回传到页面"/></label><label class="lw-label">或使用凭证文件<input v-model="connection.credentialFile" class="lw-field" placeholder="仅当前用户可读的文件路径"/></label><div class="lw-inline"><button class="lw-btn primary" :disabled="busy">保存并检查连接</button><RouterLink class="lw-btn" :to="`/lifeweave/${activeWorkspace}/connections`">打开 Linear 事项</RouterLink></div></form><p class="lw-tiny lw-muted">获取方式：Linear → Settings → Security & access → Personal API keys。凭证保存在本机私有运行目录。</p></section>
<section class="lw-panel pad"><h2>工作方法 · Skills</h2><p class="lw-small lw-sub">接入已有 Skills 目录，在每次委托中选一套方法。正文和支持文件会固定到任务目录。</p><p v-for="root in methodCatalog.roots" :key="root" class="lw-small"><code>{{root}}</code></p><div class="lw-inline"><span v-for="method in methodCatalog.items" :key="method.id" class="lw-tag">{{method.title}}</span></div><form class="lw-stack lw-mt-20" @submit.prevent="addMethods"><label class="lw-label">Skills 根目录<input v-model="methodRoot" class="lw-field" placeholder="/path/to/project/.agents/skills" required/></label><button class="lw-btn" :disabled="busy">接入工作方法</button></form></section><section class="lw-panel pad"><h2>AI 执行</h2><div v-for="(engine,name) in settings?.executors" :key="name" class="lw-source-row"><strong>{{name}}</strong><span>{{engine.available?'已安装':'不可用'}}</span><p class="lw-small lw-sub">{{engine.version||engine.reason}}</p></div><div class="lw-notice neutral"><div><strong>本机执行：{{settings?.localWorker.enabled?'已启用':'未启用'}}</strong><p>启用后，本空间的委托使用这台电脑当前的 Codex / OpenCode 账号。两个空间的工作目录和记录分别保存。</p><button class="lw-btn" :disabled="busy" @click="configureWorker(!settings?.localWorker.enabled)">{{settings?.localWorker.enabled?'停用本机执行':'使用本机账号启用执行'}}</button></div></div><p class="lw-small lw-sub">个人空间自带本机执行节点。账号由对应 CLI 管理。委托不选项目时使用空白任务目录；选择项目时使用独立检出，不直接修改原工作目录。</p><RouterLink class="lw-text-btn" :to="`/lifeweave/${activeWorkspace}/maintenance`">查看能力与评测 →</RouterLink></section>
<ResearchArchiveSettings :workspace="activeWorkspace" />
<section class="lw-panel pad"><h2>数据与运行</h2><p>当前使用方式：{{settings?.identityMode||'正在检查'}}</p><p class="lw-small lw-sub">个人与团队空间分别保存内容。目前适用于本机使用，团队成员登录和远程访问尚未开放。</p><p class="lw-small">启动、停止和备份命令见项目 README。数据库和运行产物保存在此应用自己的目录中。</p><code class="lw-command">python scripts/workbench.py backup</code><p class="lw-tiny lw-muted">备份包括数据库与工作台知识；外部知识按原项目方式备份。</p></section>
</div>
</template>

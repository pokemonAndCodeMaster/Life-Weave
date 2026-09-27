<script setup lang="ts">
import { computed, nextTick, shallowRef, useId, watch } from 'vue'
import MermaidDiagram from './reading/MermaidDiagram.vue'
import ReadingMediaDialog from './reading/ReadingMediaDialog.vue'
import type { WorkspaceKind } from '../types'
import { Marked, type Tokens } from 'marked'
import DOMPurify from 'dompurify'
import katex from 'katex'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'
import type { ReferenceMap } from '../api/library'
const props=defineProps<{content:string;sourceBase?:string;assetBase?:string;references?:ReferenceMap|null;workspace?:WorkspaceKind;outline?:boolean;plainText?:boolean}>()
const root = shallowRef<HTMLElement | null>(null)
const imagePreview = shallowRef<{ source: string; title: string } | null>(null)
const diagrams = shallowRef<Array<{ id: string; source: string; target: HTMLElement }>>([])
const copyMessage = shallowRef('')
const identity = useId().replace(/[^a-zA-Z0-9_-]/g, '-')
function mappedUrl(value: string | undefined, kind: 'image' | 'link'): string | null {
 if (!value || !value.startsWith('/') || value.startsWith('//')) return null
 const scope = props.workspace || location.pathname.match(/^\/lifeweave\/(personal|team)\//)?.[1] || (props.assetBase || props.sourceBase || '').match(/^\/api\/lifeweave\/(personal|team)\//)?.[1]
 const parsed = new URL(value, location.origin)
 if (parsed.origin !== location.origin) return null
 const internal = parsed.pathname.match(/^\/lifeweave\/(personal|team)\/knowledge$/)
 if(kind==='link' && internal && (!scope || scope===internal[1]) && ['item','output','path','version'].every(key=>parsed.searchParams.has(key))) return value
 const match = parsed.pathname.match(/^\/api\/lifeweave\/(personal|team)\/(.*)$/)
 if (!match || (scope && match[1] !== scope)) return null
 const path = match[2]!
 const allowed = kind === 'image'
  ? /^(?:runs\/[^/]+\/assets|library\/asset|items\/[^/]+\/outputs\/asset)$/.test(path)
  : /^(?:runs\/[^/]+\/source|library\/document|items\/[^/]+\/outputs\/document)$/.test(path)
 return allowed && parsed.searchParams.has('path') ? value : null
}
function decoded(value:string){try{return decodeURIComponent(value)}catch{return value}}
const rendered=computed(()=>{
 const diagramSources = new Map<string, string>()
 const formulas=new Map<string,{text:string;displayMode:boolean}>()
 const placeholder=(token:Tokens.Generic)=>{
  const id=crypto.randomUUID();formulas.set(id,{text:String(token.text),displayMode:!!token.displayMode})
  return `<span data-lw-formula="${id}"></span>`
 }
 const math=markedKatex({nonStandard:true})
 // Preserve equations before Markdown can interpret subscripts as emphasis.
 // User HTML is sanitized independently of the trusted KaTeX layout output.
 for(const extension of math.extensions??[])if('renderer' in extension)extension.renderer=placeholder
 const renderer=new Marked(math,{renderer:{code(token){
  if (token.lang?.trim().toLowerCase() !== 'mermaid') return false
  const id = crypto.randomUUID(); diagramSources.set(id, token.text)
  return `<div data-lw-diagram="${id}"></div>`
 }},extensions:[{
  name:'latexDelimited',level:'inline',start:(source:string)=>source.search(/\\[([]/),
  tokenizer(source:string){
   const match=source.match(/^\\\[([\s\S]*?)\\\]/)||source.match(/^\\\(([\s\S]*?)\\\)/)
   if(match)return {type:'latexDelimited',raw:match[0],text:match[1],displayMode:source.startsWith('\\[')}
  },renderer:placeholder,
 }],walkTokens(token){
  if(token.type!=='link')return
  const href=String(token.href??'')
  const mapped=mappedUrl(props.references?.links[decoded(href)], 'link')
  if(mapped){token.href=mapped;return}
  if(!props.sourceBase)return
  if(!/^[a-z]+:/i.test(href)&&!href.startsWith('#')&&!href.startsWith('/')){
   const path=decoded(href.split('#')[0]!).replace(/:\d+(?:-\d+)?$/,'')
   token.href=props.sourceBase+'?path='+encodeURIComponent(path)
  }
 }})
 const plain=window.document.createElement('code');plain.textContent=props.content || ''
 const parsed=props.plainText ? `<pre>${plain.outerHTML}</pre>` : renderer.parse(props.content||'',{async:false}) as string
 const config={FORBID_TAGS:['style','iframe','form','input','button','video','audio','source','picture','object','embed'],FORBID_ATTR:['style','srcdoc','srcset'],USE_PROFILES:{html:true}}
 const clean=DOMPurify.sanitize(parsed,config)
 const document=new DOMParser().parseFromString(clean,'text/html')
 for(const img of document.querySelectorAll('img')){
  const src=img.getAttribute('src')??''
  const path=decoded(src)
  const alt=img.getAttribute('alt')||'图片'
  const mapped=mappedUrl(props.references?.images[path], 'image')
  const local=props.assetBase && /^\/api\/lifeweave\/(personal|team)\/runs\/[^/]+\/assets$/.test(props.assetBase) && mappedUrl(props.assetBase+'?path='+encodeURIComponent(path), 'image')
  if(mapped){
   img.setAttribute('src',mapped);img.setAttribute('loading','lazy');img.setAttribute('referrerpolicy','no-referrer')
  }else if(local && path && !/^[a-z][a-z0-9+.-]*:/i.test(path) && !path.startsWith('/') && !path.split('/').some(p=>p==='..'||p.startsWith('.'))){
   img.setAttribute('src',props.assetBase+'?path='+encodeURIComponent(path))
   img.setAttribute('loading','lazy');img.setAttribute('referrerpolicy','no-referrer')
  }else{
   const note=document.createElement('span'); note.className='lw-image-unavailable'
   note.textContent=alt+'（未加载外部或不可用图片）'
   if(/^https?:\/\//i.test(src)){
    const link=document.createElement('a');link.href=src;link.textContent='查看图片原出处';note.append(' ',link)
   }
   img.replaceWith(note)
  }
 }
 for(const link of document.querySelectorAll('a[href]')){
  const href=link.getAttribute('href')??''
  if(/^https?:/i.test(href)||/^\/api\/lifeweave\/(personal|team)\/runs\//.test(href)||(props.sourceBase&&href.startsWith(props.sourceBase+'?'))){
   link.setAttribute('target','_blank');link.setAttribute('rel','noopener noreferrer')
  }
 }
 // Only KaTeX's renderer can add formula layout styles; trust:false prohibits
 // commands such as \htmlStyle, HTML links and external image insertion.
 document.body.innerHTML=DOMPurify.sanitize(document.body.innerHTML,{...config,ADD_ATTR:['target','rel']})
 for(const element of document.querySelectorAll<HTMLElement>('[data-lw-formula]')){
  const formula=formulas.get(element.dataset.lwFormula??'')
  if(formula){
   try { katex.render(formula.text,element,{displayMode:formula.displayMode,throwOnError:true,trust:false,strict:'ignore',maxExpand:1000}) }
   catch(error){
    element.replaceChildren();const note=document.createElement('span');note.className='formula-error-note';note.textContent='公式未能排版，保留原式：'
    const original=document.createElement('code');original.className='katex-error';original.textContent=formula.text;original.title=error instanceof Error ? error.message : '公式语法错误'
    element.append(note,original)
   }
  }
  element.removeAttribute('data-lw-formula')
 }
 const outline: Array<{ id: string; title: string; level: number }> = []
 for (const [index, heading] of Array.from(document.querySelectorAll<HTMLElement>('h1,h2,h3')).entries()) {
  const id = `lw-${identity}-section-${index}`; heading.id = id; heading.tabIndex = -1
  outline.push({ id, title: heading.textContent || '章节', level: Number(heading.tagName.slice(1)) })
 }
 for (const table of document.querySelectorAll('table')) {
  const wrapper=document.createElement('div');wrapper.className='reading-table';wrapper.tabIndex=0
  wrapper.setAttribute('role','region');wrapper.setAttribute('aria-label','表格，可横向滚动')
  table.replaceWith(wrapper);wrapper.append(table)
 }
 for (const pre of document.querySelectorAll('pre')) {
  const code=pre.querySelector('code');if(!code)continue
  const wrapper=document.createElement('div');wrapper.className='reading-code'
  const copy=document.createElement('button');copy.type='button';copy.className='reading-copy';copy.textContent=props.plainText ? '复制原文' : '复制代码'
  pre.replaceWith(wrapper);wrapper.append(copy,pre)
 }
 for (const img of document.querySelectorAll('img')) {
  const button=document.createElement('button');button.type='button';button.className='reading-image-open'
  button.setAttribute('aria-label',`放大图片：${img.alt || '图片'}`)
  img.replaceWith(button);button.append(img)
 }
 return { html:document.body.innerHTML, outline, diagramSources }
})
watch(rendered, async current => {
 diagrams.value=[];imagePreview.value=null;copyMessage.value=''
 await nextTick()
 if (current !== rendered.value) return
 diagrams.value=Array.from(root.value?.querySelectorAll<HTMLElement>('[data-lw-diagram]') || []).flatMap(target => {
  const id=target.dataset.lwDiagram!;const source=current.diagramSources.get(id)
  return source === undefined ? [] : [{ id, source, target }]
 })
}, { immediate:true, flush:'post' })
async function activate(event: MouseEvent) {
 const element = event.target instanceof Element ? event.target : null
 const button = element?.closest<HTMLButtonElement>('.reading-image-open')
 const image = button?.querySelector('img')
 if (image) { event.preventDefault(); imagePreview.value={source:image.src,title:image.alt || '图片'}; return }
 const copy=element?.closest<HTMLButtonElement>('.reading-copy')
 if (copy) {
  const text=copy.parentElement?.querySelector('code')?.textContent || ''
  const current=rendered.value
  try { await navigator.clipboard.writeText(text); if(current===rendered.value) copyMessage.value=props.plainText ? '原文已复制' : '代码已复制' }
  catch { if(current===rendered.value) copyMessage.value='未能复制，请选中代码后手动复制。' }
 }
}
function section(id:string) { const heading=document.getElementById(id);heading?.focus({preventScroll:true});heading?.scrollIntoView({block:'start'}) }

function failedImage(event:Event){
 const image=event.target
 if(!(image instanceof HTMLImageElement))return
 const notice=document.createElement('span');notice.className='lw-image-unavailable'
 notice.textContent=(image.alt||'图片')+'（加载失败；文件可能缺失或文档版本已变化，请重新读取文档）';(image.closest('.reading-image-open') || image).replaceWith(notice)
}
</script>
<template>
 <div class="markdown-reading">
  <p v-for="warning in references?.warnings||[]" :key="warning" class="lw-notice warning">{{ warning }}</p>
  <nav v-if="outline && rendered.outline.length > 1" class="reading-outline" aria-label="文档目录"><strong>本文目录</strong><ol><li v-for="heading in rendered.outline" :key="heading.id" :class="{ nested: heading.level === 3 }"><a :href="`#${heading.id}`" @click.prevent="section(heading.id)">{{ heading.title }}</a></li></ol></nav>
  <p v-if="copyMessage" role="status" class="reading-copy-message">{{ copyMessage }}</p>
  <div ref="root" class="lw-markdown" @click="activate" @error.capture="failedImage" v-html="rendered.html"></div>
  <Teleport v-for="diagram in diagrams" :key="diagram.id" :to="diagram.target"><MermaidDiagram :source="diagram.source" /></Teleport>
  <ReadingMediaDialog v-if="imagePreview" :image="imagePreview.source" :title="imagePreview.title" @close="imagePreview=null" />
 </div>
</template>
<style scoped>
.markdown-reading,.lw-markdown { min-width:0;overflow-wrap:anywhere }
.lw-markdown { line-height:1.85; }
.lw-markdown :deep(h1),.lw-markdown :deep(h2),.lw-markdown :deep(h3) { line-height:1.4;scroll-margin-top:90px; }
.lw-markdown :deep(img) { max-width:100%;height:auto; }
.lw-markdown :deep(.katex-display) { max-width:100%;overflow-x:auto;overflow-y:hidden;padding:.4em 0; }
.lw-markdown :deep(.katex-error) { white-space:pre-wrap;overflow-wrap:anywhere; }
.lw-markdown :deep(.lw-image-unavailable) { display:inline-block;color:var(--lw-muted,#667085);font-size:.9em; }
.lw-markdown :deep(.reading-table) { max-width:100%;overflow-x:auto;margin:20px 0; }
.lw-markdown :deep(table) { display:table;width:max-content;min-width:100%;max-width:none;overflow:visible;border-collapse:collapse; }
.lw-markdown :deep(th),.lw-markdown :deep(td) { padding:10px 14px;border:1px solid #dce5ef;min-width:120px;max-width:400px;text-align:left; }
.lw-markdown :deep(th) { background:#f4f7fb;font-weight:650; }
.lw-markdown :deep(.reading-code) { min-width:0;position:relative; }
.lw-markdown :deep(pre) { max-width:100%;overflow:auto;white-space:pre;padding:18px 16px;background:#f6f8fb;border-radius:7px; }
.lw-markdown :deep(.reading-copy) { display:block;margin-left:auto;border:1px solid #d4dfeb;border-radius:5px;padding:4px 8px;background:#fff;color:#385773;cursor:pointer;font-size:12px; }
.lw-markdown :deep(.reading-image-open) { display:block;max-width:100%;border:0;padding:0;background:transparent;cursor:zoom-in; }
.reading-outline { padding:14px 18px;margin-bottom:24px;border:1px solid #dce5ef;border-radius:8px;font-size:13px;color:#526d86; }
.reading-outline ol { margin:8px 0 0;padding-left:20px; }
.reading-outline li { margin-top:5px; }
.reading-outline li.nested { margin-left:12px; }
.reading-outline a { color:#396c97; }
.reading-copy-message { color:#526d86;font-size:12px; }
</style>

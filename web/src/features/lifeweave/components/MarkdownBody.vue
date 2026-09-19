<script setup lang="ts">
import { computed } from 'vue'
import { Marked, type Tokens } from 'marked'
import DOMPurify from 'dompurify'
import katex from 'katex'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'
const props=defineProps<{content:string;sourceBase?:string;assetBase?:string}>()
const html=computed(()=>{
 const formulas=new Map<string,{text:string;displayMode:boolean}>()
 const placeholder=(token:Tokens.Generic)=>{
  const id=crypto.randomUUID();formulas.set(id,{text:String(token.text),displayMode:!!token.displayMode})
  return `<span data-lw-formula="${id}"></span>`
 }
 const math=markedKatex({nonStandard:true})
 // Preserve equations before Markdown can interpret subscripts as emphasis.
 // User HTML is sanitized independently of the trusted KaTeX layout output.
 for(const extension of math.extensions??[])if('renderer' in extension)extension.renderer=placeholder
 const renderer=new Marked(math,{extensions:[{
  name:'latexDelimited',level:'inline',start:(source:string)=>source.search(/\\[([]/),
  tokenizer(source:string){
   const match=source.match(/^\\\[([\s\S]*?)\\\]/)||source.match(/^\\\(([\s\S]*?)\\\)/)
   if(match)return {type:'latexDelimited',raw:match[0],text:match[1],displayMode:source.startsWith('\\[')}
  },renderer:placeholder,
 }],walkTokens(token){
  if(token.type!=='link'||!props.sourceBase)return
  const href=String(token.href??'')
  if(!/^[a-z]+:/i.test(href)&&!href.startsWith('#')&&!href.startsWith('/')){
   const path=href.split('#')[0]!.replace(/:\d+(?:-\d+)?$/,'')
   token.href=props.sourceBase+'?path='+encodeURIComponent(path)
  }
 }})
 const parsed=renderer.parse(props.content||'',{async:false}) as string
 const config={FORBID_TAGS:['style','iframe','form','input','button','video','audio','source','picture','object','embed'],FORBID_ATTR:['style','srcdoc','srcset'],USE_PROFILES:{html:true}}
 const clean=DOMPurify.sanitize(parsed,config)
 const document=new DOMParser().parseFromString(clean,'text/html')
 for(const img of document.querySelectorAll('img')){
  const src=img.getAttribute('src')??''
  const alt=img.getAttribute('alt')||'图片'
  const local=props.assetBase && /^\/api\/lifeweave\/(personal|team)\/runs\/[^/]+\/assets$/.test(props.assetBase)
  if(local && src && !/^[a-z][a-z0-9+.-]*:/i.test(src) && !src.startsWith('/') && !src.split('/').some(p=>p==='..'||p.startsWith('.'))){
   img.setAttribute('src',props.assetBase+'?path='+encodeURIComponent(src))
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
  if(/^https?:/i.test(href)||(props.sourceBase&&href.startsWith(props.sourceBase+'?'))){
   link.setAttribute('target','_blank');link.setAttribute('rel','noopener noreferrer')
  }
 }
 // Only KaTeX's renderer can add formula layout styles; trust:false prohibits
 // commands such as \htmlStyle, HTML links and external image insertion.
 document.body.innerHTML=DOMPurify.sanitize(document.body.innerHTML,{...config,ADD_ATTR:['target','rel']})
 for(const element of document.querySelectorAll<HTMLElement>('[data-lw-formula]')){
  const formula=formulas.get(element.dataset.lwFormula??'')
  if(formula)katex.render(formula.text,element,{displayMode:formula.displayMode,throwOnError:false,trust:false,strict:'ignore',maxExpand:1000})
  element.removeAttribute('data-lw-formula')
 }
 return document.body.innerHTML
})
function failedImage(event:Event){
 const image=event.target
 if(!(image instanceof HTMLImageElement))return
 const notice=document.createElement('span');notice.className='lw-image-unavailable'
 notice.textContent=(image.alt||'图片')+'（加载失败；请核对本轮资产）';image.replaceWith(notice)
}
</script>
<template><div class="lw-markdown" @error.capture="failedImage" v-html="html"></div></template>
<style scoped>
.lw-markdown :deep(img){max-width:100%;height:auto}
.lw-markdown :deep(.katex-display){max-width:100%;overflow-x:auto;overflow-y:hidden;padding:.4em 0}
.lw-markdown :deep(.lw-image-unavailable){display:inline-block;color:var(--lw-muted,#667085);font-size:.9em}
</style>

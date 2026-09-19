<script setup lang="ts">
import { computed } from 'vue'
import { Marked } from 'marked'
import DOMPurify from 'dompurify'
const props=defineProps<{content:string;sourceBase?:string}>()
const html=computed(()=>{
 const renderer=new Marked({walkTokens(token){
  if(token.type!=='link'||!props.sourceBase)return
  const href=String(token.href??'')
  if(!/^[a-z]+:/i.test(href)&&!href.startsWith('#')&&!href.startsWith('/')){
   const path=href.split('#')[0]!.replace(/:\d+(?:-\d+)?$/,'')
   token.href=props.sourceBase+'?path='+encodeURIComponent(path)
  }
 }})
 const parsed=renderer.parse(props.content||'',{async:false}) as string
 const config={FORBID_TAGS:['style','iframe','form','input','button'],FORBID_ATTR:['style','srcdoc'],USE_PROFILES:{html:true}}
 const clean=DOMPurify.sanitize(parsed,config)
 const document=new DOMParser().parseFromString(clean,'text/html')
 for(const link of document.querySelectorAll('a[href]')){
  const href=link.getAttribute('href')??''
  if(/^https?:/i.test(href)||(props.sourceBase&&href.startsWith(props.sourceBase+'?'))){
   link.setAttribute('target','_blank');link.setAttribute('rel','noopener noreferrer')
  }
 }
 return DOMPurify.sanitize(document.body.innerHTML,{...config,ADD_ATTR:['target','rel']})
})
</script>
<template><div class="lw-markdown" v-html="html"></div></template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
const props = defineProps<{ content: string; sourceBase?:string }>()
const html = computed(() => {
 const clean=DOMPurify.sanitize(marked.parse(props.content || '', { async: false }) as string, { FORBID_TAGS: ['style','iframe','form','input','button'], FORBID_ATTR: ['style','srcdoc'] })
 const document=new DOMParser().parseFromString(clean,'text/html')
 for(const link of document.querySelectorAll('a[href]')){
  const href=link.getAttribute('href')??''
  if(props.sourceBase&&!/^[a-z]+:/i.test(href)&&!href.startsWith('#')&&!href.startsWith('/')){
   const path=href.split('#')[0]!.replace(/:\d+(?:-\d+)?$/,'')
   link.setAttribute('href',props.sourceBase+'?path='+encodeURIComponent(path))
   link.setAttribute('target','_blank');link.setAttribute('rel','noopener noreferrer')
  }else if(/^https?:/i.test(href)){link.setAttribute('target','_blank');link.setAttribute('rel','noopener noreferrer')}
 }
 return document.body.innerHTML
})
</script>
<template><div class="gz-markdown" v-html="html"></div></template>

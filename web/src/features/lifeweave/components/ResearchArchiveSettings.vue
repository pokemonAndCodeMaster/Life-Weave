<script setup lang="ts">
import { reactive, shallowRef, watch } from 'vue'
import { http } from '@/shared/api/http'
import { apiError } from '../api/lifeweave'
const props=defineProps<{workspace:string}>()
const form=reactive({enabled:false,githubRepository:'',linearProjectId:''})
const busy=shallowRef(false);const message=shallowRef('');const loaded=shallowRef(false)
let generation=0
watch(()=>props.workspace,async()=>{const ticket=++generation;loaded.value=false;message.value='';try{const r=await http.get(`/lifeweave/${props.workspace}/archive-settings`);if(ticket===generation){Object.assign(form,r.data);loaded.value=true}}catch(e){if(ticket===generation)message.value=apiError(e).message}},{immediate:true})
async function save(){const ticket=generation;busy.value=true;try{await http.put(`/lifeweave/${props.workspace}/archive-settings`,{enabled:form.enabled,githubRepository:form.githubRepository,linearProjectId:form.linearProjectId});if(ticket===generation)message.value='已保存。开启后新成功版本自动归档；以前的版本可在成果页点击立即归档。'}catch(e){if(ticket===generation)message.value=apiError(e).message}finally{if(ticket===generation)busy.value=false}}
</script>
<template>
 <section class="lw-panel pad"><h2>研究成果自动归档</h2>
  <p>每次成功生成报告后，保存正文、图片和引用材料；GitHub 与 Linear 分别显示归档结果，不覆盖你在远端修改的旧版本。</p>
  <form v-if="loaded" class="lw-stack" @submit.prevent="save">
   <label><input v-model="form.enabled" type="checkbox" :disabled="busy" />成功生成后自动归档本空间的研究成果</label>
   <label class="lw-label">GitHub 仓库地址<input v-model="form.githubRepository" class="lw-field" placeholder="https://github.com/用户名/仓库" :disabled="busy" /></label>
   <p class="lw-small">使用本机 Git SSH 认证，写入 research-archive 分支；不会替你提交工作区中的代码修改。</p>
   <label class="lw-label">Linear 项目 ID<input v-model="form.linearProjectId" class="lw-field" :disabled="busy" /></label>
   <p class="lw-small">使用已有 Linear 连接；每轮生成独立版本文档和附件。归档不等于接受为正式知识。</p>
   <button class="lw-btn" :disabled="busy">保存归档设置</button>
  </form><p v-if="message" role="status">{{message}}</p>
 </section>
</template>

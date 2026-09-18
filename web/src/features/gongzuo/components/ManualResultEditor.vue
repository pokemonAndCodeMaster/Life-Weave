<script setup lang="ts">
import {reactive,shallowRef} from 'vue'
import {http} from '@/shared/api/http'
import {apiError} from '../api/gongzuo'
import {useGongzuoWorkspace} from '../composables/useGongzuoWorkspace'
import GongzuoModal from './GongzuoModal.vue'
import type {WorkItem} from '../types'
const props=defineProps<{item:WorkItem}>();const emit=defineEmits<{close:[];saved:[]}>()
const {activeWorkspace,load,loadItem}=useGongzuoWorkspace()
const form=reactive({title:'',content:'',verification:'',environment:'本机人工工作'})
const busy=shallowRef(false);const error=shallowRef('')
async function save(){busy.value=true;error.value='';try{await http.post(`/gongzuo/${activeWorkspace.value}/items/${props.item.id}/manual-results`,form);await load(activeWorkspace.value,true);await loadItem(props.item.id,true);emit('saved')}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
</script>
<template><GongzuoModal title="登记工作成果" wide @close="emit('close')"><form id="manual-result" class="gz-stack" @submit.prevent="save"><p v-if="error" class="gz-notice warning" role="alert">{{error}}</p><label class="gz-label">成果名称<input v-model="form.title" class="gz-field" required/></label><label class="gz-label">成果正文（Markdown）<textarea v-model="form.content" class="gz-field" rows="10" required/></label><label class="gz-label">验证了什么、有什么未覆盖<textarea v-model="form.verification" class="gz-field" rows="3" required/></label><label class="gz-label">验证环境或来源<input v-model="form.environment" class="gz-field" required/></label><p class="gz-small gz-sub">保存后形成固定版本的成果和待审证据。阅读与接受证据后，才可完成事项。</p></form><template #footer><button class="gz-btn" @click="emit('close')">取消</button><button class="gz-btn primary" form="manual-result" :disabled="busy">保存成果</button></template></GongzuoModal></template>

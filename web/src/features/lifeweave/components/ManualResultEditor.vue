<script setup lang="ts">
import {reactive,shallowRef} from 'vue'
import {http} from '@/shared/api/http'
import {apiError} from '../api/lifeweave'
import {useLifeWeaveWorkspace} from '../composables/useLifeWeaveWorkspace'
import LifeWeaveModal from './LifeWeaveModal.vue'
import type {WorkItem} from '../types'
const props=defineProps<{item:WorkItem}>();const emit=defineEmits<{close:[];saved:[]}>()
const {activeWorkspace,load,loadItem}=useLifeWeaveWorkspace()
const form=reactive({title:'',content:'',verification:'',environment:'本机人工工作'})
const busy=shallowRef(false);const error=shallowRef('')
async function save(){busy.value=true;error.value='';try{await http.post(`/lifeweave/${activeWorkspace.value}/items/${props.item.id}/manual-results`,form);await load(activeWorkspace.value,true);await loadItem(props.item.id,true);emit('saved')}catch(e){error.value=apiError(e).message}finally{busy.value=false}}
</script>
<template><LifeWeaveModal title="登记工作成果" wide @close="emit('close')"><form id="manual-result" class="lw-stack" @submit.prevent="save"><p v-if="error" class="lw-notice warning" role="alert">{{error}}</p><label class="lw-label">成果名称<input v-model="form.title" class="lw-field" required/></label><label class="lw-label">成果正文（Markdown）<textarea v-model="form.content" class="lw-field" rows="10" required/></label><label class="lw-label">验证了什么、有什么未覆盖<textarea v-model="form.verification" class="lw-field" rows="3" required/></label><label class="lw-label">验证环境或来源<input v-model="form.environment" class="lw-field" required/></label><p class="lw-small lw-sub">保存后形成固定版本的成果和待审证据。阅读与接受证据后，才可完成事项。</p></form><template #footer><button class="lw-btn" @click="emit('close')">取消</button><button class="lw-btn primary" form="manual-result" :disabled="busy">保存成果</button></template></LifeWeaveModal></template>

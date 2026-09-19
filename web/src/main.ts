import { createApp } from 'vue'
import App from './App.vue'
import router from './app/router'
import './styles/tokens.css'
import './styles/base.css'
import './features/lifeweave/lifeweave.css'
const app=createApp(App).use(router)
router.isReady().then(()=>app.mount('#app'))

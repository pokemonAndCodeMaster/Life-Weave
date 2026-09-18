import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 }
  },
  routes: [
    { path: '/', redirect: '/gongzuo/personal/home' },
    { path: '/gongzuo', redirect: '/gongzuo/personal/home' },
    { path: '/gongzuo/:workspace(personal|team)/home', name: 'home', component: () => import('@/features/gongzuo/pages/HomePage.vue'), meta: { gongzuo: true, title: '我的工作' } },
    { path: '/gongzuo/:workspace(personal|team)/items', name: 'items', component: () => import('@/features/gongzuo/pages/ItemsPage.vue'), meta: { gongzuo: true, title: '工作事项' } },
    { path: '/gongzuo/:workspace(personal|team)/ideas', name: 'ideas', component: () => import('@/features/gongzuo/pages/IdeasPage.vue'), meta: { gongzuo: true, title: '灵感与讨论' } },
    { path: '/gongzuo/:workspace(personal|team)/knowledge', name: 'knowledge', component: () => import('@/features/gongzuo/pages/KnowledgePage.vue'), meta: { gongzuo: true, title: '知识' } },
    { path: '/gongzuo/:workspace(personal|team)/meeting', name: 'meeting', component: () => import('@/features/gongzuo/pages/MeetingPage.vue'), meta: { gongzuo: true, title: '组会 / 回顾' } },
    { path: '/gongzuo/:workspace(personal|team)/maintenance', name: 'maintenance', component: () => import('@/features/gongzuo/pages/MaintenancePage.vue'), meta: { gongzuo: true, title: '维护中心' } },
    { path: '/gongzuo/:workspace(personal|team)/items/:itemId/:tab(overview|context|outputs|activity|retro)?', name: 'item-detail', component: () => import('@/features/gongzuo/pages/ItemDetailPage.vue'), meta: { gongzuo: true, title: '事项' } },
    { path: '/gongzuo/:workspace(personal|team)/plan', name: 'plan', component: () => import('@/features/gongzuo/pages/PlanPage.vue') },
    { path: '/gongzuo/:workspace(personal|team)/settings', name: 'settings', component: () => import('@/features/gongzuo/pages/SettingsPage.vue') },
    { path: '/gongzuo/:workspace(personal|team)/connections', name: 'connections', component: () => import('@/features/gongzuo/pages/ConnectionsPage.vue') },
    { path: '/gongzuo/:workspace(personal|team)/runs', name: 'runs', component: () => import('@/features/gongzuo/pages/RunsPage.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/gongzuo/personal/home' },
  ],
})
export default router

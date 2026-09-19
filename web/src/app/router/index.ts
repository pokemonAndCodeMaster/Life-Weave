import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 }
  },
  routes: [
    { path: '/gongzuo/:legacyPath(.*)*', redirect: (to) => ({ path: to.path.replace(/^\/gongzuo(?=\/|$)/, '/lifeweave'), query: to.query, hash: to.hash }) },
    { path: '/', redirect: '/lifeweave/personal/home' },
    { path: '/lifeweave', redirect: '/lifeweave/personal/home' },
    { path: '/lifeweave/:workspace(personal|team)/home', name: 'home', component: () => import('@/features/lifeweave/pages/HomePage.vue'), meta: { lifeweave: true, title: '我的日常' } },
    { path: '/lifeweave/:workspace(personal|team)/items', name: 'items', component: () => import('@/features/lifeweave/pages/ItemsPage.vue'), meta: { lifeweave: true, title: '工作事项' } },
    { path: '/lifeweave/:workspace(personal|team)/ideas', name: 'ideas', component: () => import('@/features/lifeweave/pages/IdeasPage.vue'), meta: { lifeweave: true, title: '灵感与讨论' } },
    { path: '/lifeweave/:workspace(personal|team)/knowledge', name: 'knowledge', component: () => import('@/features/lifeweave/pages/KnowledgePage.vue'), meta: { lifeweave: true, title: '知识' } },
    { path: '/lifeweave/:workspace(personal|team)/meeting', name: 'meeting', component: () => import('@/features/lifeweave/pages/MeetingPage.vue'), meta: { lifeweave: true, title: '组会 / 回顾' } },
    { path: '/lifeweave/:workspace(personal|team)/maintenance', name: 'maintenance', component: () => import('@/features/lifeweave/pages/MaintenancePage.vue'), meta: { lifeweave: true, title: '维护中心' } },
    { path: '/lifeweave/:workspace(personal|team)/items/:itemId/:tab(overview|context|outputs|activity|retro)?', name: 'item-detail', component: () => import('@/features/lifeweave/pages/ItemDetailPage.vue'), meta: { lifeweave: true, title: '事项' } },
    { path: '/lifeweave/:workspace(personal|team)/plan', name: 'plan', component: () => import('@/features/lifeweave/pages/PlanPage.vue') },
    { path: '/lifeweave/:workspace(personal|team)/settings', name: 'settings', component: () => import('@/features/lifeweave/pages/SettingsPage.vue') },
    { path: '/lifeweave/:workspace(personal|team)/connections', name: 'connections', component: () => import('@/features/lifeweave/pages/ConnectionsPage.vue') },
    { path: '/lifeweave/:workspace(personal|team)/runs', name: 'runs', component: () => import('@/features/lifeweave/pages/RunsPage.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/lifeweave/personal/home' },
  ],
})
export default router

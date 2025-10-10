import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

// 定义路由配置
const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue') // 懒加载
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/AboutView.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue')
  },
  {
    path: '/paper-management',
    name: 'PaperManagement',
    component: () => import('@/views/PaperManagementView.vue')
  },
  {
    path: '/journal-management',
    name: 'JournalManagement',
    component: () => import('@/views/JournalManagementView.vue')
  },
  {
    path: '/preliminary-review',
    name: 'PreliminaryReview',
    component: () => import('@/views/PreliminaryReviewView.vue')
  },
  {
    path: '/create-journal',
    name: 'CreateJournal',
    component: () => import('@/views/CreateJournalView.vue')
  },
  // 可以继续添加更多路由...
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router

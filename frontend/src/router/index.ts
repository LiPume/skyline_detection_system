import { createRouter, createWebHistory } from 'vue-router'
import Detection     from '@/views/Detection.vue'
import History       from '@/views/History.vue'
import HistoryDetail from '@/views/HistoryDetail.vue'
import Performance   from '@/views/Performance.vue'
import Dashboard     from '@/views/Dashboard.vue'

const routes = [
  { path: '/',             component: Dashboard,   meta: { title: '系统总览' } },
  { path: '/detection',    component: Detection,     meta: { title: '智能检测舱' } },
  { path: '/history',      component: History, name: 'history',      meta: { title: '历史记录库' } },
  { path: '/history/:id',  component: HistoryDetail, name: 'history-detail', meta: { title: '数据详情' } },
  { path: '/performance',  component: Performance,    meta: { title: '性能分析' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL ?? '/'),
  routes,
})

export default router

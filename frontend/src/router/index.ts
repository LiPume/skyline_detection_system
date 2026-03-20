import { createRouter, createWebHistory } from 'vue-router'
import Detection     from '@/views/Detection.vue'
import History       from '@/views/History.vue'
import HistoryDetail from '@/views/HistoryDetail.vue'
import Performance   from '@/views/Performance.vue'

const routes = [
  { path: '/',             redirect: '/detection' },
  { path: '/detection',    component: Detection,     meta: { title: '智能检测舱' } },
  { path: '/history',      component: History,       meta: { title: '历史记录库' } },
  { path: '/history/:id',  component: HistoryDetail, name: 'history-detail', meta: { title: '数据详情' } },
  { path: '/performance',  component: Performance,    meta: { title: '性能分析' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL ?? '/'),
  routes,
})

export default router

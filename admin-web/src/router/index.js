/**
 * 管理端路由（Vue Router 4）
 * - 未登录访问业务页 → 重定向 /login
 * - 已登录访问 /login → 重定向 /
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/login/index.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: () => import('../layout/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../views/dashboard/index.vue'),
        meta: { title: '数据看板', icon: 'DataAnalysis' }
      },
      {
        path: 'departments',
        name: 'departments',
        component: () => import('../views/department/index.vue'),
        meta: { title: '院系管理', icon: 'OfficeBuilding' }
      },
      {
        path: 'classes',
        name: 'classes',
        component: () => import('../views/class/index.vue'),
        meta: { title: '班级管理', icon: 'User' }
      },
      {
        path: 'students',
        name: 'students',
        component: () => import('../views/student/index.vue'),
        meta: { title: '学生管理', icon: 'UserFilled' }
      },
      {
        path: 'teachers',
        name: 'teachers',
        component: () => import('../views/teacher/index.vue'),
        meta: { title: '教师管理', icon: 'Avatar' }
      },
      {
        path: 'courses',
        name: 'courses',
        component: () => import('../views/course/index.vue'),
        meta: { title: '课程管理', icon: 'Reading' }
      },
      {
        path: 'terms',
        name: 'terms',
        component: () => import('../views/term/index.vue'),
        meta: { title: '学期管理', icon: 'Calendar' }
      },
      {
        path: 'offerings',
        name: 'offerings',
        component: () => import('../views/offering/index.vue'),
        meta: { title: '教学班管理', icon: 'Collection' }
      },
      {
        path: 'schedules',
        name: 'schedules',
        component: () => import('../views/schedule/index.vue'),
        meta: { title: '排课管理', icon: 'Grid' }
      },
      {
        path: 'scores',
        name: 'scores',
        component: () => import('../views/score/index.vue'),
        meta: { title: '成绩管理', icon: 'DataLine' }
      },
      {
        path: 'leaves',
        name: 'leaves',
        component: () => import('../views/leave/index.vue'),
        meta: { title: '请假管理', icon: 'Document' }
      },
      {
        path: 'announcements',
        name: 'announcements',
        component: () => import('../views/announcement/index.vue'),
        meta: { title: '公告管理', icon: 'Bell' }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  // SPA 由 Django 挂载在 /admin/ 前缀下（config/urls.py AdminWebView），base 必须一致
  history: createWebHistory('/admin/'),
  routes
})

// 路由守卫：登录态校验（4011 由 request 拦截器兜底）
router.beforeEach((to) => {
  const token = localStorage.getItem('admin_access')
  if (to.path !== '/login' && !token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && token) {
    return { path: '/' }
  }
  document.title = to.meta.title ? `${to.meta.title} · 智慧校园` : '智慧校园 · 管理后台'
  return true
})

export default router

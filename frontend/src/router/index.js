import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginPage from '../views/auth/LoginPage.vue'
import ForbiddenPage from '../views/system/ForbiddenPage.vue'
import AdminDashboard from '../views/admin/AdminDashboard.vue'
import AdminTasks from '../views/admin/AdminTasks.vue'
import AdminTaskForm from '../views/admin/AdminTaskForm.vue'
import AdminTaskDetail from '../views/admin/AdminTaskDetail.vue'
import AdminTemplates from '../views/admin/AdminTemplates.vue'
import AdminNotifications from '../views/admin/AdminNotifications.vue'
import AdminMailEvents from '../views/admin/AdminMailEvents.vue'
import AdminMailEventDetail from '../views/admin/AdminMailEventDetail.vue'
import AdminDelayRequests from '../views/admin/AdminDelayRequests.vue'
import AdminUsers from '../views/admin/AdminUsers.vue'
import AdminImportExport from '../views/admin/AdminImportExport.vue'
import AdminAuditLogs from '../views/admin/AdminAuditLogs.vue'
import MemberTasks from '../views/member/MemberTasks.vue'
import MemberTaskDetail from '../views/member/MemberTaskDetail.vue'
import MemberNotifications from '../views/member/MemberNotifications.vue'
import NotificationDetailPage from '../views/shared/NotificationDetailPage.vue'

const routes = [
  { path: '/', redirect: '/auth/login' },
  { path: '/auth/login', component: LoginPage, meta: { public: true } },
  { path: '/403', component: ForbiddenPage, meta: { public: true } },
  { path: '/admin/dashboard', component: AdminDashboard, meta: { role: 'admin' } },
  { path: '/admin/tasks', component: AdminTasks, meta: { role: 'admin' } },
  { path: '/admin/tasks/new', component: AdminTaskForm, meta: { role: 'admin' } },
  { path: '/admin/tasks/:id', component: AdminTaskDetail, meta: { role: 'admin' } },
  { path: '/admin/tasks/:id/edit', component: AdminTaskForm, meta: { role: 'admin' } },
  { path: '/admin/templates', component: AdminTemplates, meta: { role: 'admin' } },
  { path: '/admin/notifications', component: AdminNotifications, meta: { role: 'admin' } },
  { path: '/admin/notifications/:id', component: NotificationDetailPage, meta: { role: 'admin' } },
  { path: '/admin/mail-events', component: AdminMailEvents, meta: { role: 'admin' } },
  { path: '/admin/mail-events/:id', component: AdminMailEventDetail, meta: { role: 'admin' } },
  { path: '/admin/delay-requests', component: AdminDelayRequests, meta: { role: 'admin' } },
  { path: '/admin/users', component: AdminUsers, meta: { role: 'admin' } },
  { path: '/admin/import-export', component: AdminImportExport, meta: { role: 'admin' } },
  { path: '/admin/audit-logs', component: AdminAuditLogs, meta: { role: 'admin' } },
  { path: '/member/tasks', component: MemberTasks, meta: { role: 'member' } },
  { path: '/member/tasks/:id', component: MemberTaskDetail, meta: { role: 'member' } },
  { path: '/member/notifications', component: MemberNotifications, meta: { role: 'member' } },
  { path: '/member/notifications/:id', component: NotificationDetailPage, meta: { role: 'member' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  auth.hydrate()
  if (to.meta.public) {
    return true
  }
  if (!auth.accessToken) {
    return '/auth/login'
  }
  if (!auth.profile) {
    try {
      await auth.fetchMe()
    } catch (error) {
      auth.logout()
      return '/auth/login'
    }
  }
  if (to.meta.role && auth.profile?.role !== to.meta.role) {
    return '/403'
  }
  return true
})

export default router

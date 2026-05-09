<template>
  <div v-if="isPublicPage" class="auth-layout">
    <router-view />
  </div>
  <div v-else class="shell">
    <aside class="sidebar" v-if="auth.isLoggedIn">
      <div class="brand">{{ labels.brand }}</div>
      <nav>
        <router-link v-for="link in auth.isAdmin ? adminLinks : []" :key="link.to" :to="link.to">
          <span class="nav-icon">{{ link.icon }}</span>
          <span>{{ link.label }}</span>
        </router-link>
        <router-link v-if="auth.isMember" to="/member/tasks">
          <span class="nav-icon">□</span>
          <span>{{ labels.memberTasks }}</span>
        </router-link>
        <router-link v-if="auth.isMember" to="/member/notifications">
          <span class="nav-icon">●</span>
          <span>{{ labels.memberNotifications }}</span>
        </router-link>
      </nav>
    </aside>
    <main class="content" :class="{ 'content-full': !auth.isLoggedIn }">
      <div v-if="auth.isLoggedIn" class="top-note">
        <span>{{ labels.currentUser }}{{ auth.profile?.name || auth.profile?.username }}</span>
        <span class="top-note-role">{{ auth.profile?.role_text || fallbackRoleText }}</span>
        <button class="button secondary small" :disabled="loading.isBusy" @click="handleLogout">{{ labels.logout }}</button>
      </div>
      <router-view />
    </main>
    <div v-if="loading.isBusy" class="global-loading-mask">
      <div class="global-loading-card">
        <div class="global-loading-spinner" />
        <strong>加载中</strong>
        <span>正在处理请求，请稍候。</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useLoadingStore } from './stores/loading'

const labels = {
  brand: '管理后台系统',
  dashboard: '看板',
  tasks: '任务管理',
  templates: '模板管理',
  notifications: '通知中心',
  mailEvents: '计划任务',
  users: '用户管理',
  importExport: '数据导入',
  auditLogs: '操作日志',
  memberTasks: '我的任务',
  memberNotifications: '我的通知',
  currentUser: '当前用户：',
  systemAdmin: '系统管理员',
  admin: '管理员',
  member: '成员',
  logout: '退出登录',
}

const auth = useAuthStore()
const loading = useLoadingStore()
const route = useRoute()
const router = useRouter()
const isPublicPage = computed(() => Boolean(route.meta.public))
const adminLinks = computed(() => {
  const links = [
    { to: '/admin/dashboard', label: labels.dashboard, icon: '▦' },
    { to: '/admin/tasks', label: labels.tasks, icon: '□' },
  ]
  if (!auth.isSystemAdmin) {
    return links
  }
  return [
    ...links,
    { to: '/admin/templates', label: labels.templates, icon: '≡' },
    { to: '/admin/notifications', label: labels.notifications, icon: '●' },
    { to: '/admin/mail-events', label: labels.mailEvents, icon: '◷' },
    { to: '/admin/users', label: labels.users, icon: '♙' },
    { to: '/admin/import-export', label: labels.importExport, icon: '⇄' },
    { to: '/admin/system-logs', label: labels.auditLogs, icon: '◴' },
  ]
})
const fallbackRoleText = computed(() => {
  if (auth.isSystemAdmin) return labels.systemAdmin
  return auth.isAdmin ? labels.admin : labels.member
})

function handleLogout() {
  auth.logout()
  loading.reset()
  router.push('/auth/login')
}
</script>

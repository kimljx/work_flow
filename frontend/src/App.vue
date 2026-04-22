<template>
  <div class="shell">
    <aside class="sidebar" v-if="auth.isLoggedIn">
      <div class="brand">{{ labels.brand }}</div>
      <nav>
        <router-link v-if="auth.isAdmin" to="/admin/dashboard">{{ labels.dashboard }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/tasks">{{ labels.tasks }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/templates">{{ labels.templates }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/notifications">{{ labels.notifications }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/mail-events">{{ labels.mailEvents }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/delay-requests">{{ labels.delayRequests }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/users">{{ labels.users }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/import-export">{{ labels.importExport }}</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/audit-logs">{{ labels.auditLogs }}</router-link>
        <router-link v-if="auth.isMember" to="/member/tasks">{{ labels.memberTasks }}</router-link>
        <router-link v-if="auth.isMember" to="/member/notifications">{{ labels.memberNotifications }}</router-link>
      </nav>
    </aside>
    <main class="content">
      <div v-if="auth.isLoggedIn" class="top-note">
        <span>{{ labels.currentUser }}{{ auth.profile?.name || auth.profile?.username }}</span>
        <span class="top-note-role">{{ auth.profile?.role_text || (auth.isAdmin ? labels.admin : labels.member) }}</span>
        <button class="button secondary small" @click="handleLogout">{{ labels.logout }}</button>
      </div>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const labels = {
  brand: '部门任务协同系统',
  dashboard: '看板',
  tasks: '任务',
  templates: '模板',
  notifications: '通知中心',
  mailEvents: '扫描邮件',
  delayRequests: '延期审批',
  users: '用户管理',
  importExport: '导入导出',
  auditLogs: '审计日志',
  memberTasks: '我的任务',
  memberNotifications: '我的通知',
  currentUser: '当前登录：',
  admin: '管理员',
  member: '成员',
  logout: '退出登录',
}

const auth = useAuthStore()
const router = useRouter()

function handleLogout() {
  auth.logout()
  router.push('/auth/login')
}
</script>

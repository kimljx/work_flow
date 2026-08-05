<template>
  <div v-if="isPublicPage" class="auth-layout">
    <router-view />
  </div>
  <div v-else class="shell">
    <header v-if="auth.isLoggedIn" class="app-topbar">
      <div class="topbar-brand">{{ labels.brand }}</div>
      <nav class="topbar-main-nav">
        <router-link
          v-for="link in primaryLinks"
          :key="link.key"
          :to="link.to"
          :class="{ active: isPrimaryActive(link.key) }"
        >
          <img :src="link.icon" alt="" />
          <span>{{ link.label }}</span>
        </router-link>
      </nav>
      <div class="topbar-spacer" />
      <div class="topbar-user">{{ auth.profile?.name || auth.profile?.username }}</div>
      <div class="settings-menu" @click.stop>
        <button class="settings-trigger" type="button" :disabled="loading.isBusy" @click="settingsOpen = !settingsOpen">
          <img :src="settingsIcon" alt="设置" />
        </button>
        <div v-if="settingsOpen" class="settings-popover">
          <button type="button" @click="openChangePassword">
            <img :src="settingsIcon" alt="" />
            <span>修改密码</span>
          </button>
          <button v-for="link in settingsLinks" :key="link.key" type="button" @click="openSettingsModal(link)">
            <img :src="link.icon" alt="" />
            <span>{{ link.label }}</span>
          </button>
          <button type="button" class="settings-logout" :disabled="loading.isBusy" @click="handleLogout">
            {{ labels.logout }}
          </button>
        </div>
      </div>
    </header>
    <main class="content" :class="{ 'content-full': !auth.isLoggedIn }">
      <router-view />
    </main>
    <div v-if="settingsModal" class="modal-mask">
      <div class="modal-card settings-modal-card">
        <div class="settings-modal-head">
          <div>
            <h2>{{ settingsModal.label }}</h2>
          </div>
          <button type="button" class="button secondary small" @click="closeSettingsModal">关闭</button>
        </div>
        <div :key="settingsModal.key" class="settings-modal-body">
          <component :is="settingsModal.component" />
        </div>
      </div>
    </div>
    <div v-if="changePasswordOpen" class="modal-mask">
      <div class="modal-card password-modal-card">
        <div class="modal-section-head">
          <div>
            <h2>修改密码</h2>
          </div>
        </div>
        <form class="password-form" @submit.prevent="submitChangePassword">
          <div>
            <label>当前密码</label>
            <input v-model="changePasswordForm.current" type="password" autocomplete="current-password" />
          </div>
          <div>
            <label>新密码</label>
            <input v-model="changePasswordForm.next" type="password" autocomplete="new-password" />
          </div>
          <div>
            <label>确认新密码</label>
            <input v-model="changePasswordForm.confirm" type="password" autocomplete="new-password" />
          </div>
          <p v-if="changePasswordMessage" :class="changePasswordType === 'success' ? 'success-text' : 'error-text'">
            {{ changePasswordMessage }}
          </p>
          <div class="toolbar modal-actions">
            <button class="button secondary" type="button" @click="closeChangePassword">取消</button>
            <button type="submit" :disabled="loading.isBusy">保存</button>
          </div>
        </form>
      </div>
    </div>
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
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from './api/http'
import { useAuthStore } from './stores/auth'
import { useLoadingStore } from './stores/loading'
import { md5Hex, sha256Hex } from './utils/md5'
import bellIcon from './assets/icons/bell.svg'
import calendarClockIcon from './assets/icons/calendar-clock.svg'
import chartGanttIcon from './assets/icons/chart-gantt.svg'
import clipboardListIcon from './assets/icons/clipboard-list.svg'
import fileTextIcon from './assets/icons/file-text.svg'
import scrollTextIcon from './assets/icons/scroll-text.svg'
import settingsIcon from './assets/icons/settings.svg'
import uploadIcon from './assets/icons/upload.svg'
import usersIcon from './assets/icons/users.svg'
import AdminAuditLogs from './views/admin/AdminAuditLogs.vue'
import AdminImportExport from './views/admin/AdminImportExport.vue'
import AdminMailEvents from './views/admin/AdminMailEvents.vue'
import AdminNotifications from './views/admin/AdminNotifications.vue'
import AdminTemplates from './views/admin/AdminTemplates.vue'
import AdminUsers from './views/admin/AdminUsers.vue'
import { APP_NAME } from './constants/app'

const labels = {
  brand: APP_NAME,
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
const settingsOpen = ref(false)
const settingsModal = ref(null)
const changePasswordOpen = ref(false)
const changePasswordForm = reactive({ current: '', next: '', confirm: '' })
const changePasswordMessage = ref('')
const changePasswordType = ref('error')
let modalObserver = null
const isPublicPage = computed(() => Boolean(route.meta.public))
const primaryLinks = computed(() => {
  if (auth.isAdmin) {
    return [
      { key: 'gantt', to: { path: '/admin/dashboard', query: { view: 'gantt' } }, label: '甘特图', icon: chartGanttIcon },
      { key: 'tasks', to: '/admin/tasks', label: labels.tasks, icon: clipboardListIcon },
    ]
  }
  if (auth.isMember) {
    return [
      { key: 'memberTasks', to: '/member/tasks', label: labels.memberTasks, icon: clipboardListIcon },
      { key: 'memberNotifications', to: '/member/notifications', label: labels.memberNotifications, icon: bellIcon },
    ]
  }
  return []
})
const settingsLinks = computed(() => {
  if (!auth.isSystemAdmin) return []
  return [
    { key: 'templates', label: labels.templates, icon: fileTextIcon, component: AdminTemplates },
    { key: 'notifications', label: labels.notifications, icon: bellIcon, component: AdminNotifications },
    { key: 'mail-events', label: labels.mailEvents, icon: calendarClockIcon, component: AdminMailEvents },
    { key: 'users', label: labels.users, icon: usersIcon, component: AdminUsers },
    { key: 'import-export', label: labels.importExport, icon: uploadIcon, component: AdminImportExport },
    { key: 'audit-logs', label: labels.auditLogs, icon: scrollTextIcon, component: AdminAuditLogs },
  ]
})

function isPrimaryActive(key) {
  if (key === 'gantt') {
    return route.path === '/admin/dashboard'
  }
  if (key === 'tasks') return route.path.startsWith('/admin/tasks')
  if (key === 'memberTasks') return route.path.startsWith('/member/tasks')
  if (key === 'memberNotifications') return route.path.startsWith('/member/notifications')
  return false
}

function handleLogout() {
  settingsOpen.value = false
  settingsModal.value = null
  auth.logout()
  loading.reset()
  router.push('/auth/login')
}

function openSettingsModal(link) {
  settingsOpen.value = false
  settingsModal.value = link
}

function openChangePassword() {
  settingsOpen.value = false
  changePasswordOpen.value = true
  changePasswordMessage.value = ''
  changePasswordType.value = 'error'
  Object.assign(changePasswordForm, { current: '', next: '', confirm: '' })
}

function closeChangePassword() {
  changePasswordOpen.value = false
}

async function submitChangePassword() {
  if (!changePasswordForm.current || !changePasswordForm.next) {
    changePasswordType.value = 'error'
    changePasswordMessage.value = '请输入当前密码和新密码'
    return
  }
  if (changePasswordForm.next !== changePasswordForm.confirm) {
    changePasswordType.value = 'error'
    changePasswordMessage.value = '两次输入的新密码不一致'
    return
  }
  try {
    const { data } = await http.post('/auth/change-password', {
      current_password: md5Hex(changePasswordForm.current),
      current_password_legacy_sha256: await sha256Hex(changePasswordForm.current),
      new_password: md5Hex(changePasswordForm.next),
    })
    changePasswordType.value = 'success'
    changePasswordMessage.value = data.message || '密码已修改'
    Object.assign(changePasswordForm, { current: '', next: '', confirm: '' })
  } catch (error) {
    changePasswordType.value = 'error'
    changePasswordMessage.value = error.response?.data?.detail || '密码修改失败'
  }
}

function closeSettingsModal() {
  settingsModal.value = null
}

function closeSettingsPopover(event) {
  if (event.target?.closest?.('.settings-menu')) return
  settingsOpen.value = false
}

onMounted(() => {
  document.addEventListener('click', closeSettingsPopover)
  const syncModalLock = () => {
    document.body.classList.toggle('modal-open', Boolean(document.querySelector('.modal-mask')))
  }
  modalObserver = new MutationObserver(syncModalLock)
  modalObserver.observe(document.body, { childList: true, subtree: true })
  syncModalLock()
})

onUnmounted(() => {
  document.removeEventListener('click', closeSettingsPopover)
  if (modalObserver) modalObserver.disconnect()
  document.body.classList.remove('modal-open')
})

watch(() => route.fullPath, () => {
  settingsOpen.value = false
})
</script>

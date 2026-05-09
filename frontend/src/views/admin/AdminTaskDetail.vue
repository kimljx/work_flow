<template>
  <section v-if="task" class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">Task Detail</div>
        <h1 class="workspace-title">{{ task.title }}</h1>
        <p class="workspace-subtitle">{{ task.content || '暂无任务内容' }}</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="backTarget">返回列表</router-link>
        <router-link class="button secondary" :to="`/admin/tasks/${task.id}/edit`">编辑</router-link>
        <button class="button secondary" :disabled="actionLoading" @click="remindTask">发送提醒</button>
        <button class="button danger" :disabled="actionLoading" @click="removeTask">删除任务</button>
      </div>
    </div>

    <div class="detail-grid">
      <div class="panel">
        <div class="section-head">
          <div>
            <h2>基本信息</h2>
          </div>
        </div>
        <div class="task-detail-meta-grid">
          <div class="info-cell">
            <span class="info-label">状态</span>
            <strong><span :class="statusMeta.tone">{{ statusMeta.text }}</span></strong>
          </div>
          <div class="info-cell">
            <span class="info-label">优先级</span>
            <strong><span :class="priorityMeta.tone">{{ priorityMeta.label }}</span></strong>
          </div>
          <div class="info-cell">
            <span class="info-label">负责人</span>
            <strong>{{ responsibleText }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">开始时间</span>
            <strong>{{ formatDateTime(task.start_at) }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">截止时间</span>
            <strong>{{ formatDateTime(task.end_at) }}</strong>
            <div v-if="delayStatus.text" :class="delayStatus.className">{{ delayStatus.text }}</div>
          </div>
          <div v-if="task.completed_at" class="info-cell">
            <span class="info-label">完成时间</span>
            <strong>{{ formatDateTime(task.completed_at) }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">提醒设置</span>
            <strong>{{ dueRemindText }}</strong>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="section-head">
          <div>
            <h2>状态更新</h2>
            <p>保留管理员最常用的状态修改入口。</p>
          </div>
        </div>
        <div class="task-detail-status-grid">
          <select v-model="statusForm.main_status" :disabled="actionLoading">
            <option value="not_started">未开始</option>
            <option value="in_progress">进行中</option>
            <option value="done">已完成</option>
            <option value="canceled">已取消</option>
          </select>
          <input v-model="statusForm.remark" :disabled="actionLoading" placeholder="可选说明" />
          <button :disabled="actionLoading" @click="changeStatus">更新状态</button>
        </div>
        <div class="task-notice-grid task-status-notice-grid">
          <div class="info-cell">
            <span class="info-label">邮件</span>
            <strong>{{ task.latest_notifications?.email?.summary || '未发送' }}</strong>
            <div class="subtle-text">{{ task.latest_notifications?.email?.read_status_text || '' }}</div>
          </div>
          <div class="info-cell">
            <span class="info-label">QAX</span>
            <strong>{{ task.latest_notifications?.qax?.summary || '未发送' }}</strong>
            <div class="subtle-text">{{ task.latest_notifications?.qax?.read_status_text || '' }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>子任务</h2>
        </div>
      </div>
      <div v-if="notificationRows.length === 0" class="muted-block">当前没有子任务。</div>
      <div v-else class="task-simple-list">
        <div v-for="item in notificationRows" :key="item.row_key" class="task-simple-row task-simple-row-detail">
          <div class="task-simple-main">
            <strong>{{ item.title }}</strong>
            <div class="subtle-text">{{ item.assignee_name || '-' }} / {{ item.status_text }}</div>
          </div>
          <div class="task-channel-stack">
            <span>邮件：{{ item.latest_notifications?.email?.summary || '未发送' }}</span>
            <span>即时消息：{{ item.latest_notifications?.qax?.summary || '未发送' }}</span>
          </div>
          <button v-if="item.id && item.status !== 'done'" class="button secondary small" :disabled="actionLoading" @click="remindSubtask(item)">提醒</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatDateTime } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const task = ref(null)
const actionLoading = ref(false)
const statusForm = reactive({
  main_status: 'not_started',
  remark: '',
})

const backTarget = route.query.from || '/admin/tasks'
const statusMeta = computed(() => resolveTaskStatusTone(task.value || null))
const priorityMeta = computed(() => resolvePriorityMeta(task.value?.priority))
const delayStatus = computed(() => resolveDelayStatus(task.value))
const responsibleText = computed(() => {
  const names = (task.value?.members || []).map((item) => item.name).filter(Boolean)
  return names.length > 0 ? names.join(', ') : '-'
})
const dueRemindText = computed(() => {
  if (!task.value || Number(task.value.due_remind_days || 0) <= 0) {
    return '未启用'
  }
  return `截止前 ${task.value.due_remind_days} 天提醒`
})

function resolveDelayStatus(item) {
  if (!item || ['done', 'canceled'].includes(item.main_status)) {
    return { text: '', className: '' }
  }
  const delayDays = Number(item.delay_days || 0)
  if (delayDays > 0) {
    return { text: `已延期${delayDays}天`, className: 'error-text task-delay-text' }
  }
  const endDate = new Date(item.end_at)
  if (Number.isNaN(endDate.getTime())) {
    return { text: '', className: '' }
  }
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const endDay = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate()).getTime()
  const daysToDue = Math.ceil((endDay - startOfToday) / 86400000)
  if (daysToDue < 0) {
    return { text: `已延期${Math.abs(daysToDue)}天`, className: 'error-text task-delay-text' }
  }
  if (daysToDue >= 0 && daysToDue <= 3) {
    return { text: '即将延期', className: 'warning-text task-delay-text' }
  }
  return { text: '', className: '' }
}
const notificationRows = computed(() => {
  if (!task.value) return []
  if ((task.value.subtasks || []).length > 0) {
    return task.value.subtasks.map((item) => ({
      ...item,
      row_key: `subtask-${item.id}`,
    }))
  }
  return (task.value.members || []).map((item) => ({
    id: null,
    row_key: `member-${item.user_id}`,
    title: item.name || `成员 #${item.user_id}`,
    assignee_name: item.email || '-',
    status: '',
    status_text: item.member_role_text || item.display_role_text || '参与人',
    latest_notifications: item.latest_notifications || {},
  }))
})

async function loadTask() {
  const { data } = await http.get(`/tasks/${route.params.id}`)
  task.value = data
  statusForm.main_status = data.main_status
}

async function remindTask() {
  if (!window.confirm('确认发送一次任务提醒吗？')) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/remind`)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function remindSubtask(item) {
  if (!window.confirm(`确认提醒子任务“${item.title}”吗？`)) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/subtasks/${item.id}/remind`)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function changeStatus() {
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/status`, statusForm)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function removeTask() {
  if (!window.confirm('确认删除这项任务吗？')) return
  actionLoading.value = true
  try {
    await http.delete(`/tasks/${route.params.id}`)
    router.push(backTarget)
  } finally {
    actionLoading.value = false
  }
}

onMounted(loadTask)
</script>

<template>
  <section v-if="task" class="task-detail-dialog">
    <button v-if="props.taskId" type="button" class="task-detail-close" @click="$emit('cancel')">×</button>
    <div v-if="feedback.message" class="task-detail-feedback">
      <strong>{{ feedback.title }}</strong>
      <span :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</span>
    </div>
    <div class="task-detail-floating-stack">
      <span :class="['task-detail-status-floating', statusMeta.tone]">{{ statusMeta.text }}</span>
      <span v-if="delayStatus.text" class="task-detail-delay-floating" :class="delayStatus.className">
        {{ delayStatus.text }}
      </span>
    </div>

    <div class="task-detail-head">
      <div class="task-detail-title-line">
        <h1>{{ task.title }}</h1>
        <div class="task-detail-chip-line">
          <span :class="priorityMeta.tone">{{ priorityMeta.label }}</span>
        </div>
      </div>
      <div class="task-detail-date-line">
        <img class="task-detail-line-icon" :src="calendarIcon" alt="" />
        {{ formatDate(task.start_at) }}至{{ formatDate(task.end_at) }}
      </div>
      <div v-if="Number(task.due_remind_days || 0) > 0" class="task-detail-remind">
        到期前 {{ task.due_remind_days }} 天提醒
      </div>
    </div>

    <div class="task-detail-description">
      <span>任务描述</span>
      <div>{{ task.content || '暂无任务内容' }}</div>
    </div>

    <div class="task-detail-subtask-section">
      <div class="task-detail-subtask-head">
        <h2><img class="task-detail-section-icon" :src="subtaskIcon" alt="" /> 子任务</h2>
        <button class="button secondary small" :disabled="syncDisabled" @click="syncCollect">
          {{ syncButtonText }}
        </button>
      </div>

      <div v-if="participantRows.length === 0" class="muted-block">当前没有参与人。</div>
      <div v-else class="task-participant-grid">
        <article v-for="item in participantRows" :key="item.user_id" class="task-participant-card">
          <div class="task-participant-head">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ item.email || '-' }}</span>
            </div>
            <button
              v-if="!isParticipantDone(item)"
              class="button secondary small"
              :disabled="actionLoading"
              @click="remindParticipant(item)"
            >
              发送提醒
            </button>
            <span v-else class="task-participant-done">已完成</span>
          </div>

          <div v-if="item.subtasks.length > 0" class="task-participant-subtasks">
            <div v-for="subtask in item.subtasks" :key="subtask.id" class="task-participant-subtask">
              <span>{{ subtask.title }}</span>
            </div>
          </div>

          <div class="task-participant-status-row">
            <span>邮件:</span>
            <strong>
              <span>{{ channelStatusText(item, 'email') }}</span>
              <i v-if="channelCollecting(item.user_id, 'email')" class="inline-spinner" />
            </strong>
            <button
              v-if="shouldShowChannelReminder(item, 'email')"
              class="button secondary small"
              :disabled="actionLoading"
              @click="remindMemberChannel(item, 'email')"
            >
              邮件提醒
            </button>
          </div>
          <div class="task-participant-status-row">
            <span>即时消息:</span>
            <strong>
              <span>{{ channelStatusText(item, 'qax') }}</span>
              <i v-if="channelCollecting(item.user_id, 'qax')" class="inline-spinner" />
            </strong>
            <button
              v-if="shouldShowChannelReminder(item, 'qax')"
              class="button secondary small"
              :disabled="actionLoading"
              @click="remindMemberChannel(item, 'qax')"
            >
              即时消息提醒
            </button>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import http from '../../api/http'
import { resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatDate } from '../../utils/format'
import calendarIcon from '../../assets/icons/calendar-days.svg'
import subtaskIcon from '../../assets/icons/list-checks.svg'

const props = defineProps({
  taskId: {
    type: [Number, String],
    default: null,
  },
})
defineEmits(['cancel'])

const route = useRoute()
const task = ref(null)
const actionLoading = ref(false)
const collectState = ref({})
const feedback = ref({ title: '', message: '', type: 'success' })
let collectTimerId = null
let feedbackTimerId = null

const currentTaskId = computed(() => props.taskId || route.params.id)
const statusMeta = computed(() => resolveTaskStatusTone(task.value || null))
const priorityMeta = computed(() => resolvePriorityMeta(task.value?.priority))
const delayStatus = computed(() => resolveDelayStatus(task.value))
const collectParticipants = computed(() => collectState.value?.participants || [])
const syncDisabled = computed(() => {
  return actionLoading.value || Boolean(collectState.value?.running)
})
const syncButtonText = computed(() => (syncDisabled.value ? '收集中...' : '同步'))

const participantRows = computed(() => {
  if (!task.value) return []
  return (task.value.members || []).map((item) => ({
    user_id: item.user_id,
    name: item.name || `成员 #${item.user_id}`,
    email: item.email || '',
    latest_notifications: item.latest_notifications || {},
    subtasks: (task.value.subtasks || []).filter((subtask) => Number(subtask.assignee_id) === Number(item.user_id)),
  }))
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

function participantCollectText(userId) {
  if (!collectState.value?.running || collectState.value?.task_id !== Number(currentTaskId.value)) return ''
  const participant = collectParticipants.value.find((item) => Number(item.user_id) === Number(userId))
  return participant?.status_text || ''
}

function channelCollecting(userId, channel) {
  const text = participantCollectText(userId)
  if (!text) return false
  if (channel === 'email') {
    return collectState.value?.mode === 'mail' || text.includes('邮件')
  }
  return collectState.value?.mode === 'qax' || text.includes('QAX') || text.includes('查询') || text.includes('已读') || text.includes('未读')
}

function channelStatusText(item, channel) {
  const collectingText = participantCollectText(item.user_id)
  if (channelCollecting(item.user_id, channel)) {
    return collectingText || '收集中'
  }
  return item.latest_notifications?.[channel]?.summary || '未发送'
}

function shouldShowChannelReminder(item, channel) {
  if (channelCollecting(item.user_id, channel)) return false
  if (isParticipantDone(item)) return false
  const status = item.latest_notifications?.[channel] || {}
  return status.delivery_status === 'failed' || status.read_status !== 'read'
}

function isParticipantDone(item) {
  const activeSubtasks = item.subtasks.filter((subtask) => subtask.status !== 'canceled')
  if (activeSubtasks.length > 0) {
    return activeSubtasks.every((subtask) => subtask.status === 'done')
  }
  return item.latest_notifications?.email?.read_status === 'read'
}

async function loadTask() {
  if (!currentTaskId.value) return
  const { data } = await http.get(`/tasks/${currentTaskId.value}`, { skipGlobalLoading: Boolean(props.taskId) })
  task.value = data
}

async function loadCollectState() {
  const { data } = await http.get('/admin/collect/state', {
    params: { task_id: currentTaskId.value },
    skipGlobalLoading: true,
  })
  const wasRunning = collectState.value?.running
  collectState.value = data
  if (wasRunning && !data.running) {
    await loadTask()
  }
}

async function remindParticipant(item) {
  const unfinishedCount = item.subtasks.filter((subtask) => subtask.status !== 'done').length
  const focusText = unfinishedCount > 0 ? `${unfinishedCount} 项未完成子任务` : '主任务'
  if (!window.confirm(`确认提醒“${item.name}”处理${focusText}吗？`)) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${currentTaskId.value}/members/${item.user_id}/task-remind`, {}, { skipGlobalLoading: true })
    await loadTask()
    showFeedback('发送成功', '提醒已发送。')
  } finally {
    actionLoading.value = false
  }
}

async function remindMemberChannel(item, channel) {
  const channelName = channel === 'email' ? '邮件' : '即时消息'
  if (!window.confirm(`确认向“${item.name}”发送${channelName}提醒吗？`)) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${currentTaskId.value}/members/${item.user_id}/remind`, {}, {
      params: { channel },
      skipGlobalLoading: true,
    })
    await loadTask()
    showFeedback('发送成功', `${channelName}提醒已发送。`)
  } finally {
    actionLoading.value = false
  }
}

function showFeedback(title, message, type = 'success') {
  feedback.value = { title, message, type }
  if (feedbackTimerId) {
    window.clearTimeout(feedbackTimerId)
  }
  feedbackTimerId = window.setTimeout(() => {
    feedback.value = { title: '', message: '', type: 'success' }
    feedbackTimerId = null
  }, 3000)
}

async function syncCollect() {
  actionLoading.value = true
  try {
    const { data } = await http.post(`/tasks/${currentTaskId.value}/sync-collect`, {}, { skipGlobalLoading: true })
    collectState.value = data
    await loadCollectState()
  } finally {
    actionLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadTask(), loadCollectState()])
  collectTimerId = window.setInterval(loadCollectState, 2000)
})

onUnmounted(() => {
  if (collectTimerId) {
    window.clearInterval(collectTimerId)
  }
  if (feedbackTimerId) {
    window.clearTimeout(feedbackTimerId)
  }
})

watch(currentTaskId, async () => {
  await Promise.all([loadTask(), loadCollectState()])
})
</script>

<template>
  <section class="page dashboard-page">
    <header class="dashboard-page-head dashboard-page-head-compact">
      <h1>任务甘特图</h1>
    </header>

    <div v-if="feedback.message" class="panel dashboard-feedback">
      <strong>{{ feedback.title }}</strong>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <section class="gantt-summary-cards">
      <article class="gantt-summary-card clickable" @click="openTaskList('inProgress')">
        <div class="gantt-summary-top">
          <span>进行中任务</span>
          <img class="gantt-summary-icon icon-running" :src="iconRunning" alt="" aria-hidden="true" />
        </div>
        <strong>{{ summary.in_progress_total }}</strong>
      </article>
      <article v-if="notStartedTotal > 0" class="gantt-summary-card clickable" @click="openTaskList('notStarted')">
        <div class="gantt-summary-top">
          <span>未开始任务</span>
          <img class="gantt-summary-icon icon-pending" :src="iconPending" alt="" aria-hidden="true" />
        </div>
        <strong>{{ notStartedTotal }}</strong>
      </article>
      <article class="gantt-summary-card clickable" @click="openTaskList('dueToday')">
        <div class="gantt-summary-top">
          <span>今日到期</span>
          <img class="gantt-summary-icon icon-due" :src="iconDue" alt="" aria-hidden="true" />
        </div>
        <strong>{{ dueTodayTotal }}</strong>
        <small class="warning-text">{{ dueTodayUrgentText }}</small>
      </article>
      <article class="gantt-summary-card danger clickable" @click="openTaskList('delayed')">
        <div class="gantt-summary-top">
          <span>已延期</span>
          <img class="gantt-summary-icon icon-delayed" :src="iconDelayed" alt="" aria-hidden="true" />
        </div>
        <strong>{{ summary.delayed_total }}!</strong>
        <small>立即处理</small>
      </article>
      <article class="gantt-summary-card">
        <div class="gantt-summary-top">
          <span>待确认提醒</span>
          <img class="gantt-summary-icon icon-notice" :src="iconNotice" alt="" aria-hidden="true" />
        </div>
        <strong>{{ pendingNoticeTotal }}</strong>
        <div class="gantt-summary-links">
          <button class="gantt-summary-link" type="button" @click="openTaskList('pendingEmail')">邮件:{{ pendingEmailTotal }}</button>
          <button class="gantt-summary-link" type="button" @click="openTaskList('pendingQax')">即时消息:{{ pendingQaxTotal }}</button>
        </div>
      </article>
    </section>

      <section class="panel gantt-panel">
        <div class="gantt-toolbar">
          <div class="gantt-filters">
            <div class="multi-filter">
              <button class="button secondary small" @click="ownerFilterOpen = !ownerFilterOpen">成员：{{ selectedOwnerText }}</button>
              <div v-if="ownerFilterOpen" class="multi-filter-menu">
                <label class="multi-filter-all">
                  <span>全选</span>
                  <input type="checkbox" :checked="isAllOwnersSelected" @change="toggleAllOwners" />
                </label>
                <label v-for="name in ganttOwners" :key="name">
                  <span>{{ name }}</span>
                  <input v-model="ganttOwnersSelected" type="checkbox" :value="name" />
                </label>
              </div>
            </div>
            <div class="multi-filter">
              <button class="button secondary small" @click="statusFilterOpen = !statusFilterOpen">状态：{{ selectedStatusText }}</button>
              <div v-if="statusFilterOpen" class="multi-filter-menu">
                <label class="multi-filter-all">
                  <span>全选</span>
                  <input type="checkbox" :checked="isAllStatusesSelected" @change="toggleAllStatuses" />
                </label>
                <label v-for="item in statusOptions" :key="item.value">
                  <span>{{ item.label }}</span>
                  <input v-model="ganttStatusesSelected" type="checkbox" :value="item.value" />
                </label>
              </div>
            </div>
            <div class="multi-filter">
              <button class="button secondary small" @click="delayFilterOpen = !delayFilterOpen">延期：{{ selectedDelayText }}</button>
              <div v-if="delayFilterOpen" class="multi-filter-menu">
                <label class="multi-filter-all">
                  <span>全选</span>
                  <input type="checkbox" :checked="isAllDelaySelected" @change="toggleAllDelay" />
                </label>
                <label v-for="item in delayOptions" :key="item.value">
                  <span>{{ item.label }}</span>
                  <input v-model="ganttDelaySelected" type="checkbox" :value="item.value" />
                </label>
              </div>
            </div>
            <div class="gantt-scale-switch" aria-label="时间维度">
              <button :class="{ active: ganttScale === 'day' }" @click="ganttScale = 'day'">日</button>
              <button :class="{ active: ganttScale === 'week' }" @click="ganttScale = 'week'">周</button>
              <button :class="{ active: ganttScale === 'month' }" @click="ganttScale = 'month'">月</button>
            </div>
          </div>
          <div class="gantt-actions">
            <span class="gantt-legend running"><i></i>进行中</span>
            <span class="gantt-legend done"><i></i>已完成</span>
            <span class="gantt-legend delayed"><i></i>已延期</span>
            <button @click="createOpen = true">新增任务</button>
          </div>
        </div>

        <div class="gantt-board" :style="{ '--gantt-columns': ganttTimeline.length }">
          <div class="gantt-left gantt-head">任务列表</div>
          <div class="gantt-timeline gantt-head">
            <strong>{{ ganttRangeLabel }}</strong>
            <div class="gantt-dates">
              <span v-for="tick in ganttTimeline" :key="tick.key" :class="{ today: tick.isToday }">{{ tick.label }}</span>
            </div>
          </div>

          <template v-if="ganttRows.length === 0">
            <div class="gantt-empty">暂无符合条件的任务</div>
          </template>
          <template v-else>
            <template v-for="row in ganttRows" :key="row.id">
              <div class="gantt-left gantt-task-cell">
                <div class="gantt-task-line gantt-task-line-main">
                  <strong :title="row.title">{{ row.title }}</strong>
                  <em :class="row.tone">{{ row.statusText }}</em>
                </div>
                <div class="gantt-task-line gantt-task-line-sub">
                  <span :title="row.content">{{ row.content || '暂无任务内容' }}</span>
                  <b>{{ row.durationDays }} 天</b>
                </div>
                <div class="gantt-task-members" :title="row.memberTitle">
                  <span class="gantt-member-icon" aria-hidden="true">♙</span>
                  <span>{{ row.memberText }}</span>
                </div>
              </div>
              <div class="gantt-row">
                <span v-for="tick in ganttTimeline" :key="`${row.id}-${tick.key}`" :class="{ today: tick.isToday }"></span>
                <div
                  class="gantt-bar"
                  :class="row.tone"
                  :style="{ left: `${row.left}%`, width: `${row.width}%` }"
                >
                  <span class="gantt-bar-fill" :style="{ width: `${row.progress}%` }">
                    <strong v-if="row.showProgressLabel" class="gantt-bar-label">{{ row.progress }}%</strong>
                  </span>
                </div>
              </div>
            </template>
          </template>
        </div>
      </section>

    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <div class="modal-card task-modal-card">
        <TaskEditorForm @cancel="closeCreate" @saved="handleCreated" />
      </div>
    </div>

    <div v-if="taskListModal" class="modal-mask" @click.self="closeTaskList">
      <div class="modal-card gantt-list-modal">
        <div class="gantt-list-modal-head">
          <div>
            <h2>{{ taskListModalTitle }}</h2>
            <p>共 {{ taskListModalItems.length }} 项</p>
          </div>
          <button class="button secondary small" type="button" @click="closeTaskList">关闭</button>
        </div>
        <table v-if="!isNotificationListModal" class="table task-table">
          <thead>
            <tr>
              <th>任务</th>
              <th>负责人</th>
              <th>状态</th>
              <th>截止时间</th>
              <th>优先级</th>
              <th>通知</th>
              <th>子任务</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="taskListModalItems.length === 0">
              <td colspan="8">暂无相关任务</td>
            </tr>
            <tr v-for="task in taskListModalItems" :key="task.id">
              <td>
                <div class="task-table-title">{{ task.title }}</div>
                <div class="subtle-text clamp-2">{{ task.content }}</div>
              </td>
              <td>{{ joinNames(task.responsible_names) || task.owner_name || '-' }}</td>
              <td><span :class="statusUi(task).tone">{{ statusUi(task).text }}</span></td>
              <td>
                <div>{{ formatDateTime(task.end_at) }}</div>
                <div v-if="task.completed_at" class="subtle-text">完成时间：{{ formatDateTime(task.completed_at) }}</div>
                <div v-if="taskDelayStatus(task).text" :class="taskDelayStatus(task).className">{{ taskDelayStatus(task).text }}</div>
              </td>
              <td><span :class="resolvePriorityMeta(task.priority).tone">{{ resolvePriorityMeta(task.priority).label }}</span></td>
              <td>
                <div class="task-channel-stack">
                  <span class="task-channel-line">
                    <span>邮件：{{ notificationSummaryText(task, 'email') }}</span>
                    <span v-if="isNotificationSending(task, 'email')" class="inline-spinner task-channel-spinner" aria-label="正在发送"></span>
                  </span>
                  <span class="task-channel-line">
                    <span>即时消息：{{ notificationSummaryText(task, 'qax') }}</span>
                    <span v-if="isNotificationSending(task, 'qax')" class="inline-spinner task-channel-spinner" aria-label="正在发送"></span>
                  </span>
                </div>
              </td>
              <td>{{ task.subtask_count || 0 }}</td>
              <td>
                <div class="toolbar compact-toolbar">
                  <button class="button secondary small" type="button" @click="openTaskDetail(task.id)">详情</button>
                  <button class="button secondary small" type="button" @click="remindTask(task.id)">提醒</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <table v-else class="table">
          <thead>
            <tr>
              <th>任务</th>
              <th>提醒场景</th>
              <th>状态</th>
              <th>送达</th>
              <th>反馈</th>
              <th>未读人员</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="taskListModalItems.length === 0">
              <td colspan="8">暂无相关通知</td>
            </tr>
            <tr v-for="item in taskListModalItems" :key="`${taskListModal}-${item.pending_key || item.id}`">
              <td>{{ item.task_title || item.title || '-' }}</td>
              <td>
                <div>{{ item.notify_scene_text || item.notify_type_text || item.latest_notifications?.[notificationChannel]?.notify_type_text || '-' }}</div>
                <div class="subtle-text" v-if="item.remind_focus">{{ item.remind_focus }}</div>
              </td>
              <td>{{ item.status_text || notificationStatusText(item) }}</td>
              <td>{{ notificationDeliveryText(item) }}</td>
              <td>{{ notificationReadText(item) }}</td>
              <td>{{ notificationUnreadNames(item) }}</td>
              <td>{{ formatDateTime(item.created_at || item.latest_notifications?.[notificationChannel]?.sent_at) }}</td>
              <td>
                <div class="toolbar compact-toolbar">
                  <button
                    class="button secondary small"
                    type="button"
                    @click="openTaskDetail(item.task_id || item.id)"
                  >
                    任务详情
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="detailTaskId" class="modal-mask" @click.self="closeTaskDetail">
      <div class="modal-card task-modal-card task-detail-modal-card">
        <AdminTaskDetail :task-id="detailTaskId" @cancel="closeTaskDetail" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import http from '../../api/http'
import AdminTaskDetail from './AdminTaskDetail.vue'
import TaskEditorForm from '../../components/admin/TaskEditorForm.vue'
import iconDue from '../../assets/icons/clock.svg'
import iconDelayed from '../../assets/icons/triangle-alert.svg'
import iconNotice from '../../assets/icons/mail.svg'
import iconPending from '../../assets/icons/circle-play.svg'
import iconRunning from '../../assets/icons/trending-up.svg'
import { resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatExportTimestamp } from '../../utils/exportTable'
import { formatDateTime } from '../../utils/format'

const actionLoading = ref(false)
const feedback = ref({ title: '', message: '', type: 'success' })
const tasks = ref([])
const taskDetails = ref([])
const createOpen = ref(false)
const ganttOwnersSelected = ref([])
const ganttStatusesSelected = ref([])
const ganttDelaySelected = ref([])
const ganttScale = ref('day')
const ownerFilterOpen = ref(false)
const statusFilterOpen = ref(false)
const delayFilterOpen = ref(false)
const taskListModal = ref('')
const detailTaskId = ref(null)
const sendingNotificationTasks = ref({})
const NOTIFICATION_POLL_INTERVAL_MS = 2000
const NOTIFICATION_SENDING_TIMEOUT_MS = 120000
let feedbackTimerId = null
let notificationPollTimerId = null
const statusOptions = [
  { value: 'not_started', label: '未开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'done', label: '已完成' },
]
const delayOptions = [
  { value: 'delayed', label: '已延期' },
  { value: 'due_soon', label: '即将延期' },
]
const summary = ref({
  task_total: 0,
  in_progress_total: 0,
  done_total: 0,
  canceled_total: 0,
  delayed_total: 0,
  pending_total: 0,
  due_soon_total: 0,
  completion_rate: 0,
  email_success_rate: 0,
  qax_delivery_rate: 0,
  qax_read_rate: 0,
  retry_total: 0,
  mail_failure_total: 0,
  owner_task_distribution: [],
  warning_tasks: [],
})

const ringLength = 465
const completionCircleOffset = computed(() => ringLength - ringLength * safePercent(summary.value.completion_rate) / 100)

const ownerColors = ['#0050cb', '#565e74', '#ba1a1a', '#4f8cff', '#8aa0c8', '#16a34a', '#0f766e', '#7c3aed', '#ea580c', '#64748b']
const ownerDistribution = computed(() =>
  (summary.value.owner_task_distribution || []).slice(0, 10).map((item, index) => ({
    ...item,
    color: ownerColors[index % ownerColors.length],
  }))
)

const ownerDonutGradient = computed(() => {
  const total = ownerDistribution.value.reduce((sum, item) => sum + Number(item.task_total || 0), 0)
  if (!total) return 'conic-gradient(#dae2fd 0% 100%)'
  let cursor = 0
  const stops = ownerDistribution.value.map((item) => {
    const start = cursor
    const end = cursor + (Number(item.task_total || 0) / total) * 100
    cursor = end
    return `${item.color} ${start}% ${end}%`
  })
  return `conic-gradient(${stops.join(', ')})`
})

const warningTasks = computed(() => summary.value.warning_tasks || [])
const ganttOwners = computed(() => Array.from(new Set(tasks.value.map((task) => task.owner_name || joinNames(task.responsible_names)).filter(Boolean))).sort())
const isAllOwnersSelected = computed(() => ganttOwners.value.length > 0 && ganttOwnersSelected.value.length === ganttOwners.value.length)
const isAllStatusesSelected = computed(() => ganttStatusesSelected.value.length === statusOptions.length)
const isAllDelaySelected = computed(() => ganttDelaySelected.value.length === delayOptions.length)
const selectedOwnerText = computed(() => ganttOwnersSelected.value.length ? `${ganttOwnersSelected.value.length} 项` : '全部成员')
const selectedStatusText = computed(() => {
  if (!ganttStatusesSelected.value.length) return '所有状态'
  return statusOptions.filter((item) => ganttStatusesSelected.value.includes(item.value)).map((item) => item.label).join('、')
})
const selectedDelayText = computed(() => {
  if (!ganttDelaySelected.value.length) return '全部'
  return delayOptions.filter((item) => ganttDelaySelected.value.includes(item.value)).map((item) => item.label).join('、')
})
const dueTodayTotal = computed(() => {
  const today = startOfDay(new Date()).getTime()
  return tasks.value.filter((task) => {
    if (!task.end_at || ['done', 'canceled'].includes(task.main_status)) return false
    const endDate = new Date(task.end_at)
    return !Number.isNaN(endDate.getTime()) && startOfDay(endDate).getTime() === today
  }).length
})
const dueTodayUrgentText = computed(() => dueTodayTotal.value > 0 ? `${dueTodayTotal.value} 项待跟进` : '暂无到期')
const notStartedTasks = computed(() => tasks.value.filter((task) => task.main_status === 'not_started'))
const notStartedTotal = computed(() => notStartedTasks.value.length)
const dueTodayTasks = computed(() => {
  const today = startOfDay(new Date()).getTime()
  return tasks.value.filter((task) => {
    if (!task.end_at || ['done', 'canceled'].includes(task.main_status)) return false
    const endDate = new Date(task.end_at)
    return !Number.isNaN(endDate.getTime()) && startOfDay(endDate).getTime() === today
  })
})
const inProgressTasks = computed(() => tasks.value.filter((task) => task.main_status === 'in_progress'))
const delayedTasks = computed(() => tasks.value.filter((task) => isGanttTaskDelayed(task)))
const pendingEmailTasks = computed(() => buildPendingNotificationItems('email'))
const pendingQaxTasks = computed(() => buildPendingNotificationItems('qax'))
const pendingEmailTotal = computed(() => pendingEmailTasks.value.length)
const pendingQaxTotal = computed(() => pendingQaxTasks.value.length)
const pendingNoticeTotal = computed(() => pendingEmailTotal.value + pendingQaxTotal.value)
const taskListModalTitle = computed(() => {
  const titles = {
    notStarted: '未开始任务',
    inProgress: '进行中任务',
    dueToday: '今日到期任务',
    delayed: '已延期任务',
    pendingEmail: '待确认邮件列表',
    pendingQax: '待确认即时消息列表',
  }
  return titles[taskListModal.value] || '任务列表'
})
const isNotificationListModal = computed(() => ['pendingEmail', 'pendingQax'].includes(taskListModal.value))
const notificationChannel = computed(() => (taskListModal.value === 'pendingEmail' ? 'email' : 'qax'))
const taskListModalItems = computed(() => {
  const groups = {
    notStarted: notStartedTasks.value,
    inProgress: inProgressTasks.value,
    dueToday: dueTodayTasks.value,
    delayed: delayedTasks.value,
    pendingEmail: pendingEmailTasks.value,
    pendingQax: pendingQaxTasks.value,
  }
  return groups[taskListModal.value] || []
})
const filteredGanttTasks = computed(() =>
  tasks.value.filter((task) => {
    const owner = task.owner_name || joinNames(task.responsible_names)
    const matchOwner = ganttOwnersSelected.value.length === 0 || ganttOwnersSelected.value.includes(owner)
    const matchStatus = ganttStatusesSelected.value.length === 0 || ganttStatusesSelected.value.includes(task.main_status)
    const delayState = resolveGanttDelayState(task)
    const matchDelay = ganttDelaySelected.value.length === 0 || ganttDelaySelected.value.includes(delayState)
    return matchOwner && matchStatus && matchDelay
  })
)

const ganttTimeline = computed(() => buildTimeline(filteredGanttTasks.value, ganttScale.value))
const ganttRangeLabel = computed(() => {
  if (ganttTimeline.value.length === 0) return '暂无时间范围'
  const first = ganttTimeline.value[0].date
  const last = ganttTimeline.value[ganttTimeline.value.length - 1].date
  if (ganttScale.value === 'month') return `${first.getFullYear()} 年`
  return `${first.getFullYear()}年${first.getMonth() + 1}月 - ${last.getFullYear()}年${last.getMonth() + 1}月`
})

const ganttRows = computed(() => {
  const timeline = ganttTimeline.value
  if (timeline.length === 0) return []
  const min = timeline[0].date.getTime()
  const max = endOfUnit(timeline[timeline.length - 1].date, ganttScale.value).getTime()
  const total = Math.max(max - min, 1)
  return filteredGanttTasks.value
    .slice()
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime())
    .map((task) => {
      const start = clampDate(new Date(task.start_at), min, max)
      const end = clampDate(new Date(task.end_at), min, max)
      const duration = Math.max(end.getTime() - start.getTime(), 86400000)
      const status = resolveGanttStatus(task)
      const progress = resolveDateProgress(task, status)
      return {
        id: task.id,
        title: task.title,
        content: task.content || '',
        owner: task.owner_name || joinNames(task.responsible_names),
        memberText: resolveGanttMembers(task).text,
        memberTitle: resolveGanttMembers(task).title,
        statusText: status.text,
        tone: status.tone,
        progress,
        showProgressLabel: status.tone !== 'pending' && progress > 0,
        durationDays: Math.max(1, Math.ceil((new Date(task.end_at).getTime() - new Date(task.start_at).getTime()) / 86400000)),
        left: Math.max(0, ((start.getTime() - min) / total) * 100),
        width: Math.max(6, (duration / total) * 100),
      }
    })
})

function safePercent(value) {
  return Math.max(0, Math.min(100, Number(value || 0)))
}

function percentText(value) {
  return `${safePercent(value).toFixed(safePercent(value) % 1 === 0 ? 0 : 1)}%`
}

function joinNames(names) {
  return Array.isArray(names) && names.length > 0 ? names.join('、') : ''
}

function toggleAllOwners() {
  ganttOwnersSelected.value = isAllOwnersSelected.value ? [] : [...ganttOwners.value]
}

function toggleAllStatuses() {
  ganttStatusesSelected.value = isAllStatusesSelected.value ? [] : statusOptions.map((item) => item.value)
}

function toggleAllDelay() {
  ganttDelaySelected.value = isAllDelaySelected.value ? [] : delayOptions.map((item) => item.value)
}

function closeFloatingFilters(event) {
  if (event.target?.closest?.('.multi-filter')) return
  ownerFilterOpen.value = false
  statusFilterOpen.value = false
  delayFilterOpen.value = false
}

function openTaskList(type) {
  taskListModal.value = type
}

function closeTaskList() {
  taskListModal.value = ''
}

function openTaskDetail(taskId) {
  detailTaskId.value = taskId
}

function closeTaskDetail() {
  detailTaskId.value = null
}

function channelNotificationStatus(task, channel) {
  return task?.latest_notifications?.[channel] || {}
}

function notificationId(task, channel) {
  return Number(channelNotificationStatus(task, channel).notification_id || 0)
}

function taskNotificationSendingEntry(taskId) {
  return sendingNotificationTasks.value[String(taskId)] || null
}

function hasNewNotificationResult(task, channel, entry) {
  const baseline = Number(entry?.[`${channel}NotificationId`] || 0)
  return notificationId(task, channel) > baseline
}

function isNotificationSending(task, channel) {
  const entry = taskNotificationSendingEntry(task.id)
  return Boolean(entry) && !hasNewNotificationResult(task, channel, entry)
}

function notificationSummaryText(task, channel) {
  if (isNotificationSending(task, channel)) return '正在发送'
  return channelNotificationStatus(task, channel).summary || '未发送'
}

function isTaskNotificationSendFinished(task) {
  const entry = taskNotificationSendingEntry(task.id)
  return Boolean(entry) && hasNewNotificationResult(task, 'email', entry) && hasNewNotificationResult(task, 'qax', entry)
}

function pruneSendingNotificationTasks() {
  const now = Date.now()
  const next = {}
  Object.entries(sendingNotificationTasks.value).forEach(([taskId, entry]) => {
    const task = tasks.value.find((item) => String(item.id) === taskId)
    const startedAt = Number(entry?.startedAt || 0)
    if (!task) {
      if (now - startedAt < NOTIFICATION_SENDING_TIMEOUT_MS) next[taskId] = entry
      return
    }
    if (!isTaskNotificationSendFinished(task) && now - startedAt < NOTIFICATION_SENDING_TIMEOUT_MS) {
      next[taskId] = entry
    }
  })
  sendingNotificationTasks.value = next
  if (Object.keys(next).length === 0) {
    stopNotificationStatusPolling()
  }
}

function startNotificationStatusPolling() {
  if (notificationPollTimerId || Object.keys(sendingNotificationTasks.value).length === 0) return
  notificationPollTimerId = window.setTimeout(pollSendingNotificationTasks, NOTIFICATION_POLL_INTERVAL_MS)
}

function stopNotificationStatusPolling() {
  if (!notificationPollTimerId) return
  window.clearTimeout(notificationPollTimerId)
  notificationPollTimerId = null
}

function markTaskNotificationsSending(taskOrId) {
  const taskId = typeof taskOrId === 'object' ? taskOrId?.id : taskOrId
  if (!taskId) return
  const task = typeof taskOrId === 'object'
    ? taskOrId
    : tasks.value.find((item) => Number(item.id) === Number(taskId))
  sendingNotificationTasks.value = {
    ...sendingNotificationTasks.value,
    [String(taskId)]: {
      startedAt: Date.now(),
      emailNotificationId: notificationId(task, 'email'),
      qaxNotificationId: notificationId(task, 'qax'),
    },
  }
  startNotificationStatusPolling()
}

async function pollSendingNotificationTasks() {
  notificationPollTimerId = null
  if (Object.keys(sendingNotificationTasks.value).length === 0) return
  try {
    await loadSummary({ skipGlobalLoading: true })
  } finally {
    pruneSendingNotificationTasks()
    startNotificationStatusPolling()
  }
}

async function remindTask(taskId) {
  if (!window.confirm('确认向该任务负责人发送提醒？')) return
  markTaskNotificationsSending(taskId)
  await http.post(`/tasks/${taskId}/remind`, {}, { skipGlobalLoading: true })
  await loadSummary({ skipGlobalLoading: true })
  showFeedback('发送成功', '提醒已发送。')
}

function statusUi(task) {
  return resolveTaskStatusTone(task)
}

function taskDelayStatus(task) {
  const status = resolveDelayStatus(task)
  return {
    text: status.text,
    className: status.className,
  }
}

function resolveDelayStatus(item) {
  if (!item || ['done', 'canceled'].includes(item.main_status)) return { text: '', className: '' }
  const delayDays = Number(item.delay_days || 0)
  if (delayDays > 0) return { text: `已延期${delayDays}天`, className: 'error-text task-delay-text' }
  const endDate = new Date(item.end_at)
  if (Number.isNaN(endDate.getTime())) return { text: '', className: '' }
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const endDay = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate()).getTime()
  const daysToDue = Math.ceil((endDay - startOfToday) / 86400000)
  if (daysToDue < 0) return { text: `已延期${Math.abs(daysToDue)}天`, className: 'error-text task-delay-text' }
  if (daysToDue >= 0 && daysToDue <= 3) return { text: '即将延期', className: 'warning-text task-delay-text' }
  return { text: '', className: '' }
}

function resolveGanttDelayState(task) {
  const status = resolveDelayStatus(task)
  if (!status.text) return ''
  return status.text.includes('即将延期') ? 'due_soon' : 'delayed'
}

function buildPendingNotificationItems(channel) {
  return taskDetails.value
    .map((task) => buildPendingNotificationItem(task, channel))
    .filter(Boolean)
}

function buildPendingNotificationItem(task, channel) {
  const sources = [
    { label: '主任务', name: '', status: task.latest_notifications?.[channel] || {} },
    ...(task.members || []).map((member) => ({
      label: '主任务',
      name: member.name,
      status: member.latest_notifications?.[channel] || {},
    })),
    ...(task.subtasks || []).map((subtask) => ({
      label: subtask.title || subtask.content || '子任务',
      name: subtask.assignee_name,
      status: subtask.latest_notifications?.[channel] || {},
    })),
  ].filter((source) => source.status?.notification_id || source.status?.sent_at)
  if (sources.length === 0) return null
  const latestKey = latestNotificationKey(sources)
  const latestSources = sources.filter((source) => notificationKey(source.status) === latestKey)
  const pendingSources = latestSources.filter((source) => isPendingNotificationStatus(source.status, channel))
  if (pendingSources.length === 0) return null
  const unreadNames = uniqueValues(pendingSources.flatMap((source) => {
    const names = source.status.pending_recipient_names || []
    return names.length ? names : [source.name || notificationUnreadName(source.status)]
  }))
  const focusText = uniqueValues(pendingSources.map((source) => source.label)).join('、')
  const baseStatus = task.latest_notifications?.[channel]?.notification_id === latestSources[0].status.notification_id
    ? task.latest_notifications[channel]
    : latestSources[0].status
  return {
    ...task,
    id: task.id,
    task_id: task.id,
    task_title: task.title,
    pending_key: `${task.id}-${channel}-${latestKey}`,
    remind_focus: focusText,
    latest_notifications: {
      [channel]: {
        ...baseStatus,
        delivery_status: pendingSources.some((source) => source.status.delivery_status === 'failed') ? 'failed' : baseStatus.delivery_status,
        read_status: 'unread',
        read_status_text: `${unreadNames.length || pendingSources.length} 人未确认`,
        pending_recipient_names: unreadNames,
      },
    },
  }
}

function latestNotificationKey(sources) {
  return sources
    .map((source) => notificationKey(source.status))
    .sort()
    .at(-1)
}

function notificationKey(status) {
  if (status.notification_id != null) return `id:${String(status.notification_id).padStart(12, '0')}`
  return `time:${status.sent_at || ''}`
}

function uniqueValues(values) {
  return Array.from(new Set(values.filter(Boolean)))
}

function isPendingNotificationStatus(status, channel) {
  if (status.delivery_status === 'failed') return true
  return channel === 'email' ? status.read_status === 'unread' : status.read_status !== 'read'
}

function notificationUnreadName(status) {
  const names = status.pending_recipient_names || []
  return Array.isArray(names) && names.length > 0 ? names[0] : ''
}

function notificationChannelText(item) {
  return notificationChannel.value === 'email' ? '邮件' : '即时消息'
}

function notificationStatusText(item) {
  const status = item.latest_notifications?.[notificationChannel.value] || {}
  if (status.delivery_status === 'failed') return '发送失败'
  if (status.read_status === 'read') return '已确认'
  return '待确认'
}

function notificationDeliveryText(item) {
  const status = item.latest_notifications?.[notificationChannel.value] || {}
  if (status.delivery_status_text) return status.delivery_status_text
  if (status.delivery_status === 'failed') return '异常'
  if (status.delivery_status === 'delivered') return '已送达'
  return status.summary || '-'
}

function notificationReadText(item) {
  const status = item.latest_notifications?.[notificationChannel.value] || {}
  if (status.read_status_text) return status.read_status_text
  if (status.read_status === 'read') return '已读'
  return status.summary || '未读'
}

function notificationUnreadNames(item) {
  const status = item.latest_notifications?.[notificationChannel.value] || {}
  const names = status.pending_recipient_names || []
  return Array.isArray(names) && names.length > 0 ? names.join('、') : '-'
}

function resolveGanttMembers(task) {
  const names = Array.isArray(task.responsible_names) && task.responsible_names.length > 0
    ? task.responsible_names
    : [task.owner_name].filter(Boolean)
  if (names.length === 0) return { text: '-', title: '-' }
  const full = names.join('、')
  return {
    text: full,
    title: full,
  }
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function addDays(date, count) {
  const next = new Date(date)
  next.setDate(next.getDate() + count)
  return next
}

function addMonths(date, count) {
  const next = new Date(date)
  next.setMonth(next.getMonth() + count)
  return next
}

function startOfWeek(date) {
  const day = startOfDay(date)
  const offset = day.getDay() === 0 ? 6 : day.getDay() - 1
  return addDays(day, -offset)
}

function endOfUnit(date, scale) {
  if (scale === 'month') return addMonths(new Date(date.getFullYear(), date.getMonth(), 1), 1)
  if (scale === 'week') return addDays(startOfWeek(date), 7)
  return addDays(startOfDay(date), 1)
}

function buildTimeline(source, scale) {
  const dated = source.filter((task) => task.start_at && task.end_at)
  if (dated.length === 0) return []
  const starts = dated.map((task) => new Date(task.start_at).getTime())
  const ends = dated.map((task) => new Date(task.end_at).getTime())
  let cursor = new Date(Math.min(...starts))
  let limit = new Date(Math.max(...ends))
  if (scale === 'month') {
    cursor = new Date(cursor.getFullYear(), 0, 1)
    limit = new Date(limit.getFullYear(), 11, 1)
  } else if (scale === 'week') {
    cursor = startOfWeek(cursor)
    limit = addDays(startOfWeek(limit), 7)
  } else {
    cursor = addDays(startOfDay(cursor), -2)
    limit = addDays(startOfDay(limit), 2)
  }

  const ticks = []
  const today = startOfDay(new Date()).getTime()
  const maxTicks = scale === 'day' ? 32 : scale === 'week' ? 18 : 12
  while (cursor <= limit && ticks.length < maxTicks) {
    const date = new Date(cursor)
    ticks.push({
      key: date.toISOString(),
      date,
      label: scale === 'month' ? `${date.getMonth() + 1}月` : scale === 'week' ? `${date.getMonth() + 1}/${date.getDate()}` : `${date.getDate()}`,
      isToday: startOfDay(date).getTime() === today,
    })
    cursor = scale === 'month' ? addMonths(cursor, 1) : scale === 'week' ? addDays(cursor, 7) : addDays(cursor, 1)
  }
  return ticks
}

function clampDate(date, min, max) {
  const time = Number.isNaN(date.getTime()) ? min : date.getTime()
  return new Date(Math.max(min, Math.min(max, time)))
}

function isGanttTaskDelayed(task) {
  if (!task || ['done', 'canceled'].includes(task.main_status)) return false
  if (Number(task.delay_days || 0) > 0) return true
  if (!task.end_at) return false
  const endDate = new Date(task.end_at)
  if (Number.isNaN(endDate.getTime())) return false
  return startOfDay(new Date()).getTime() > startOfDay(endDate).getTime()
}

function resolveGanttStatus(task) {
  if (task.main_status === 'done') return { text: '已完成', tone: 'done' }
  if (isGanttTaskDelayed(task)) {
    const baseText = task.main_status === 'not_started' ? '未开始' : '进行中'
    return { text: `${baseText} · 已延期`, tone: 'delayed' }
  }
  if (task.main_status === 'in_progress') return { text: '进行中', tone: 'running' }
  return { text: '未开始', tone: 'pending' }
}

function resolveDateProgress(task, status) {
  if (status.tone === 'done') return 100
  if (!task.start_at || !task.end_at) return 0
  const start = new Date(task.start_at).getTime()
  const end = new Date(task.end_at).getTime()
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return 0
  const current = new Date().getTime()
  const progress = ((current - start) / (end - start)) * 100
  return Math.round(Math.max(0, Math.min(100, progress)))
}

function exportGantt() {
  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    window.alert('浏览器拦截了 PDF 导出窗口，请允许弹窗后重试。')
    return
  }
  printWindow.document.write(buildGanttPrintHtml())
  printWindow.document.close()
  printWindow.focus()
  printWindow.print()
}

function formatGanttTickDate(date) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function taskCoversTick(task, tickDate) {
  if (!task.start_at || !task.end_at) return false
  const start = startOfDay(new Date(task.start_at)).getTime()
  const end = startOfDay(new Date(task.end_at)).getTime()
  const tick = startOfDay(tickDate).getTime()
  return !Number.isNaN(start) && !Number.isNaN(end) && tick >= start && tick <= end
}

function buildGanttPrintHtml() {
  const page = document.querySelector('.dashboard-page')?.cloneNode(true)
  if (!page) return '<!doctype html><meta charset="utf-8"><body>暂无可导出的甘特图</body>'
  page.querySelectorAll('.dashboard-feedback, .modal-mask').forEach((item) => item.remove())
  page.querySelectorAll('button').forEach((button) => {
    if (button.classList.contains('gantt-summary-link')) return
    button.remove()
  })
  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
    .map((item) => item.outerHTML)
    .join('')
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>项目助手甘特图${formatExportTimestamp()}</title>
  ${styles}
  <style>
    @page { size: A4 landscape; margin: 10mm; }
    body { margin: 0; background: #f6f8fc; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .page { padding: 0; }
    .app-topbar, .gantt-actions, .gantt-filters { display: none !important; }
    .gantt-panel { box-shadow: none; }
    .gantt-board { overflow: visible !important; width: max-content; min-width: 100%; }
    .gantt-left { width: 260px; }
    .gantt-row, .gantt-timeline { min-width: 900px; }
  </style>
</head>
<body>
  ${page.outerHTML}
  <script>window.addEventListener('afterprint', () => window.close())<\/script>
</body>
</html>`
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function closeCreate() {
  createOpen.value = false
}

async function handleCreated(task) {
  closeCreate()
  markTaskNotificationsSending(task)
  await loadSummary({ skipGlobalLoading: true })
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

async function loadSummary(config = {}) {
  const [{ data: summaryData }, { data: taskData }] = await Promise.all([
    http.get('/dashboard/summary', config),
    http.get('/tasks', config),
  ])
  summary.value = summaryData
  tasks.value = taskData
  taskDetails.value = await Promise.all(taskData.map((task) => http.get(`/tasks/${task.id}`, config).then((response) => response.data)))
  pruneSendingNotificationTasks()
}

async function pollInbox() {
  actionLoading.value = true
  try {
    const { data } = await http.post('/admin/mail/poll')
    showFeedback('邮件采集完成', data.message || `当前状态：${data.status}`, ['success', 'initialized'].includes(data.status) ? 'success' : 'error')
    await loadSummary()
  } catch (error) {
    showFeedback('邮件采集失败', error.response?.data?.detail || '采集邮箱时发生错误', 'error')
  } finally {
    actionLoading.value = false
  }
}

async function collectQaxStatus() {
  actionLoading.value = true
  try {
    const { data } = await http.post('/admin/qax/collect')
    showFeedback('即时消息采集完成', data.message || `更新 ${data.updated_count || 0} 条`, data.status === 'success' ? 'success' : 'error')
    await loadSummary()
  } catch (error) {
    showFeedback('即时消息采集失败', error.response?.data?.detail || '采集 QAX 状态时发生错误', 'error')
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeFloatingFilters)
  loadSummary()
})

onUnmounted(() => {
  document.removeEventListener('click', closeFloatingFilters)
  stopNotificationStatusPolling()
  if (feedbackTimerId) {
    window.clearTimeout(feedbackTimerId)
  }
})
</script>

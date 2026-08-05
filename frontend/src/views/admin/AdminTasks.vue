<template>
  <section class="page">
    <div v-if="feedback.message" class="panel dashboard-feedback">
      <strong>{{ feedback.title }}</strong>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <div class="panel filter-shell">
      <div class="section-head task-list-action-head">
        <div>
          <h2>任务列表</h2>
        </div>
        <div class="toolbar">
          <button class="button secondary" @click="exportFilteredTasks">导出任务</button>
          <button class="button secondary" @click="importOpen = true">导入任务</button>
          <button @click="createOpen = true">新建任务</button>
        </div>
      </div>
      <div class="filter-grid task-simple-filter-grid">
        <div class="filter-field">
          <span class="filter-label">搜索</span>
          <input v-model="keyword" placeholder="搜索任务名称或负责人" />
        </div>
        <div class="filter-field">
          <span class="filter-label">状态</span>
          <div class="multi-filter">
            <button class="button secondary small" @click="statusFilterOpen = !statusFilterOpen">{{ selectedStatusText }}</button>
            <div v-if="statusFilterOpen" class="multi-filter-menu">
              <label class="multi-filter-all">
                <span>全选</span>
                <input type="checkbox" :checked="isAllStatusesSelected" @change="toggleAllStatuses" />
              </label>
              <label v-for="item in statusOptions" :key="item.value">
                <span>{{ item.label }}</span>
                <input v-model="status" type="checkbox" :value="item.value" />
              </label>
            </div>
          </div>
        </div>
        <div class="filter-field">
          <span class="filter-label">优先级</span>
          <div class="multi-filter">
            <button class="button secondary small" @click="priorityFilterOpen = !priorityFilterOpen">{{ selectedPriorityText }}</button>
            <div v-if="priorityFilterOpen" class="multi-filter-menu">
              <label class="multi-filter-all">
                <span>全选</span>
                <input type="checkbox" :checked="isAllPrioritiesSelected" @change="toggleAllPriorities" />
              </label>
              <label v-for="item in priorityOptions" :key="item.value">
                <span>{{ item.label }}</span>
                <input v-model="priorityFilter" type="checkbox" :value="item.value" />
              </label>
            </div>
          </div>
        </div>
        <div class="filter-field">
          <span class="filter-label">延期</span>
          <div class="multi-filter">
            <button class="button secondary small" @click="delayFilterOpen = !delayFilterOpen">{{ selectedDelayText }}</button>
            <div v-if="delayFilterOpen" class="multi-filter-menu">
              <label class="multi-filter-all">
                <span>全选</span>
                <input type="checkbox" :checked="isAllDelaySelected" @change="toggleAllDelay" />
              </label>
              <label v-for="item in delayOptions" :key="item.value">
                <span>{{ item.label }}</span>
                <input v-model="delayFilter" type="checkbox" :value="item.value" />
              </label>
            </div>
          </div>
        </div>
        <div class="filter-field">
          <span class="filter-label">截止日期</span>
          <div class="date-range-filter">
            <button class="button secondary small date-range-trigger" type="button" @click="dateFilterOpen = !dateFilterOpen">
              <span :class="{ empty: !dateFrom }">{{ dateFrom || '开始日期' }}</span>
              <b>→</b>
              <span :class="{ empty: !dateTo }">{{ dateTo || '结束日期' }}</span>
              <img :src="calendarIcon" alt="" aria-hidden="true" />
            </button>
            <div v-if="dateFilterOpen" class="date-range-menu">
              <div class="date-range-nav">
                <button class="icon-button" type="button" @click="shiftRangeMonth(-12)">«</button>
                <button class="icon-button" type="button" @click="shiftRangeMonth(-1)">‹</button>
                <button class="icon-button" type="button" @click="shiftRangeMonth(1)">›</button>
                <button class="icon-button" type="button" @click="shiftRangeMonth(12)">»</button>
              </div>
              <div class="date-range-calendars">
                <section v-for="month in dateRangeMonths" :key="month.key" class="date-range-month">
                  <h3>{{ month.title }}</h3>
                  <div class="date-range-week">
                    <span v-for="day in weekLabels" :key="day">{{ day }}</span>
                  </div>
                  <div class="date-range-days">
                    <button
                      v-for="day in month.days"
                      :key="day.key"
                      type="button"
                      :class="{
                        muted: !day.inMonth,
                        selected: day.selected,
                        inRange: day.inRange,
                        today: day.today,
                      }"
                      @click="selectRangeDate(day.value)"
                    >
                      {{ day.label }}
                    </button>
                  </div>
                </section>
              </div>
              <div class="date-range-actions">
                <button class="button secondary small" type="button" @click="clearDateRange">清空</button>
                <button class="button small" type="button" @click="dateFilterOpen = false">确定</button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="filter-footer">
        <div class="filter-summary">共 {{ filteredTasks.length }} 项任务</div>
        <div class="filter-actions">
          <button class="button secondary" @click="resetFilters">重置</button>
          <button @click="applyFilters">查询</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <table class="table task-table">
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
          <tr v-if="pagedTasks.length === 0">
            <td colspan="8">暂无符合条件的任务</td>
          </tr>
          <tr v-for="task in pagedTasks" :key="task.id">
            <td>
              <div class="task-table-title">{{ task.title }}</div>
              <div class="subtle-text clamp-2">{{ task.content }}</div>
            </td>
            <td>{{ joinNames(task.responsible_names) }}</td>
            <td><span :class="statusUi(task).tone">{{ statusUi(task).text }}</span></td>
            <td>
              <div>{{ formatDateTime(task.end_at) }}</div>
              <div v-if="task.completed_at" class="subtle-text">完成时间：{{ formatDateTime(task.completed_at) }}</div>
              <div v-if="delayStatus(task).text" :class="delayStatus(task).className">{{ delayStatus(task).text }}</div>
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
              <div class="toolbar">
                <button class="button secondary small" @click="openDetail(task.id)">详情</button>
                <button class="button secondary small" @click="openEdit(task.id)">编辑</button>
                <button class="button secondary small" @click="remind(task.id)">提醒</button>
                <button class="button danger small" @click="removeTask(task.id)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppPagination v-model="page" v-model:page-size="pageSize" :total="filteredTasks.length" />

    <div v-if="createOpen" class="modal-mask">
      <div class="modal-card task-modal-card">
        <TaskEditorForm @cancel="closeCreate" @saved="handleCreated" />
      </div>
    </div>

    <div v-if="editTaskId" class="modal-mask">
      <div class="modal-card task-modal-card">
        <TaskEditorForm :task-id="editTaskId" @cancel="closeEdit" @saved="handleEdited" />
      </div>
    </div>

    <div v-if="detailTaskId" class="modal-mask">
      <div class="modal-card task-modal-card task-detail-modal-card">
        <AdminTaskDetail :task-id="detailTaskId" @cancel="closeDetail" />
      </div>
    </div>

    <div v-if="importOpen" class="modal-mask">
      <div class="modal-card task-modal-card">
        <TaskImportDialog @cancel="closeImport" @imported="handleImported" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import http from '../../api/http'
import AdminTaskDetail from './AdminTaskDetail.vue'
import AppPagination from '../../components/AppPagination.vue'
import TaskEditorForm from '../../components/admin/TaskEditorForm.vue'
import TaskImportDialog from '../../components/admin/TaskImportDialog.vue'
import calendarIcon from '../../assets/icons/calendar-days.svg'
import { priorityMeta, resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { downloadUtf16Table, formatExportTimestamp } from '../../utils/exportTable'
import { formatDateTime } from '../../utils/format'

const tasks = ref([])
const feedback = ref({ title: '', message: '', type: 'success' })
const keyword = ref('')
const status = ref([])
const delayFilter = ref([])
const priorityFilter = ref([])
const statusFilterOpen = ref(false)
const delayFilterOpen = ref(false)
const priorityFilterOpen = ref(false)
const dateFilterOpen = ref(false)
const statusOptions = [
  { value: 'not_started', label: '未开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'done', label: '已完成' },
]
const delayOptions = [
  { value: 'delayed', label: '已延期' },
  { value: 'due_soon', label: '即将延期' },
  { value: 'normal', label: '未延期' },
]
const priorityOptions = Object.entries(priorityMeta).map(([value, item]) => ({ value, label: item.label }))
const dateFrom = ref('')
const dateTo = ref('')
const dateRangeCursor = ref(startOfMonth(new Date()))
const page = ref(1)
const pageSize = ref(20)
const createOpen = ref(false)
const importOpen = ref(false)
const editTaskId = ref(null)
const detailTaskId = ref(null)
const sendingNotificationTasks = ref({})
const NOTIFICATION_POLL_INTERVAL_MS = 2000
const NOTIFICATION_SENDING_TIMEOUT_MS = 120000
let notificationPollTimerId = null

const isAllStatusesSelected = computed(() => status.value.length === statusOptions.length)
const isAllDelaySelected = computed(() => delayFilter.value.length === delayOptions.length)
const isAllPrioritiesSelected = computed(() => priorityFilter.value.length === priorityOptions.length)

const filteredTasks = computed(() => {
  const query = keyword.value.trim()
  return tasks.value.filter((item) => {
    const matchKeyword =
      !query ||
      item.title.includes(query) ||
      joinNames(item.responsible_names).includes(query)
    const matchStatus = status.value.length === 0 || status.value.includes(item.main_status)
    const matchPriority = priorityFilter.value.length === 0 || priorityFilter.value.includes(item.priority)
    const delayState = delayStatus(item).state
    const matchDelay =
      delayFilter.value.length === 0 ||
      delayFilter.value.includes(delayState) ||
      (delayFilter.value.includes('normal') && !delayState)
    const endDate = toDateOnly(item.end_at)
    const matchDateFrom = !dateFrom.value || (endDate && endDate >= dateFrom.value)
    const matchDateTo = !dateTo.value || (endDate && endDate <= dateTo.value)
    return matchKeyword && matchStatus && matchPriority && matchDelay && matchDateFrom && matchDateTo
  })
})

const selectedStatusText = computed(() => {
  if (!status.value.length) return '全部状态'
  return statusOptions.filter((item) => status.value.includes(item.value)).map((item) => item.label).join('、')
})

const selectedDelayText = computed(() => {
  if (!delayFilter.value.length) return '全部'
  return delayOptions.filter((item) => delayFilter.value.includes(item.value)).map((item) => item.label).join('、')
})
const selectedPriorityText = computed(() => {
  if (!priorityFilter.value.length) return '全部优先级'
  return priorityOptions.filter((item) => priorityFilter.value.includes(item.value)).map((item) => item.label).join('、')
})
const selectedDateRangeText = computed(() => {
  if (dateFrom.value && dateTo.value) return `${dateFrom.value} 至 ${dateTo.value}`
  if (dateFrom.value) return `${dateFrom.value} 起`
  if (dateTo.value) return `截至 ${dateTo.value}`
  return '选择日期范围'
})
const weekLabels = ['一', '二', '三', '四', '五', '六', '日']
const dateRangeMonths = computed(() => [buildCalendarMonth(0), buildCalendarMonth(1)])

const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredTasks.value.slice(start, start + pageSize.value)
})

watch([keyword, status, priorityFilter, delayFilter, dateFrom, dateTo], () => {
  page.value = 1
}, { deep: true })

function applyFilters() {
  page.value = 1
}

function resetFilters() {
  keyword.value = ''
  status.value = []
  priorityFilter.value = []
  delayFilter.value = []
  clearDateRange()
  page.value = 1
}

function clearDateRange() {
  dateFrom.value = ''
  dateTo.value = ''
}

function shiftRangeMonth(count) {
  dateRangeCursor.value = addMonths(dateRangeCursor.value, count)
}

function selectRangeDate(value) {
  if (!dateFrom.value || (dateFrom.value && dateTo.value)) {
    dateFrom.value = value
    dateTo.value = ''
    return
  }
  if (value < dateFrom.value) {
    dateTo.value = dateFrom.value
    dateFrom.value = value
    return
  }
  dateTo.value = value
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function addMonths(date, count) {
  return new Date(date.getFullYear(), date.getMonth() + count, 1)
}

function toDateValue(date) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function buildCalendarMonth(offset) {
  const monthDate = addMonths(dateRangeCursor.value, offset)
  const monthStart = startOfMonth(monthDate)
  const mondayOffset = (monthStart.getDay() + 6) % 7
  const firstCell = new Date(monthStart)
  firstCell.setDate(monthStart.getDate() - mondayOffset)
  const today = toDateValue(new Date())
  const days = Array.from({ length: 42 }, (_, index) => {
    const current = new Date(firstCell)
    current.setDate(firstCell.getDate() + index)
    const value = toDateValue(current)
    const hasRange = dateFrom.value && dateTo.value
    return {
      key: `${monthDate.getFullYear()}-${monthDate.getMonth()}-${index}`,
      label: current.getDate(),
      value,
      inMonth: current.getMonth() === monthDate.getMonth(),
      selected: value === dateFrom.value || value === dateTo.value,
      inRange: Boolean(hasRange && value >= dateFrom.value && value <= dateTo.value),
      today: value === today,
    }
  })
  return {
    key: `${monthDate.getFullYear()}-${monthDate.getMonth()}`,
    title: `${monthDate.getFullYear()} 年 ${monthDate.getMonth() + 1} 月`,
    days,
  }
}

function toggleAllStatuses() {
  status.value = isAllStatusesSelected.value ? [] : statusOptions.map((item) => item.value)
}

function toggleAllDelay() {
  delayFilter.value = isAllDelaySelected.value ? [] : delayOptions.map((item) => item.value)
}

function toggleAllPriorities() {
  priorityFilter.value = isAllPrioritiesSelected.value ? [] : priorityOptions.map((item) => item.value)
}

function closeFloatingFilters(event) {
  if (event.target?.closest?.('.multi-filter, .date-range-filter')) return
  statusFilterOpen.value = false
  priorityFilterOpen.value = false
  delayFilterOpen.value = false
  dateFilterOpen.value = false
}

function statusUi(task) {
  return resolveTaskStatusTone(task)
}

function joinNames(names) {
  return Array.isArray(names) && names.length > 0 ? names.join(', ') : '-'
}

function toDateOnly(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function isOpenTask(task) {
  return !['done', 'canceled'].includes(task.main_status)
}

function delayStatus(task) {
  if (!isOpenTask(task)) return { state: '', text: '', className: '' }
  const delayDays = Number(task.delay_days || 0)
  if (delayDays > 0) {
    return { state: 'delayed', text: `已延期${delayDays}天`, className: 'error-text task-delay-text' }
  }
  const endDate = new Date(task.end_at)
  if (Number.isNaN(endDate.getTime())) return { state: '', text: '', className: '' }
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const endDay = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate()).getTime()
  const daysToDue = Math.ceil((endDay - startOfToday) / 86400000)
  if (daysToDue < 0) {
    return { state: 'delayed', text: `已延期${Math.abs(daysToDue)}天`, className: 'error-text task-delay-text' }
  }
  if (daysToDue >= 0 && daysToDue <= 3) {
    return { state: 'due_soon', text: '即将延期', className: 'warning-text task-delay-text' }
  }
  return { state: '', text: '', className: '' }
}

function channelNotificationStatus(task, channel) {
  return task?.latest_notifications?.[channel] || {}
}

function notificationId(task, channel) {
  const status = channelNotificationStatus(task, channel)
  return Number(status.notification_id || 0)
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

function markTaskNotificationsSending(taskOrId, baseline = {}) {
  const taskId = typeof taskOrId === 'object' ? taskOrId?.id : taskOrId
  if (!taskId) return
  const task = typeof taskOrId === 'object'
    ? taskOrId
    : tasks.value.find((item) => Number(item.id) === Number(taskId))
  sendingNotificationTasks.value = {
    ...sendingNotificationTasks.value,
    [String(taskId)]: {
      startedAt: Date.now(),
      emailNotificationId: Number.isFinite(Number(baseline.emailNotificationId))
        ? Number(baseline.emailNotificationId)
        : notificationId(task, 'email'),
      qaxNotificationId: Number.isFinite(Number(baseline.qaxNotificationId))
        ? Number(baseline.qaxNotificationId)
        : notificationId(task, 'qax'),
    },
  }
  startNotificationStatusPolling()
}

async function pollSendingNotificationTasks() {
  notificationPollTimerId = null
  if (Object.keys(sendingNotificationTasks.value).length === 0) return
  try {
    await loadTasks({ skipGlobalLoading: true })
  } finally {
    pruneSendingNotificationTasks()
    startNotificationStatusPolling()
  }
}

async function loadTasks(config = {}) {
  const { data } = await http.get('/tasks', config)
  tasks.value = data
  pruneSendingNotificationTasks()
}

function hideCreate() {
  createOpen.value = false
}

function hideImport() {
  importOpen.value = false
}

function openEdit(taskId) {
  editTaskId.value = taskId
}

function openDetail(taskId) {
  detailTaskId.value = taskId
}

function hideEdit() {
  editTaskId.value = null
}

function hideDetail() {
  detailTaskId.value = null
}

async function refreshTaskList() {
  await loadTasks({ skipGlobalLoading: true })
}

async function closeCreate() {
  hideCreate()
  await refreshTaskList()
}

async function closeImport() {
  hideImport()
  await refreshTaskList()
}

async function closeEdit() {
  hideEdit()
  await refreshTaskList()
}

async function closeDetail() {
  hideDetail()
  await refreshTaskList()
}

async function handleCreated(task) {
  hideCreate()
  markTaskNotificationsSending(task)
  await refreshTaskList()
}

async function handleEdited(task) {
  hideEdit()
  if (task?.notification_sending) {
    markTaskNotificationsSending(task)
    await refreshTaskList()
    return
  }
  await refreshTaskList()
}

async function handleImported(result) {
  hideImport()
  const createdTaskIds = result?.created_task_ids || []
  createdTaskIds.forEach((taskId) => {
    markTaskNotificationsSending(taskId, {
      emailNotificationId: 0,
      qaxNotificationId: 0,
    })
  })
  await refreshTaskList()
}

async function exportFilteredTasks() {
  const details = await Promise.all(filteredTasks.value.map((task) => http.get(`/tasks/${task.id}`).then((response) => response.data)))
  const rows = [['序号', '任务名称', '任务内容', '子任务', '负责人', '任务状态', '截止日期']]
  details.forEach((task, index) => {
    const subtasks = Array.isArray(task.subtasks) ? task.subtasks : []
    const subtaskAssigneeIds = new Set(subtasks.map((subtask) => Number(subtask.assignee_id)).filter(Boolean))
    const membersWithoutSubtasks = (task.members || []).filter((member) => !subtaskAssigneeIds.has(Number(member.user_id)))
    const taskStatusText = task.status_text || statusUi(task).text
    if (subtasks.length === 0) {
      rows.push([
        index + 1,
        task.title,
        task.content || '',
        '',
        membersWithoutSubtasks.map((member) => member.name).filter(Boolean).join('、') || joinNamesForExport(task.responsible_names),
        taskStatusText,
        toDateOnly(task.end_at),
      ])
      return
    }
    subtasks.forEach((subtask) => {
      rows.push([
        index + 1,
        task.title,
        task.content || '',
        subtask.content || subtask.title || '',
        subtask.assignee_name || '',
        taskStatusText,
        toDateOnly(task.end_at),
      ])
    })
    if (membersWithoutSubtasks.length > 0) {
      rows.push([
        index + 1,
        task.title,
        task.content || '',
        '',
        membersWithoutSubtasks.map((member) => member.name).filter(Boolean).join('、'),
        taskStatusText,
        toDateOnly(task.end_at),
      ])
    }
  })
  downloadUtf16Table(`任务列表导出${formatExportTimestamp()}.xls`, rows)
}

function joinNamesForExport(names) {
  return Array.isArray(names) && names.length > 0 ? names.join('、') : ''
}

async function remind(taskId) {
  if (!window.confirm('确认向该任务负责人发送提醒？')) return
  markTaskNotificationsSending(taskId)
  await http.post(`/tasks/${taskId}/remind`, {}, { skipGlobalLoading: true })
  await loadTasks({ skipGlobalLoading: true })
  showFeedback('发送成功', '提醒已发送。')
}

let feedbackTimerId = null
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

async function removeTask(taskId) {
  if (!window.confirm('确认删除该任务？')) return
  await http.delete(`/tasks/${taskId}`)
  await loadTasks()
}

onMounted(() => {
  document.addEventListener('click', closeFloatingFilters)
  loadTasks()
})

onUnmounted(() => {
  document.removeEventListener('click', closeFloatingFilters)
  stopNotificationStatusPolling()
  if (feedbackTimerId) {
    window.clearTimeout(feedbackTimerId)
  }
})
</script>

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
                <span>邮件：{{ task.latest_notifications?.email?.summary || '暂无' }}</span>
                <span>即时消息：{{ task.latest_notifications?.qax?.summary || '暂无' }}</span>
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

    <AppPagination v-model="page" :total="filteredTasks.length" :page-size="pageSize" />

    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <div class="modal-card task-modal-card">
        <TaskEditorForm @cancel="closeCreate" @saved="handleCreated" />
      </div>
    </div>

    <div v-if="editTaskId" class="modal-mask" @click.self="closeEdit">
      <div class="modal-card task-modal-card">
        <TaskEditorForm :task-id="editTaskId" @cancel="closeEdit" @saved="handleEdited" />
      </div>
    </div>

    <div v-if="detailTaskId" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card task-modal-card task-detail-modal-card">
        <AdminTaskDetail :task-id="detailTaskId" @cancel="closeDetail" />
      </div>
    </div>

    <div v-if="importOpen" class="modal-mask" @click.self="closeImport">
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
import { resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { downloadUtf16Table, formatExportTimestamp } from '../../utils/exportTable'
import { formatDateTime } from '../../utils/format'

const tasks = ref([])
const feedback = ref({ title: '', message: '', type: 'success' })
const keyword = ref('')
const status = ref([])
const delayFilter = ref([])
const statusFilterOpen = ref(false)
const delayFilterOpen = ref(false)
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
const dateFrom = ref('')
const dateTo = ref('')
const dateRangeCursor = ref(startOfMonth(new Date()))
const page = ref(1)
const pageSize = 10
const createOpen = ref(false)
const importOpen = ref(false)
const editTaskId = ref(null)
const detailTaskId = ref(null)

const isAllStatusesSelected = computed(() => status.value.length === statusOptions.length)
const isAllDelaySelected = computed(() => delayFilter.value.length === delayOptions.length)

const filteredTasks = computed(() => {
  const query = keyword.value.trim()
  return tasks.value.filter((item) => {
    const matchKeyword =
      !query ||
      item.title.includes(query) ||
      joinNames(item.responsible_names).includes(query)
    const matchStatus = status.value.length === 0 || status.value.includes(item.main_status)
    const delayState = delayStatus(item).state
    const matchDelay =
      delayFilter.value.length === 0 ||
      delayFilter.value.includes(delayState) ||
      (delayFilter.value.includes('normal') && !delayState)
    const endDate = toDateOnly(item.end_at)
    const matchDateFrom = !dateFrom.value || (endDate && endDate >= dateFrom.value)
    const matchDateTo = !dateTo.value || (endDate && endDate <= dateTo.value)
    return matchKeyword && matchStatus && matchDelay && matchDateFrom && matchDateTo
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
const selectedDateRangeText = computed(() => {
  if (dateFrom.value && dateTo.value) return `${dateFrom.value} 至 ${dateTo.value}`
  if (dateFrom.value) return `${dateFrom.value} 起`
  if (dateTo.value) return `截至 ${dateTo.value}`
  return '选择日期范围'
})
const weekLabels = ['一', '二', '三', '四', '五', '六', '日']
const dateRangeMonths = computed(() => [buildCalendarMonth(0), buildCalendarMonth(1)])

const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})

watch([keyword, status, delayFilter, dateFrom, dateTo], () => {
  page.value = 1
}, { deep: true })

function applyFilters() {
  page.value = 1
}

function resetFilters() {
  keyword.value = ''
  status.value = []
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

function closeFloatingFilters(event) {
  if (event.target?.closest?.('.multi-filter, .date-range-filter')) return
  statusFilterOpen.value = false
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

async function loadTasks() {
  const { data } = await http.get('/tasks')
  tasks.value = data
}

function closeCreate() {
  createOpen.value = false
}

function closeImport() {
  importOpen.value = false
}

function openEdit(taskId) {
  editTaskId.value = taskId
}

function openDetail(taskId) {
  detailTaskId.value = taskId
}

function closeEdit() {
  editTaskId.value = null
}

function closeDetail() {
  detailTaskId.value = null
}

async function handleCreated() {
  closeCreate()
  await loadTasks()
}

async function handleEdited() {
  closeEdit()
  await loadTasks()
}

async function handleImported() {
  closeImport()
  await loadTasks()
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
  await http.post(`/tasks/${taskId}/remind`)
  await loadTasks()
  showFeedback('发送成功', '提醒已发送，将在 3 秒后自动隐藏。')
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
  if (feedbackTimerId) {
    window.clearTimeout(feedbackTimerId)
  }
})
</script>

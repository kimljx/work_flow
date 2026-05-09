<template>
  <section class="page">
    <div class="panel filter-shell">
      <div class="section-head task-list-action-head">
        <div>
          <h2>任务列表</h2>
        </div>
        <div class="toolbar">
          <button class="button secondary" @click="importOpen = true">导入任务</button>
          <button @click="createOpen = true">新建任务</button>
        </div>
      </div>
      <div class="filter-grid task-simple-filter-grid">
        <div class="filter-field">
          <span class="filter-label">搜索</span>
          <input v-model="keyword" placeholder="搜索任务名称或负责人" @keyup.enter="applyFilters" />
        </div>
        <div class="filter-field">
          <span class="filter-label">状态</span>
          <select v-model="status">
            <option value="">全部状态</option>
            <option value="not_started">未开始</option>
            <option value="in_progress">进行中</option>
            <option value="done">已完成</option>
            <option value="canceled">已取消</option>
          </select>
        </div>
        <div class="filter-field">
          <span class="filter-label">延期</span>
          <select v-model="delayFilter">
            <option value="">全部</option>
            <option value="delayed">已延期</option>
            <option value="due_soon">即将延期</option>
            <option value="normal">未延期</option>
          </select>
        </div>
        <div class="filter-field">
          <span class="filter-label">截止日期起</span>
          <input v-model="dateFrom" type="date" @keyup.enter="applyFilters" />
        </div>
        <div class="filter-field">
          <span class="filter-label">截止日期止</span>
          <input v-model="dateTo" type="date" @keyup.enter="applyFilters" />
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
                <router-link class="button secondary small" :to="`/admin/tasks/${task.id}`">查看</router-link>
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

    <div v-if="importOpen" class="modal-mask" @click.self="closeImport">
      <div class="modal-card task-modal-card">
        <TaskImportDialog @cancel="closeImport" @imported="handleImported" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import TaskEditorForm from '../../components/admin/TaskEditorForm.vue'
import TaskImportDialog from '../../components/admin/TaskImportDialog.vue'
import { resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatDateTime } from '../../utils/format'

const router = useRouter()
const tasks = ref([])
const keyword = ref('')
const status = ref('')
const delayFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const appliedFilters = ref({
  keyword: '',
  status: '',
  delayFilter: '',
  dateFrom: '',
  dateTo: '',
})
const page = ref(1)
const pageSize = 10
const createOpen = ref(false)
const importOpen = ref(false)
const editTaskId = ref(null)

const filteredTasks = computed(() => {
  const filters = appliedFilters.value
  const query = filters.keyword.trim()
  return tasks.value.filter((item) => {
    const matchKeyword =
      !query ||
      item.title.includes(query) ||
      joinNames(item.responsible_names).includes(query)
    const matchStatus = !filters.status || item.main_status === filters.status
    const delayState = delayStatus(item).state
    const matchDelay =
      !filters.delayFilter ||
      filters.delayFilter === delayState ||
      (filters.delayFilter === 'normal' && !delayState)
    const endDate = toDateOnly(item.end_at)
    const matchDateFrom = !filters.dateFrom || (endDate && endDate >= filters.dateFrom)
    const matchDateTo = !filters.dateTo || (endDate && endDate <= filters.dateTo)
    return matchKeyword && matchStatus && matchDelay && matchDateFrom && matchDateTo
  })
})

const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})

function applyFilters() {
  appliedFilters.value = {
    keyword: keyword.value,
    status: status.value,
    delayFilter: delayFilter.value,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
  }
  page.value = 1
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  delayFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  applyFilters()
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

function closeEdit() {
  editTaskId.value = null
}

async function handleCreated(task) {
  closeCreate()
  await loadTasks()
  router.push(`/admin/tasks/${task.id}`)
}

async function handleEdited() {
  closeEdit()
  await loadTasks()
}

async function handleImported() {
  closeImport()
  await loadTasks()
}

async function remind(taskId) {
  if (!window.confirm('确认向该任务负责人发送提醒？')) return
  await http.post(`/tasks/${taskId}/remind`)
  await loadTasks()
}

async function removeTask(taskId) {
  if (!window.confirm('确认删除该任务？')) return
  await http.delete(`/tasks/${taskId}`)
  await loadTasks()
}

onMounted(loadTasks)
</script>

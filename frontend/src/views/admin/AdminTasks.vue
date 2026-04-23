<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">任务模块</div>
        <h1 class="workspace-title">任务排期与执行视图</h1>
        <p class="workspace-subtitle">集中查看任务起止时间、优先级、当前状态和送达情况，支持直接进入详情、提醒和删除。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="{ path: '/admin/import-export', query: { from: route.fullPath } }">导入任务</router-link>
        <router-link class="button" :to="{ path: '/admin/tasks/new', query: { from: route.fullPath } }">新建任务</router-link>
      </div>
    </div>

    <div class="panel filter-shell">
      <div class="filter-grid">
        <input v-model="keyword" placeholder="搜索任务标题或负责人" />
        <select v-model="status">
          <option value="">全部状态</option>
          <option value="not_started">未开始</option>
          <option value="in_progress">进行中</option>
          <option value="done">已完成</option>
          <option value="canceled">已取消</option>
        </select>
      </div>
      <div class="filter-chip-group">
        <button
          v-for="item in subtaskFilterOptions"
          :key="item.value"
          :class="['button secondary small filter-chip', { active: subtaskStatusFilter === item.value }]"
          @click="toggleSubtaskFilter(item.value)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="filter-chip-group">
        <button
          v-for="item in advancedFilterOptions"
          :key="item.key"
          :class="['button secondary small filter-chip', { active: advancedFilters[item.key] }]"
          @click="toggleAdvancedFilter(item.key)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="filter-summary">
        当前展示 {{ filteredTasks.length }} 条任务
        <span v-if="activeFilterTexts.length > 0">，已启用：{{ activeFilterTexts.join(' / ') }}</span>
      </div>
    </div>

    <div class="task-stack">
      <article v-if="pagedTasks.length === 0" class="panel empty-state">
        <h2>暂无符合条件的任务</h2>
        <p>可以调整筛选条件，或直接创建新的任务计划。</p>
      </article>

      <article
        v-for="task in pagedTasks"
        :key="task.id"
        class="task-work-card"
      >
        <div :class="statusUi(task).dot"></div>
        <div class="task-work-main">
          <div class="task-work-heading">
            <div>
              <div class="task-work-kicker">任务编号 #{{
                task.id
              }}</div>
              <h2>{{ task.title }}</h2>
              <p>{{ task.content }}</p>
            </div>
            <span :class="resolvePriorityMeta(task.priority).tone">
              {{ resolvePriorityMeta(task.priority).label }}
            </span>
          </div>

          <div class="task-info-grid">
            <div class="info-cell">
              <span class="info-label">负责人</span>
              <strong>{{ task.owner_name || '-' }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">参与成员</span>
              <strong>{{ task.participant_count }} 人</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">开始时间</span>
              <strong>{{ formatDateTime(task.start_at) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">结束时间</span>
              <strong>{{ formatDateTime(task.end_at) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">计划用时</span>
              <strong>{{ formatMinutes(task.planned_minutes) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">通知送达</span>
              <strong>{{ task.delivered_count }}/{{ task.notification_total }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">子任务进度</span>
              <strong>{{ task.subtask_count || 0 }} 项</strong>
              <div v-if="subtaskStatusSummary(task).length > 0" class="subtask-summary-row">
                <span
                  v-for="item in subtaskStatusSummary(task)"
                  :key="`${task.id}-${item.status}`"
                  :class="`${resolveSubtaskStatusMeta(item.status, item.label).tone} status-chip`"
                >
                  {{ item.label }} {{ item.count }}
                </span>
              </div>
              <div v-else class="subtle-text">暂无子任务</div>
            </div>
          </div>
        </div>

        <div class="task-work-side">
          <span :class="statusUi(task).tone">{{ statusUi(task).text }}</span>
          <div class="task-side-note">优先级 {{ task.priority_text }}</div>
          <div class="task-side-note">提醒设置 {{ task.due_remind_days > 0 ? `提前 ${task.due_remind_days} 天` : '未开启' }}</div>
          <div class="toolbar task-actions">
            <router-link class="button secondary" :to="{ path: `/admin/tasks/${task.id}`, query: { from: route.fullPath } }">详情</router-link>
            <button class="button secondary" @click="remind(task.id)">提醒</button>
            <button class="button danger" @click="removeTask(task.id)">删除</button>
          </div>
        </div>
      </article>
    </div>

    <AppPagination v-model="page" :total="filteredTasks.length" :page-size="pageSize" />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { resolvePriorityMeta, resolveSubtaskStatusMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatDateTime, formatMinutes } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const tasks = ref([])
const keyword = ref('')
const status = ref('')
const subtaskStatusFilter = ref('')
const page = ref(1)
const pageSize = 8
const advancedFilters = reactive({
  delayedOnly: false,
  lockedOnly: false,
  lowDeliveryOnly: false,
})
const subtaskFilterOptions = [
  { value: '', label: '全部子任务' },
  { value: 'in_progress', label: '进行中子任务' },
  { value: 'pending', label: '待开始子任务' },
  { value: 'done', label: '已完成子任务' },
  { value: 'canceled', label: '已取消子任务' },
  { value: 'empty', label: '无子任务' },
]
const advancedFilterOptions = [
  { key: 'delayedOnly', label: '仅看延期任务' },
  { key: 'lockedOnly', label: '仅看已锁定' },
  { key: 'lowDeliveryOnly', label: '仅看送达不足' },
]
const activeFilterTexts = computed(() => {
  const labels = []
  if (status.value) {
    const statusText = {
      not_started: '主状态=未开始',
      in_progress: '主状态=进行中',
      done: '主状态=已完成',
      canceled: '主状态=已取消',
    }[status.value]
    if (statusText) {
      labels.push(statusText)
    }
  }
  if (subtaskStatusFilter.value) {
    const subtaskText = {
      in_progress: '子任务=进行中',
      pending: '子任务=待开始',
      done: '子任务=已完成',
      canceled: '子任务=已取消',
      empty: '无子任务',
    }[subtaskStatusFilter.value]
    if (subtaskText) {
      labels.push(subtaskText)
    }
  }
  if (advancedFilters.delayedOnly) {
    labels.push('延期中')
  }
  if (advancedFilters.lockedOnly) {
    labels.push('状态已锁定')
  }
  if (advancedFilters.lowDeliveryOnly) {
    labels.push('通知送达不足')
  }
  return labels
})

const filteredTasks = computed(() =>
  tasks.value.filter((item) => {
    const query = keyword.value.trim()
    const matchKeyword =
      !query ||
      item.title.includes(query) ||
      (item.owner_name || '').includes(query)
    const matchStatus = !status.value || item.main_status === status.value
    const matchSubtask = matchSubtaskFilter(item)
    const matchAdvanced = matchAdvancedFilters(item)
    return matchKeyword && matchStatus && matchSubtask && matchAdvanced
  })
)

const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})

watch([keyword, status, subtaskStatusFilter, () => advancedFilters.delayedOnly, () => advancedFilters.lockedOnly, () => advancedFilters.lowDeliveryOnly], () => {
  page.value = 1
})

/**
 * 返回任务主状态的视觉展示配置。
 * @param {object} task 当前任务对象。
 * @returns {{tone: string, dot: string, text: string}} 列表卡片使用的状态样式与文案。
 */
function statusUi(task) {
  return resolveTaskStatusTone(task)
}

/**
 * 提取当前任务的子任务状态统计，用于列表信息卡和快捷筛选。
 * @param {object} task 当前任务对象。
 * @returns {Array<{status: string, label: string, count: number}>} 只保留数量大于 0 的状态项。
 */
function subtaskStatusSummary(task) {
  return (task.subtask_status_summary || []).filter((item) => Number(item.count) > 0)
}

/**
 * 判断任务是否命中当前子任务筛选条件。
 * @param {object} task 当前任务对象。
 * @returns {boolean} 是否需要在列表中保留。
 */
function matchSubtaskFilter(task) {
  if (!subtaskStatusFilter.value) {
    return true
  }
  if (subtaskStatusFilter.value === 'empty') {
    return Number(task.subtask_count || 0) === 0
  }
  return subtaskStatusSummary(task).some((item) => item.status === subtaskStatusFilter.value)
}

/**
 * 判断任务是否命中高级组合筛选条件。
 * 这些条件与主状态、子任务状态筛选叠加使用，用于快速定位“进行中且延期”等交叉场景。
 * @param {object} task 当前任务对象。
 * @returns {boolean} 是否满足当前高级筛选组合。
 */
function matchAdvancedFilters(task) {
  if (advancedFilters.delayedOnly && Number(task.delay_days || 0) <= 0) {
    return false
  }
  if (advancedFilters.lockedOnly && !task.state_locked) {
    return false
  }
  if (advancedFilters.lowDeliveryOnly && Number(task.delivered_count || 0) >= Number(task.notification_total || 0)) {
    return false
  }
  return true
}

/**
 * 切换列表顶部的子任务快捷筛选。
 * 再次点击同一项时会恢复为“全部子任务”，减少用户来回清空筛选的操作成本。
 * @param {string} value 目标筛选值。
 * @returns {void}
 */
function toggleSubtaskFilter(value) {
  subtaskStatusFilter.value = subtaskStatusFilter.value === value ? '' : value
}

/**
 * 切换高级组合筛选项。
 * 支持与主状态和子任务筛选同时生效，用于快速锁定复杂业务场景。
 * @param {'delayedOnly' | 'lockedOnly' | 'lowDeliveryOnly'} key 高级筛选键。
 * @returns {void}
 */
function toggleAdvancedFilter(key) {
  advancedFilters[key] = !advancedFilters[key]
}

/**
 * 拉取当前账号可见的任务列表。
 * @returns {Promise<void>}
 */
async function loadTasks() {
  const { data } = await http.get('/tasks')
  tasks.value = data
}

/**
 * 处理从导入页返回任务列表后的刷新提示。
 * @returns {Promise<void>}
 */
async function handleRouteRefresh() {
  if (route.query.refresh !== 'import') {
    return
  }
  await loadTasks()
  const successCount = Number(route.query.import_success_count || 0)
  const failureCount = Number(route.query.import_failure_count || 0)
  window.alert(`任务导入完成：成功 ${successCount} 条，失败 ${failureCount} 条`)
  router.replace({ path: route.path, query: {} })
}

/**
 * 为指定任务创建一次手动提醒。
 * @param {number} taskId 任务编号。
 * @returns {Promise<void>}
 */
async function remind(taskId) {
  if (!window.confirm('确认要对该任务发送手动提醒吗？')) return
  await http.post(`/tasks/${taskId}/remind`)
  window.alert('已创建提醒通知。')
  await loadTasks()
}

/**
 * 删除指定任务并刷新列表。
 * @param {number} taskId 任务编号。
 * @returns {Promise<void>}
 */
async function removeTask(taskId) {
  if (!window.confirm('删除任务会保留审计记录，是否继续？')) return
  await http.delete(`/tasks/${taskId}`)
  await loadTasks()
}

onMounted(async () => {
  await loadTasks()
  await handleRouteRefresh()
})
</script>

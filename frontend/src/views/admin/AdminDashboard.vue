<template>
  <section class="page dashboard-page">
    <header class="dashboard-page-head dashboard-page-head-compact">
      <h1>{{ activeView === 'overview' ? '仪表盘概览' : '任务甘特图' }}</h1>
      <div class="dashboard-view-switch">
        <button :class="{ active: activeView === 'overview' }" @click="activeView = 'overview'">仪表盘</button>
        <button :class="{ active: activeView === 'gantt' }" @click="activeView = 'gantt'">甘特图</button>
      </div>
    </header>

    <div v-if="feedback.message" class="panel dashboard-feedback">
      <strong>{{ feedback.title }}</strong>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <template v-if="activeView === 'overview'">
      <section class="panel dashboard-metrics-panel">
        <div class="dashboard-panel-title">
          <span class="dashboard-title-icon">□</span>
          <h2>任务指标统计</h2>
        </div>
        <div class="dashboard-metrics-body">
          <div class="dashboard-completion-ring">
            <svg viewBox="0 0 180 180" aria-hidden="true">
              <circle cx="90" cy="90" r="74" class="dashboard-ring-bg" />
              <circle
                cx="90"
                cy="90"
                r="74"
                class="dashboard-ring-value"
                :style="{ strokeDashoffset: completionCircleOffset }"
              />
            </svg>
            <div>
              <strong>{{ summary.completion_rate }}%</strong>
              <span>总完成率</span>
            </div>
          </div>

          <div class="dashboard-metric-cards">
            <article class="dashboard-metric-card">
              <span>总任务数</span>
              <strong>{{ summary.task_total }}</strong>
              <small>系统内全部任务</small>
            </article>
            <article class="dashboard-metric-card">
              <span>未开始</span>
              <strong>{{ summary.pending_total }}</strong>
              <small>等待启动</small>
            </article>
            <article class="dashboard-metric-card">
              <span>进行中</span>
              <strong>{{ summary.in_progress_total }}</strong>
              <small>正在推进</small>
            </article>
            <article class="dashboard-metric-card success">
              <span>已完成</span>
              <strong>{{ summary.done_total }}</strong>
              <small>完成率 {{ summary.completion_rate }}%</small>
            </article>
            <article class="dashboard-metric-card danger">
              <span>已延期</span>
              <strong>{{ summary.delayed_total }}</strong>
              <small>需重点跟进</small>
            </article>
          </div>
        </div>
      </section>

      <div class="dashboard-grid-main">
        <section class="panel dashboard-notice-analysis">
          <div class="dashboard-panel-title split">
            <h2>通知分析</h2>
            <span class="dashboard-trend-icon">⌁</span>
          </div>

          <article class="dashboard-notice-block">
            <div class="dashboard-notice-line">
              <div>
                <strong>邮件性能</strong>
                <p>{{ summary.mail_failure_total }} 条异常 · {{ summary.retry_total }} 次重试</p>
              </div>
              <b>{{ percentText(summary.email_success_rate) }}</b>
            </div>
            <div class="dashboard-notice-meta">
              <span>发送成功率</span>
              <span>{{ percentText(summary.email_success_rate) }}</span>
            </div>
            <div class="dashboard-notice-track">
              <span :style="{ width: `${safePercent(summary.email_success_rate)}%` }"></span>
            </div>
          </article>

          <article class="dashboard-notice-block">
            <div class="dashboard-notice-line">
              <div>
                <strong>即时消息性能</strong>
                <p>企安信送达率 {{ percentText(summary.qax_delivery_rate) }}</p>
              </div>
              <b>{{ percentText(summary.qax_read_rate) }}</b>
            </div>
            <div class="dashboard-notice-meta">
              <span>已读率</span>
              <span>{{ percentText(summary.qax_read_rate) }}</span>
            </div>
            <div class="dashboard-notice-track active">
              <span :style="{ width: `${safePercent(summary.qax_read_rate)}%` }"></span>
            </div>
          </article>
        </section>

        <section class="panel dashboard-sync-panel">
          <div class="dashboard-panel-title">
            <span class="dashboard-title-icon">↻</span>
            <h2>同步控制中心</h2>
          </div>
          <div class="dashboard-sync-list">
            <article class="dashboard-sync-card">
              <div>
                <span class="dashboard-sync-icon">✉</span>
                <div>
                  <strong>邮件通讯同步</strong>
                  <p>手动采集邮箱任务回复和状态反馈</p>
                </div>
              </div>
              <button :disabled="actionLoading" @click="pollInbox">刷新</button>
            </article>
            <article class="dashboard-sync-card">
              <div>
                <span class="dashboard-sync-icon">⚡</span>
                <div>
                  <strong>即时消息同步</strong>
                  <p>采集 QAX 消息送达和已读状态</p>
                </div>
              </div>
              <button :disabled="actionLoading" @click="collectQaxStatus">采集</button>
            </article>
          </div>
          <div class="dashboard-system-line">
            <span>系统运行状态</span>
            <strong><i></i>正常运行中</strong>
          </div>
        </section>
      </div>

      <div class="dashboard-grid-bottom">
        <section class="panel dashboard-distribution-panel dashboard-owner-panel">
          <h2>任务按负责人分布</h2>
          <div class="dashboard-distribution-body compact">
            <div class="dashboard-donut small" :style="{ background: ownerDonutGradient }"></div>
            <div class="dashboard-distribution-list">
              <div v-for="item in ownerDistribution" :key="item.owner_name">
                <span><i :style="{ background: item.color }"></i>{{ item.owner_name }}</span>
                <strong>{{ item.task_total }}</strong>
              </div>
              <div v-if="ownerDistribution.length === 0">
                <span><i></i>暂无负责人</span>
                <strong>0</strong>
              </div>
            </div>
          </div>
          <div class="dashboard-owner-mini">
            <span>已延期 {{ summary.delayed_total }}</span>
            <span>即将延期 {{ summary.due_soon_total }}</span>
          </div>
        </section>

        <section class="panel dashboard-warning-panel">
          <div class="dashboard-panel-title split">
            <h2>任务预警状态</h2>
          </div>
          <table class="table dashboard-warning-table">
            <thead>
              <tr>
                <th>任务名称</th>
                <th>负责人</th>
                <th>延期状态</th>
                <th>截止时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="warningTasks.length === 0">
                <td colspan="5">暂无即将到期或已延期任务</td>
              </tr>
              <tr v-for="task in warningTasks" :key="task.task_id">
                <td>{{ task.title }}</td>
                <td>{{ task.owner_name || '-' }}</td>
                <td>
                  <span :class="task.warning_type === 'delayed' ? 'status-tone status-tone-danger' : 'status-tone status-tone-warning'">
                    {{ task.warning_text }}
                  </span>
                </td>
                <td>{{ formatDateTime(task.end_at) }}</td>
                <td><router-link class="button secondary small" :to="task.route || `/admin/tasks/${task.task_id}`">查看详情</router-link></td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </template>

    <template v-else>
      <section class="panel gantt-panel">
        <div class="gantt-toolbar">
          <div class="gantt-filters">
            <label>
              <span>成员</span>
              <select v-model="ganttOwner">
                <option value="">全部成员</option>
                <option v-for="name in ganttOwners" :key="name" :value="name">{{ name }}</option>
              </select>
            </label>
            <label>
              <span>任务状态</span>
              <select v-model="ganttStatus">
                <option value="">所有状态</option>
                <option value="not_started">未开始</option>
                <option value="in_progress">进行中</option>
                <option value="done">已完成</option>
                <option value="canceled">已取消</option>
              </select>
            </label>
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
            <button class="button secondary" @click="exportGantt">导出数据</button>
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
    </template>

    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <div class="modal-card task-modal-card">
        <TaskEditorForm @cancel="closeCreate" @saved="handleCreated" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../../api/http'
import TaskEditorForm from '../../components/admin/TaskEditorForm.vue'
import { formatDateTime } from '../../utils/format'

const actionLoading = ref(false)
const activeView = ref('overview')
const feedback = ref({ title: '', message: '', type: 'success' })
const tasks = ref([])
const createOpen = ref(false)
const ganttOwner = ref('')
const ganttStatus = ref('')
const ganttScale = ref('day')
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
const filteredGanttTasks = computed(() =>
  tasks.value.filter((task) => {
    const owner = task.owner_name || joinNames(task.responsible_names)
    const matchOwner = !ganttOwner.value || owner === ganttOwner.value
    const matchStatus = !ganttStatus.value || task.main_status === ganttStatus.value
    return matchOwner && matchStatus
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
  const rows = ganttRows.value.map((row) => `${row.title},${row.owner},${row.statusText},${row.durationDays}天`).join('\n')
  const blob = new Blob([`任务,负责人,状态,周期\n${rows}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = '任务甘特图.csv'
  link.click()
  URL.revokeObjectURL(url)
}

function closeCreate() {
  createOpen.value = false
}

async function handleCreated() {
  closeCreate()
  activeView.value = 'gantt'
  await loadSummary()
}

function showFeedback(title, message, type = 'success') {
  feedback.value = { title, message, type }
}

async function loadSummary() {
  const [{ data: summaryData }, { data: taskData }] = await Promise.all([
    http.get('/dashboard/summary'),
    http.get('/tasks'),
  ])
  summary.value = summaryData
  tasks.value = taskData
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

onMounted(loadSummary)
</script>

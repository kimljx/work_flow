<template>
  <section class="page dashboard-page">
    <header class="dashboard-page-head">
      <h1>仪表盘概览</h1>
      <p>系统全域指标监控与通讯同步管理</p>
    </header>

    <div v-if="feedback.message" class="panel dashboard-feedback">
      <strong>{{ feedback.title }}</strong>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

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
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../../api/http'
import { formatDateTime } from '../../utils/format'

const actionLoading = ref(false)
const feedback = ref({ title: '', message: '', type: 'success' })
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

function safePercent(value) {
  return Math.max(0, Math.min(100, Number(value || 0)))
}

function percentText(value) {
  return `${safePercent(value).toFixed(safePercent(value) % 1 === 0 ? 0 : 1)}%`
}

function showFeedback(title, message, type = 'success') {
  feedback.value = { title, message, type }
}

async function loadSummary() {
  const { data } = await http.get('/dashboard/summary')
  summary.value = data
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

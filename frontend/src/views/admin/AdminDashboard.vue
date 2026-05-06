<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">管理看板</div>
        <h1 class="workspace-title">任务推进总览</h1>
        <p class="workspace-subtitle">{{ heroSummary }}</p>
      </div>
      <div class="toolbar">
        <button @click="goCreateTask">新建任务</button>
        <router-link class="button secondary" to="/admin/tasks">查看任务</router-link>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact dashboard-stat-primary">
        <span class="metric-label">任务总数</span>
        <strong>{{ summary.task_total }}</strong>
        <div class="subtle-text">{{ healthScoreText }}</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">完成率</span>
        <strong>{{ summary.completion_rate }}%</strong>
        <div class="subtle-text">已完成 {{ summary.done_total }} / 全部 {{ summary.task_total }}</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">进行中</span>
        <strong>{{ summary.in_progress_total }}</strong>
        <div class="subtle-text">未开始 {{ summary.pending_total }}</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">即将到期</span>
        <strong>{{ summary.due_soon_total }}</strong>
        <div class="subtle-text">已延期 {{ summary.delayed_total }}</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">邮件状态</span>
        <strong>{{ summary.email_success_rate }}%</strong>
        <div class="subtle-text">异常 {{ summary.mail_failure_total }}</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">即时消息</span>
        <strong>{{ summary.qax_read_rate }}%</strong>
        <div class="subtle-text">送达 {{ summary.qax_delivery_rate }}%</div>
      </div>
    </div>

    <div class="detail-grid">
      <div class="panel">
        <div class="section-head">
          <div>
            <h2>七日趋势</h2>
            <p>只保留任务推进最关键的新增、完成和延期走势。</p>
          </div>
        </div>

        <div v-if="trendHasData" class="dashboard-simple-chart">
          <svg viewBox="0 0 720 240" preserveAspectRatio="none" class="dashboard-simple-chart-svg">
            <line
              v-for="grid in chartGridLines"
              :key="grid"
              x1="40"
              :y1="grid"
              x2="680"
              :y2="grid"
              class="dashboard-simple-chart-grid"
            />
            <polyline :points="createdLinePoints" class="dashboard-simple-chart-line dashboard-simple-chart-line-created" />
            <polyline :points="completedLinePoints" class="dashboard-simple-chart-line dashboard-simple-chart-line-completed" />
            <polyline :points="delayedLinePoints" class="dashboard-simple-chart-line dashboard-simple-chart-line-delayed" />
            <text
              v-for="label in chartLabels"
              :key="label.label"
              :x="label.x"
              y="228"
              text-anchor="middle"
              class="dashboard-simple-chart-label"
            >
              {{ label.label }}
            </text>
          </svg>

          <div class="dashboard-simple-legend">
            <span><i class="dashboard-simple-dot created"></i>新增</span>
            <span><i class="dashboard-simple-dot completed"></i>完成</span>
            <span><i class="dashboard-simple-dot delayed"></i>延期</span>
          </div>
        </div>
        <div v-else class="muted-block">当前数据量还不足以形成趋势。</div>
      </div>

      <div class="panel">
        <div class="section-head">
          <div>
            <h2>任务结构</h2>
            <p>快速判断状态分布和优先级压力，不再放审批入口和通知中心入口。</p>
          </div>
        </div>

        <div class="dashboard-structure-grid">
          <div>
            <div class="filter-label">状态分布</div>
            <div
              v-for="item in summary.status_distribution"
              :key="item.key"
              class="dashboard-structure-row"
            >
              <div class="dashboard-structure-meta">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <div class="dashboard-structure-track">
                <span :style="{ width: `${toPercent(item.value, summary.task_total)}%` }"></span>
              </div>
            </div>
          </div>

          <div>
            <div class="filter-label">优先级分布</div>
            <div
              v-for="item in summary.priority_distribution"
              :key="item.key"
              class="dashboard-structure-row"
            >
              <div class="dashboard-structure-meta">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <div class="dashboard-structure-track warm">
                <span :style="{ width: `${toPercent(item.value, summary.task_total)}%` }"></span>
              </div>
            </div>
          </div>
        </div>

        <div class="dashboard-signal-grid">
          <div class="info-cell">
            <span class="info-label">健康任务率</span>
            <strong>{{ summary.healthy_task_rate }}%</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">QAX 送达率</span>
            <strong>{{ summary.qax_delivery_rate }}%</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">QAX 已读率</span>
            <strong>{{ summary.qax_read_rate }}%</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">重试次数</span>
            <strong>{{ summary.retry_total }}</strong>
          </div>
        </div>
      </div>
    </div>

    <div class="detail-grid">
      <div class="panel">
        <div class="section-head">
          <div>
            <h2>重点提醒</h2>
            <p>仅保留与任务推进直接相关的提醒项。</p>
          </div>
        </div>

        <div class="dashboard-attention-list-simple">
          <article
            v-for="item in attentionItems"
            :key="`${item.title}-${item.route}`"
            class="dashboard-attention-item-simple"
          >
            <div>
              <div class="dashboard-attention-item-top">
                <span :class="toneClass(item.tone)">{{ item.value || '提醒' }}</span>
                <strong>{{ item.title }}</strong>
              </div>
              <p class="subtle-text">{{ item.description }}</p>
            </div>
            <router-link class="button secondary small" :to="item.route || '/admin/tasks'">
              {{ item.action_label || '查看' }}
            </router-link>
          </article>
        </div>
      </div>

      <div class="panel">
        <div class="section-head">
          <div>
            <h2>快捷入口</h2>
            <p>固定为任务相关入口，避免看板再次长成一个管理菜单。</p>
          </div>
        </div>

        <div class="dashboard-action-list-simple">
          <router-link
            v-for="item in quickActions"
            :key="item.route"
            class="dashboard-action-item-simple"
            :to="item.route"
          >
            <strong>{{ item.title }}</strong>
            <p class="subtle-text">{{ item.description }}</p>
            <span class="dashboard-action-text">{{ item.action_label }}</span>
          </router-link>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../../api/http'

const router = useRouter()
const summary = ref({
  task_total: 0,
  in_progress_total: 0,
  done_total: 0,
  canceled_total: 0,
  delayed_total: 0,
  pending_total: 0,
  due_soon_total: 0,
  completion_rate: 0,
  healthy_task_rate: 0,
  email_success_rate: 0,
  qax_delivery_rate: 0,
  qax_read_rate: 0,
  retry_total: 0,
  pending_delay_requests: 0,
  mail_failure_total: 0,
  health_score: 0,
  status_distribution: [],
  priority_distribution: [],
  task_trend: [],
  attention_items: [],
  quick_actions: [],
})

const heroSummary = computed(() => {
  if (!summary.value.task_total) {
    return '当前还没有任务数据，先新建任务或导入任务，让看板开始形成可跟踪的节奏。'
  }
  return `当前共 ${summary.value.task_total} 项任务，完成率 ${summary.value.completion_rate}% 。其中 ${summary.value.due_soon_total} 项即将到期，${summary.value.delayed_total} 项已延期。`
})

const healthScoreText = computed(() => {
  if (summary.value.health_score >= 80) return '整体推进较稳定'
  if (summary.value.health_score >= 60) return '需要关注部分风险'
  return '建议优先处理风险任务'
})

const attentionItems = computed(() =>
  (summary.value.attention_items || []).filter((item) => !String(item.route || '').includes('/delay-requests'))
)

const quickActions = computed(() => {
  const source = (summary.value.quick_actions || []).filter((item) => String(item.route || '').startsWith('/admin/tasks'))
  if (source.length > 0) {
    return source
  }
  return [
    {
      title: '查看任务列表',
      description: '进入任务表格，集中查看当前全部任务。',
      route: '/admin/tasks',
      action_label: '进入任务',
    },
    {
      title: '新建任务',
      description: '创建主任务、负责人和子任务。',
      route: '/admin/tasks',
      action_label: '前往创建',
    },
  ]
})

const trendHasData = computed(() =>
  summary.value.task_trend.some((item) => item.created_total || item.completed_total || item.delayed_total)
)

const chartMax = computed(() => {
  const values = summary.value.task_trend.flatMap((item) => [item.created_total, item.completed_total, item.delayed_total])
  return Math.max(...values, 1)
})

const chartSeries = computed(() => {
  const spacing = 640 / Math.max(summary.value.task_trend.length - 1, 1)
  return summary.value.task_trend.map((item, index) => ({
    ...item,
    x: 40 + spacing * index,
    createdY: valueToY(item.created_total),
    completedY: valueToY(item.completed_total),
    delayedY: valueToY(item.delayed_total),
  }))
})

const createdLinePoints = computed(() => chartSeries.value.map((item) => `${item.x},${item.createdY}`).join(' '))
const completedLinePoints = computed(() => chartSeries.value.map((item) => `${item.x},${item.completedY}`).join(' '))
const delayedLinePoints = computed(() => chartSeries.value.map((item) => `${item.x},${item.delayedY}`).join(' '))
const chartLabels = computed(() => chartSeries.value.map((item) => ({ label: item.label, x: item.x })))
const chartGridLines = [28, 76, 124, 172]

function valueToY(value) {
  const ratio = value / Math.max(chartMax.value, 1)
  return 180 - ratio * 140
}

function toPercent(value, total) {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

function toneClass(tone) {
  if (tone === 'success') return 'status-tone status-tone-success'
  if (tone === 'warning') return 'status-tone status-tone-warning'
  if (tone === 'danger') return 'status-tone status-tone-danger'
  if (tone === 'primary') return 'status-tone status-tone-primary'
  return 'status-tone status-tone-neutral'
}

function goCreateTask() {
  router.push('/admin/tasks')
}

onMounted(async () => {
  const { data } = await http.get('/dashboard/summary')
  summary.value = data
})
</script>

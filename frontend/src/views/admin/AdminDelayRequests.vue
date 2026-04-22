<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">延期审批</div>
        <h1 class="workspace-title">延期审批工作台</h1>
        <p class="workspace-subtitle">按申请卡片集中处理延期审批，支持直接录入新截止时间和审批意见。</p>
      </div>
      <div class="toolbar">
        <button class="button secondary" @click="loadRequests">刷新数据</button>
        <button class="button secondary" @click="exportList">导出清单</button>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">待审批申请</span>
        <strong>{{ pendingRequests.length }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">等待超 48 小时</span>
        <strong>{{ urgentPendingCount }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">平均等待时长</span>
        <strong>{{ averageWaitHours }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">已处理总数</span>
        <strong>{{ processedRequests.length }}</strong>
      </div>
    </div>

    <div class="panel section-block">
      <div class="section-head">
        <div>
          <h2>待审批申请</h2>
          <p>优先处理等待时间较长和新截止时间临近的申请。</p>
        </div>
      </div>

      <div v-if="pendingRequests.length === 0" class="empty-state approval-empty">
        <h3>当前没有待审批申请</h3>
        <p>所有延期申请都已处理完成。</p>
      </div>

      <article
        v-for="item in pendingRequests"
        :key="item.id"
        class="approval-card"
      >
        <div class="approval-avatar">
          {{ applicantInitial(item.applicant_name) }}
        </div>

        <div class="approval-main">
          <div class="approval-topline">
            <div>
              <div class="approval-user">{{ item.applicant_name }}</div>
              <div class="subtle-text">{{ item.applicant_email || '未配置邮箱' }}</div>
            </div>
            <span class="status-tone status-tone-warning">PENDING</span>
          </div>

          <h3>{{ item.task_title }}</h3>
          <div class="approval-meta-grid">
            <div class="info-cell">
              <span class="info-label">任务优先级</span>
              <strong :class="resolvePriorityMeta(item.task_priority).tone">
                {{ resolvePriorityMeta(item.task_priority).label }}
              </strong>
            </div>
            <div class="info-cell">
              <span class="info-label">任务开始</span>
              <strong>{{ formatDateTime(item.task_start_at) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">原截止时间</span>
              <strong>{{ formatDateTime(item.original_deadline) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">申请截止时间</span>
              <strong>{{ formatDateTime(item.proposed_deadline) }}</strong>
            </div>
          </div>

          <div class="approval-reason">
            <span class="info-label">申请原因</span>
            <p>{{ item.apply_reason }}</p>
          </div>
        </div>

        <div class="approval-action">
          <label>确认延期到</label>
          <input
            v-model="reviewForms[item.id].approved_deadline"
            type="datetime-local"
          />
          <label>审批备注</label>
          <textarea
            v-model="reviewForms[item.id].remark"
            rows="4"
            placeholder="请输入审批意见或驳回原因"
          />
          <div class="toolbar approval-action-buttons">
            <button @click="approve(item)">同意延期</button>
            <button class="button danger" @click="reject(item)">执行驳回</button>
          </div>
        </div>
      </article>
    </div>

    <div class="panel section-block">
      <div class="section-head">
        <div>
          <h2>已处理记录</h2>
          <p>保留最近处理过的延期申请，方便复盘。</p>
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>任务</th>
            <th>申请人</th>
            <th>原截止时间</th>
            <th>审批结果</th>
            <th>审批备注</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="processedRequests.length === 0">
            <td colspan="5">当前没有已处理记录。</td>
          </tr>
          <tr v-for="item in processedRequests" :key="`done-${item.id}`">
            <td>{{ item.task_title }}</td>
            <td>{{ item.applicant_name }}</td>
            <td>{{ formatDateTime(item.original_deadline) }}</td>
            <td>{{ item.approval_status_text }}</td>
            <td>{{ item.approve_remark || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import http from '../../api/http'
import { resolvePriorityMeta } from '../../constants/taskUi'
import { formatDateTime, toBackendDateTime, toDateTimeLocal } from '../../utils/format'

const requests = ref([])
const reviewForms = reactive({})

const pendingRequests = computed(() =>
  requests.value.filter((item) => item.approval_status === 'PENDING')
)

const processedRequests = computed(() =>
  requests.value.filter((item) => item.approval_status !== 'PENDING')
)

const urgentPendingCount = computed(() =>
  pendingRequests.value.filter((item) => {
    if (!item.created_at) return false
    return Date.now() - new Date(item.created_at).getTime() > 48 * 3600 * 1000
  }).length
)

const averageWaitHours = computed(() => {
  if (pendingRequests.value.length === 0) return '0h'
  const total = pendingRequests.value.reduce((sum, item) => {
    if (!item.created_at) return sum
    return sum + (Date.now() - new Date(item.created_at).getTime()) / 3600000
  }, 0)
  return `${(total / pendingRequests.value.length).toFixed(1)}h`
})

function applicantInitial(name) {
  return (name || '成员').slice(0, 2)
}

function ensureForm(item) {
  if (!reviewForms[item.id]) {
    reviewForms[item.id] = {
      approved_deadline: toDateTimeLocal(item.proposed_deadline),
      remark: item.approve_remark || '',
    }
  }
}

async function loadRequests() {
  const { data } = await http.get('/delay-requests/pending')
  requests.value = data
  requests.value.forEach(ensureForm)
}

async function approve(item) {
  const form = reviewForms[item.id]
  const approvedDeadlineValue = toBackendDateTime(form.approved_deadline)
  if (!approvedDeadlineValue) {
    window.alert('请先填写有效的新截止时间')
    return
  }
  try {
    await http.post(`/delay-requests/${item.id}/approve`, {
      action: 'APPROVE',
      request_id: `web-${item.id}-${Date.now()}`,
      version: item.version,
      remark: form.remark || '',
      approved_deadline: approvedDeadlineValue,
    })
    await loadRequests()
  } catch (error) {
    window.alert(error.response?.data?.detail || '审批失败')
  }
}

async function reject(item) {
  const form = reviewForms[item.id]
  try {
    await http.post(`/delay-requests/${item.id}/approve`, {
      action: 'REJECT',
      request_id: `web-${item.id}-${Date.now()}`,
      version: item.version,
      remark: form.remark || '',
      approved_deadline: null,
    })
    await loadRequests()
  } catch (error) {
    window.alert(error.response?.data?.detail || '审批失败')
  }
}

function exportList() {
  const header = ['任务', '申请人', '原截止时间', '申请截止时间', '状态', '备注']
  const rows = requests.value.map((item) => [
    item.task_title,
    item.applicant_name,
    formatDateTime(item.original_deadline),
    formatDateTime(item.proposed_deadline),
    item.approval_status_text,
    item.approve_remark || '',
  ])
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'delay-requests.csv'
  link.click()
  window.URL.revokeObjectURL(url)
}

onMounted(loadRequests)
</script>

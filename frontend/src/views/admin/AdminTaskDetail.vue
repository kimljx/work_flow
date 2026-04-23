<template>
  <section v-if="task" class="page">
    <div class="panel task-detail-header">
      <div class="task-detail-header-main">
        <div class="task-detail-title-row">
          <span class="task-detail-id-chip">TASK-{{ task.id }}</span>
          <span :class="statusMeta.tone">{{ statusMeta.text }}</span>
          <span :class="priorityMeta.tone">{{ task.priority_text }}优先级</span>
        </div>
        <h1 class="task-detail-title">{{ task.title }}</h1>
        <p class="task-detail-summary">{{ task.content || '暂无任务说明' }}</p>

        <div class="task-progress-board">
          <div class="task-progress-head">
            <div>
              <span class="metric-label">任务进度</span>
              <strong>{{ progressSummary.label }}</strong>
            </div>
            <span class="task-progress-percent">{{ progressSummary.percent }}%</span>
          </div>
          <div class="task-progress-bar">
            <span :style="progressStyle(progressSummary.percent)"></span>
          </div>
          <div class="task-progress-foot">
            <span>{{ progressSummary.hint }}</span>
            <span>{{ scheduleSummary.deadlineLabel }}</span>
          </div>
        </div>
      </div>

      <div class="task-detail-header-side">
        <div class="task-detail-meta-card">
          <div class="task-detail-meta-row">
            <span>负责人</span>
            <strong>{{ ownerMember?.name || task.owner_name || '-' }}</strong>
          </div>
          <div class="task-detail-meta-row">
            <span>任务创建人</span>
            <strong>{{ task.creator_name || '-' }}</strong>
          </div>
          <div class="task-detail-meta-row">
            <span>开始时间</span>
            <strong>{{ formatDateTime(task.start_at) }}</strong>
          </div>
          <div class="task-detail-meta-row">
            <span>结束时间</span>
            <strong>{{ formatDateTime(task.end_at) }}</strong>
          </div>
          <div class="task-detail-meta-row">
            <span>到期提醒</span>
            <strong>{{ dueRemindText }}</strong>
          </div>
          <div class="task-detail-meta-row">
            <span>创建时间</span>
            <strong>{{ formatDateTime(task.created_at) }}</strong>
          </div>
          <div class="task-member-chip-row">
            <span
              v-for="member in task.members"
              :key="member.user_id"
              class="status-tone status-tone-soft"
            >
              {{ member.name }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="task-detail-metric-grid">
      <div class="task-detail-metric-card">
        <span class="metric-label">计划时长</span>
        <strong>{{ formatDurationDays(task.planned_minutes) }}</strong>
        <span class="subtle-text">按任务起止时间折算</span>
      </div>
      <div class="task-detail-metric-card">
        <span class="metric-label">实际时长</span>
        <strong>{{ formatDurationDays(task.actual_minutes) }}</strong>
        <span class="subtle-text">按当前累计记录折算</span>
      </div>
      <div class="task-detail-metric-card">
        <span class="metric-label">子任务完成</span>
        <strong>{{ subtaskDoneCount }}/{{ task.subtask_count || 0 }}</strong>
        <span class="subtle-text">已完成 / 全部子任务</span>
      </div>
      <div class="task-detail-metric-card">
        <span class="metric-label">通知送达</span>
        <strong>{{ deliverySummary.label }}</strong>
        <span class="subtle-text">{{ deliverySummary.hint }}</span>
      </div>
    </div>

    <div class="panel task-detail-action-panel">
      <div class="section-head">
        <div>
          <h2>任务操作</h2>
          <p>把返回、编辑、提醒和状态流转拆开布局，减少按钮堆叠造成的拥挤感。</p>
        </div>
      </div>
      <div class="task-detail-action-grid">
        <div class="task-detail-action-block">
          <span class="info-label">快捷操作</span>
          <div class="toolbar">
            <router-link class="button secondary" :to="backTarget">返回上页</router-link>
            <router-link
              class="button secondary"
              :to="{ path: `/admin/tasks/${task.id}/edit`, query: { from: route.fullPath } }"
            >
              编辑任务
            </router-link>
            <button class="button secondary" :disabled="actionLoading" @click="remindTask">
              手动提醒
            </button>
          </div>
        </div>

        <div class="task-detail-action-block">
          <span class="info-label">状态流转</span>
          <div class="task-detail-status-grid">
            <select v-model="statusForm.main_status" :disabled="actionLoading">
              <option value="not_started">未开始</option>
              <option value="in_progress">进行中</option>
              <option value="done">已完成</option>
              <option value="canceled">已取消</option>
            </select>
            <input v-model="statusForm.remark" :disabled="actionLoading" placeholder="填写状态备注" />
            <button :disabled="actionLoading" @click="changeStatus">更新状态</button>
          </div>
        </div>

        <div class="task-detail-action-block">
          <span class="info-label">安全操作</span>
          <div class="toolbar">
            <button
              v-if="!task.state_locked"
              class="button secondary"
              :disabled="actionLoading"
              @click="toggleLock(true)"
            >
              锁定状态
            </button>
            <button
              v-else
              class="button secondary"
              :disabled="actionLoading"
              @click="toggleLock(false)"
            >
              解除锁定
            </button>
            <button class="button danger" :disabled="actionLoading" @click="removeTask">删除任务</button>
          </div>
        </div>
      </div>
    </div>

    <div class="task-detail-board">
      <div class="task-detail-primary">
        <div class="panel">
          <div class="section-head">
            <div>
              <h2>任务说明与概览</h2>
              <p>把核心状态、时间与通知概况集中展示，避免上半区留下无效空白。</p>
            </div>
          </div>
          <div class="task-overview-grid">
            <div class="info-cell">
              <span class="info-label">当前状态</span>
              <strong>{{ task.status_text }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">优先级</span>
              <strong>{{ task.priority_text }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">时间进度</span>
              <strong>{{ scheduleSummary.percent }}%</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">剩余情况</span>
              <strong>{{ scheduleSummary.deadlineLabel }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">通知记录</span>
              <strong>{{ task.notifications.length }} 条</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">延期申请</span>
              <strong>{{ task.delay_requests.length }} 条</strong>
            </div>
          </div>
          <div v-if="task.remark" class="task-remark-card">
            <span class="info-label">任务备注</span>
            <p>{{ task.remark }}</p>
          </div>
        </div>

        <div class="task-detail-work-grid">
          <div class="panel task-milestone-panel">
            <div class="section-head">
              <div>
                <h2>里程碑进度</h2>
                <p>用摘要加节点清单的方式展示阶段安排，减少单薄列表造成的空感。</p>
              </div>
            </div>

            <div class="task-milestone-summary-grid">
              <div class="info-cell">
                <span class="info-label">里程碑总数</span>
                <strong>{{ task.milestones.length }} 个</strong>
              </div>
              <div class="info-cell">
                <span class="info-label">最近节点</span>
                <strong>{{ nextMilestone ? nextMilestone.name : '暂无待执行节点' }}</strong>
                <div class="subtle-text">
                  {{ nextMilestone ? formatDateTime(nextMilestone.planned_at) : '当前任务暂无未来里程碑' }}
                </div>
              </div>
            </div>

            <div v-if="task.milestones.length === 0" class="muted-block">
              当前没有里程碑，后续可以在编辑任务时补充阶段节点。
            </div>
            <div v-else class="task-board-list">
              <article v-for="milestone in task.milestones" :key="milestone.id" class="task-board-item">
                <div class="task-milestone-main">
                  <span class="task-detail-id-chip task-milestone-chip">节点</span>
                  <div>
                    <strong>{{ milestone.name }}</strong>
                    <div class="subtle-text">
                      提前 {{ milestone.remind_offsets.length ? milestone.remind_offsets.join(' / ') : '无' }} 天提醒
                    </div>
                  </div>
                </div>
                <div class="task-board-item-side">
                  <strong>{{ formatDateTime(milestone.planned_at) }}</strong>
                  <div class="subtle-text">{{ milestoneStatusText(milestone.planned_at) }}</div>
                </div>
              </article>
            </div>
          </div>

          <div class="panel task-subtask-panel">
            <div class="section-head">
              <div>
                <h2>子任务列表</h2>
                <p>突出执行人、状态和内容，让高频信息更靠前。</p>
              </div>
            </div>
            <div class="subtask-summary-row">
              <span class="status-tone status-tone-neutral">待开始 {{ subtaskCountByStatus('pending') }}</span>
              <span class="status-tone status-tone-primary">进行中 {{ subtaskCountByStatus('in_progress') }}</span>
              <span class="status-tone status-tone-success">已完成 {{ subtaskCountByStatus('done') }}</span>
              <span class="status-tone status-tone-muted">已取消 {{ subtaskCountByStatus('canceled') }}</span>
            </div>
            <div v-if="task.subtasks.length === 0" class="muted-block">当前没有子任务。</div>
            <div v-else class="section-block">
              <article v-for="item in task.subtasks" :key="item.id" class="subtask-card task-detail-subtask-card">
                <div class="task-subtask-topline">
                  <div>
                    <strong>{{ item.title }}</strong>
                    <div class="subtle-text">
                      {{ item.assignee_name || '-' }} / {{ item.assignee_email || '未配置邮箱' }}
                    </div>
                  </div>
                  <span :class="resolveSubtaskStatusMeta(item.status, item.status_text).tone">
                    {{ resolveSubtaskStatusMeta(item.status, item.status_text).label }}
                  </span>
                </div>
                <div>{{ item.content || '暂无说明' }}</div>
              </article>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="section-head">
            <div>
              <h2>通知记录</h2>
              <p>保持和通知模块一致，可直接查看每条通知的送达详情。</p>
            </div>
          </div>
          <table class="table">
            <thead>
              <tr>
                <th>渠道</th>
                <th>类型</th>
                <th>状态</th>
                <th>送达</th>
                <th>已读</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="task.notifications.length === 0">
                <td colspan="7">当前没有通知记录。</td>
              </tr>
              <tr v-for="item in task.notifications" :key="item.id">
                <td>{{ item.channel_text }}</td>
                <td>{{ item.notify_type_text }}</td>
                <td>{{ item.status_text }}</td>
                <td>{{ item.delivered_count }}/{{ item.recipient_total }}</td>
                <td>{{ item.read_count }}</td>
                <td>{{ formatDateTime(item.created_at) }}</td>
                <td>
                  <router-link
                    class="button secondary small"
                    :to="{ path: `/admin/notifications/${item.id}`, query: { from: route.fullPath } }"
                  >
                    查看详情
                  </router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="panel">
          <div class="section-head">
            <div>
              <h2>延期记录</h2>
              <p>审批结果、渠道、审批时间和备注统一放进同一张卡片里查看。</p>
            </div>
          </div>
          <div v-if="task.delay_requests.length === 0" class="empty-state approval-empty">
            <h3>当前没有延期申请记录</h3>
            <p>成员提交延期申请后，这里会同步展示审批结果和处理信息。</p>
          </div>
          <div v-else class="section-block">
            <article v-for="item in task.delay_requests" :key="item.id" class="approval-card task-delay-card">
              <div class="approval-avatar">{{ applicantInitial(item.applicant_name) }}</div>
              <div class="approval-main">
                <div class="approval-topline">
                  <div>
                    <div class="approval-user">{{ item.applicant_name || '未知申请人' }}</div>
                    <div class="subtle-text">申请编号 #{{ item.id }}</div>
                  </div>
                  <span :class="delayStatusTone(item.approval_status)">{{ item.approval_status_text }}</span>
                </div>
                <div class="approval-meta-grid">
                  <div class="info-cell">
                    <span class="info-label">原截止时间</span>
                    <strong>{{ formatDateTime(item.original_deadline) }}</strong>
                  </div>
                  <div class="info-cell">
                    <span class="info-label">申请截止时间</span>
                    <strong>{{ formatDateTime(item.proposed_deadline) }}</strong>
                  </div>
                  <div class="info-cell">
                    <span class="info-label">最终截止时间</span>
                    <strong>{{ formatDateTime(item.approved_deadline || item.proposed_deadline) }}</strong>
                  </div>
                </div>
                <div class="approval-reason">
                  <span class="info-label">申请原因</span>
                  <p>{{ item.apply_reason || '未填写申请原因' }}</p>
                </div>
              </div>
              <div class="approval-action task-delay-summary">
                <label>审批人</label>
                <div>{{ item.approver_name || '待处理' }}</div>
                <label>审批渠道</label>
                <div>{{ decisionChannelText(item.decided_by_channel) }}</div>
                <label>审批时间</label>
                <div>{{ formatDateTime(item.decided_at) }}</div>
                <label>审批备注</label>
                <div class="task-delay-remark">{{ item.approve_remark || '暂无审批备注' }}</div>
                <div class="toolbar approval-action-buttons">
                  <router-link
                    class="button secondary small"
                    :to="{ path: '/admin/delay-requests', query: { from: route.fullPath } }"
                  >
                    前往审批工作台
                  </router-link>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>

      <div class="task-detail-secondary">
        <div class="panel">
          <div class="section-head">
            <div>
              <h2>邮件 / 即时消息预览</h2>
              <p>直接查看指定成员在指定渠道下最终会收到的主题和正文。</p>
            </div>
            <button class="button secondary small" :disabled="previewLoading" @click="loadPreview">刷新预览</button>
          </div>
          <div class="task-preview-control-grid">
            <select v-model="previewForm.channel" :disabled="previewLoading" @change="loadPreview">
              <option v-for="item in channelOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <select v-model="previewForm.notify_type" :disabled="previewLoading" @change="loadPreview">
              <option v-for="item in notifyTypeOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <select v-model="previewForm.recipient_user_id" :disabled="previewLoading" @change="loadPreview">
              <option v-for="member in previewMembers" :key="member.value ?? 'all'" :value="member.value">
                {{ member.label }}
              </option>
            </select>
          </div>

          <div v-if="previewLoading" class="muted-block">正在加载通知预览...</div>
          <div v-else-if="preview" class="task-preview-shell">
            <div class="task-preview-meta-grid">
              <div class="info-cell">
                <span class="info-label">模板</span>
                <strong>{{ preview.template_name }}</strong>
                <div class="subtle-text">版本 {{ preview.template_version || '-' }}</div>
              </div>
              <div class="info-cell">
                <span class="info-label">接收人</span>
                <strong>{{ preview.recipient_name || '整任务预览' }}</strong>
                <div class="subtle-text">{{ preview.recipient_email || '用于查看完整正文' }}</div>
              </div>
              <div class="info-cell">
                <span class="info-label">关键信息</span>
                <strong>{{ preview.context.owner_name || '-' }}</strong>
                <div class="subtle-text">负责人 / {{ preview.context.creator_name || '-' }}</div>
              </div>
            </div>
            <div class="task-preview-context-card">
              <span class="info-label">子任务摘要</span>
              <div class="subtle-text">{{ preview.context.subtask_summary || '暂无子任务' }}</div>
            </div>
            <div>
              <span class="info-label">主题</span>
              <pre class="detail-pre detail-pre-subtle">{{ preview.subject || '当前模板未设置主题' }}</pre>
            </div>
            <div>
              <span class="info-label">正文</span>
              <pre class="detail-pre dark">{{ preview.content || '当前模板未生成正文' }}</pre>
            </div>
          </div>
        </div>

        <div class="panel">
          <h2>状态时间线</h2>
          <ul class="timeline">
            <li v-for="item in task.events" :key="item.id">
              <strong>{{ item.to_status_text }}</strong>
              <span>{{ formatDateTime(item.created_at) }}</span>
              <div>{{ item.remark || '无备注' }}</div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { resolvePriorityMeta, resolveSubtaskStatusMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatDateTime, formatDurationDays } from '../../utils/format'

const route = useRoute()
const router = useRouter()

const task = ref(null)
const preview = ref(null)
const actionLoading = ref(false)
const previewLoading = ref(false)

const statusForm = reactive({
  main_status: 'not_started',
  remark: '',
})

const previewForm = reactive({
  channel: 'email',
  notify_type: 'task_created',
  recipient_user_id: null,
})

const backTarget = route.query.from || '/admin/tasks'

const channelOptions = [
  { value: 'email', label: '邮件' },
  { value: 'qax', label: '即时消息' },
]

const notifyTypeOptions = [
  { value: 'task_created', label: '任务创建' },
  { value: 'manual_remind', label: '手动提醒' },
  { value: 'due_remind', label: '到期提醒' },
]

const statusMeta = computed(() => resolveTaskStatusTone(task.value || null))
const priorityMeta = computed(() => resolvePriorityMeta(task.value?.priority))
const ownerMember = computed(() => task.value?.members.find((item) => item.member_role === 'owner') || null)
const subtaskDoneCount = computed(() => task.value?.subtasks.filter((item) => item.status === 'done').length || 0)

const previewMembers = computed(() => {
  const members = task.value?.members || []
  return [
    { value: null, label: '整任务预览' },
    ...members.map((member) => ({
      value: member.user_id,
      label: `${member.name} / ${member.member_role_text}`,
    })),
  ]
})

const deliverySummary = computed(() => {
  if (!task.value?.notification_total) {
    return { label: '暂无', hint: '当前还没有送达对象' }
  }
  return {
    label: `${task.value.delivered_count}/${task.value.notification_total}`,
    hint: `送达率 ${Math.round((task.value.delivered_count / task.value.notification_total) * 100)}%`,
  }
})

// 详情页要让里程碑区更饱满，所以这里优先挑出最接近当前时间的节点做摘要。
const nextMilestone = computed(() => {
  if (!task.value?.milestones?.length) return null
  const now = Date.now()
  const ordered = [...task.value.milestones].sort(
    (left, right) => new Date(left.planned_at).getTime() - new Date(right.planned_at).getTime()
  )
  return ordered.find((item) => new Date(item.planned_at).getTime() >= now) || ordered[ordered.length - 1]
})

const progressSummary = computed(() => {
  if (!task.value) {
    return { percent: 0, label: '暂无任务数据', hint: '等待任务加载' }
  }
  if (task.value.subtask_count > 0) {
    const done = subtaskDoneCount.value
    const total = task.value.subtask_count
    const percent = Math.round((done / total) * 100)
    return {
      percent,
      label: `${done}/${total} 个子任务已完成`,
      hint: total === done ? '当前拆解任务已全部完成。' : '子任务完成度优先反映实际执行进展。',
    }
  }
  const percent = schedulePercent(task.value.start_at, task.value.end_at, task.value.main_status)
  return {
    percent,
    label: `${percent}% 时间进度`,
    hint: '当前没有子任务时，使用主任务时间进度估算。',
  }
})

const scheduleSummary = computed(() => {
  if (!task.value) {
    return { percent: 0, deadlineLabel: '-' }
  }
  return {
    percent: schedulePercent(task.value.start_at, task.value.end_at, task.value.main_status),
    deadlineLabel: deadlineText(task.value.end_at, task.value.main_status),
  }
})

const dueRemindText = computed(() => {
  if (!task.value || task.value.due_remind_days <= 0) return '未开启'
  return `提前 ${task.value.due_remind_days} 天`
})

function applicantInitial(name) {
  return (name || '成员').slice(0, 2)
}

function delayStatusTone(status) {
  if (status === 'APPROVED') return 'status-tone status-tone-success'
  if (status === 'REJECTED') return 'status-tone status-tone-danger'
  return 'status-tone status-tone-warning'
}

function decisionChannelText(channel) {
  if (channel === 'web') return '系统审批'
  if (channel === 'mail') return '邮件审批'
  return '待处理'
}

function subtaskCountByStatus(status) {
  return task.value?.subtasks.filter((item) => item.status === status).length || 0
}

function milestoneStatusText(plannedAt) {
  if (!plannedAt) return '未设置时间'
  return new Date(plannedAt).getTime() < Date.now() ? '已进入当前节点' : '待执行节点'
}

function progressStyle(percent) {
  return { width: `${Math.max(0, Math.min(percent, 100))}%` }
}

function schedulePercent(startAt, endAt, status) {
  if (!startAt || !endAt) return 0
  if (status === 'done') return 100
  const start = new Date(startAt)
  const end = new Date(endAt)
  const total = end.getTime() - start.getTime()
  const now = Date.now()
  if (!Number.isFinite(total) || total <= 0) return 0
  if (now <= start.getTime()) return 0
  if (now >= end.getTime()) return 100
  return Math.round(((now - start.getTime()) / total) * 100)
}

function deadlineText(endAt, status) {
  if (!endAt) return '未设置'
  if (status === 'done') return '已按当前状态完成'
  const end = new Date(endAt)
  const diffMs = end.getTime() - Date.now()
  const dayMs = 24 * 60 * 60 * 1000
  if (diffMs < 0) {
    return `已逾期 ${Math.ceil(Math.abs(diffMs) / dayMs)} 天`
  }
  return `剩余 ${Math.ceil(diffMs / dayMs)} 天`
}

async function loadPreview() {
  if (!task.value) return
  previewLoading.value = true
  try {
    const params = {
      channel: previewForm.channel,
      notify_type: previewForm.notify_type,
    }
    if (previewForm.recipient_user_id) {
      params.recipient_user_id = previewForm.recipient_user_id
    }
    const { data } = await http.get(`/tasks/${route.params.id}/notification-preview`, { params })
    preview.value = data
  } finally {
    previewLoading.value = false
  }
}

async function loadTask() {
  const { data } = await http.get(`/tasks/${route.params.id}`)
  task.value = data
  statusForm.main_status = data.main_status
  await loadPreview()
}

async function remindTask() {
  if (!window.confirm('确认要发送手动提醒吗？')) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/remind`)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function changeStatus() {
  if (!window.confirm('确认要修改任务状态吗？本操作将写入审计日志。')) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/status`, statusForm)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function toggleLock(shouldLock) {
  if (!window.confirm(`确认要${shouldLock ? '锁定' : '解除锁定'}任务状态吗？`)) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/${shouldLock ? 'lock' : 'unlock'}`)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function removeTask() {
  if (!window.confirm('确认删除该任务吗？删除后仍会保留审计日志。')) return
  actionLoading.value = true
  try {
    await http.delete(`/tasks/${route.params.id}`)
    router.push(backTarget)
  } finally {
    actionLoading.value = false
  }
}

onMounted(loadTask)
</script>

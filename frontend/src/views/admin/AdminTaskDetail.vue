<template>
  <section v-if="task" class="page">
    <div class="panel task-detail-hero">
      <div class="task-detail-topbar">
        <div class="task-detail-topbar-info">
          <span class="task-detail-id-chip">TASK-{{ task.id }}</span>
          <span :class="priorityMeta.tone">{{ task.priority_text }}优先级</span>
          <span :class="statusMeta.tone">{{ statusMeta.text }}</span>
        </div>
        <div class="toolbar task-detail-top-actions">
          <router-link class="button secondary" :to="backTarget">返回上页</router-link>
          <router-link
            class="button secondary"
            :to="{ path: `/admin/tasks/${task.id}/edit`, query: { from: route.fullPath } }"
          >
            编辑任务
          </router-link>
          <button class="button secondary" :disabled="actionLoading" @click="remindTask">手动提醒</button>
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

      <div class="task-detail-hero-grid">
        <div class="task-detail-hero-main">
          <div class="task-detail-heading-block">
            <h1 class="task-detail-title">{{ task.title }}</h1>
            <p class="task-detail-summary">{{ task.content || '暂无任务说明' }}</p>
          </div>

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

          <div class="task-detail-status-card">
            <div class="section-head compact">
              <div>
                <h2>状态操作</h2>
                <p>把状态流转保留在首屏，处理任务时不需要来回滚动查找。</p>
              </div>
            </div>
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
        </div>

        <div class="task-detail-hero-side">
          <div class="task-detail-meta-grid">
            <div class="info-cell">
              <span class="info-label">负责人</span>
              <strong>{{ ownerMember?.name || task.owner_name || '-' }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">任务创建人</span>
              <strong>{{ task.creator_name || '-' }}</strong>
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
              <span class="info-label">到期提醒</span>
              <strong>{{ dueRemindText }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">创建时间</span>
              <strong>{{ formatDateTime(task.created_at) }}</strong>
            </div>
          </div>
          <div class="task-member-chip-card">
            <span class="info-label">参与成员</span>
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

    <div class="task-detail-board">
      <div class="task-detail-primary">
        <div class="panel">
          <div class="section-head">
            <div>
              <h2>任务说明与概览</h2>
              <p>把核心状态、时间与通知概况集中展示，减少重复信息卡的占位。</p>
            </div>
          </div>
          <div class="task-overview-grid">
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
            <div class="info-cell">
              <span class="info-label">状态锁定</span>
              <strong>{{ task.state_locked ? '已锁定' : '未锁定' }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">参与人数</span>
              <strong>{{ task.members.length }} 人</strong>
            </div>
          </div>
          <div v-if="task.remark" class="task-remark-card">
            <span class="info-label">任务备注</span>
            <p>{{ task.remark }}</p>
          </div>
        </div>

        <div class="panel task-subtask-panel">
          <div class="section-head">
            <div>
              <h2>子任务列表</h2>
              <p>突出执行人、状态和内容，并在需要时支持按单个子任务发起提醒。</p>
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
              <div class="task-inline-actions" v-if="item.status !== 'done'">
                <button class="button secondary small" :disabled="actionLoading" @click="remindSubtask(item)">提醒子任务</button>
              </div>
            </article>
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
                <th>反馈</th>
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
                <td>
                  <div>{{ item.notify_scene_text || item.notify_type_text }}</div>
                  <div class="subtle-text" v-if="item.remind_focus">{{ item.remind_focus }}</div>
                </td>
                <td>{{ item.status_text }}</td>
                <td>{{ item.delivered_count }}/{{ item.recipient_total }}</td>
                <td>{{ item.read_count }} {{ item.feedback_label }}</td>
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
        <div class="panel task-timeline-panel">
          <div class="section-head">
            <div>
              <h2>状态与节奏</h2>
              <p>把里程碑和状态流转收进同一张节奏卡，同时收起原始邮件大段正文，减少干扰。</p>
            </div>
          </div>

          <div class="task-timeline-section">
            <div class="task-timeline-subhead">
              <h3>里程碑节点</h3>
              <span class="subtle-text">共 {{ task.milestones.length }} 个</span>
            </div>
            <div class="task-milestone-summary-grid">
              <div class="info-cell">
                <span class="info-label">最近节点</span>
                <strong>{{ nextMilestone ? nextMilestone.name : '暂无待执行节点' }}</strong>
                <div class="subtle-text">
                  {{ nextMilestone ? formatDateTime(nextMilestone.planned_at) : '当前任务暂无未来里程碑' }}
                </div>
              </div>
              <div class="info-cell">
                <span class="info-label">延期节点</span>
                <strong>{{ delayedMilestoneCount }} 个</strong>
                <div class="subtle-text">节点时间已过且尚未完成的里程碑会自动标记为延期。</div>
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
                    <div class="task-inline-actions" v-if="milestone.status !== 'done'">
                      <button class="button secondary small" :disabled="actionLoading" @click="remindMilestone(milestone)">提醒节点</button>
                    </div>
                  </div>
                </div>
                <div class="task-board-item-side">
                  <strong>{{ formatDateTime(milestone.planned_at) }}</strong>
                  <span :class="milestoneMeta(milestone).tone">{{ milestoneMeta(milestone).label }}</span>
                </div>
              </article>
            </div>
          </div>

          <div class="task-timeline-divider"></div>

          <div class="task-timeline-section">
            <div class="task-timeline-subhead">
              <h3>状态时间线</h3>
              <span class="subtle-text">共 {{ timelineItems.length }} 条</span>
            </div>
            <div v-if="timelineItems.length === 0" class="muted-block">当前还没有状态变更记录。</div>
            <ul v-else class="timeline task-status-timeline task-status-timeline-cards">
              <li v-for="item in timelineItems" :key="item.id" class="task-status-timeline-item">
                <div class="task-status-timeline-top">
                  <strong>{{ item.title }}</strong>
                  <span>{{ formatDateTime(item.created_at) }}</span>
                </div>
                <div class="task-status-timeline-meta">
                  <span :class="item.sourceTone">{{ item.sourceText }}</span>
                  <span class="subtle-text">{{ item.summaryLabel }}</span>
                </div>
                <div class="task-status-timeline-body">{{ item.summary }}</div>
                <div v-if="item.hasOriginalMail" class="task-inline-actions">
                  <button class="button secondary small" @click="openOriginalMail(item)">查看原始邮件</button>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div v-if="originalMailModal.visible" class="modal-mask" @click.self="closeOriginalMail">
      <div class="modal-card mail-original-modal">
        <div class="section-head">
          <div>
            <h2>原始邮件</h2>
            <p>这里展示状态流转时解析出的完整原始邮件正文，默认隐藏以减少时间线干扰。</p>
          </div>
          <button class="button secondary small" @click="closeOriginalMail">关闭</button>
        </div>
        <pre class="detail-pre mail-original-pre">{{ originalMailModal.content || '当前没有可展示的原始邮件正文' }}</pre>
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
const actionLoading = ref(false)
const originalMailModal = reactive({
  visible: false,
  content: '',
})

const statusForm = reactive({
  main_status: 'not_started',
  remark: '',
})

const backTarget = route.query.from || '/admin/tasks'

const statusMeta = computed(() => resolveTaskStatusTone(task.value || null))
const priorityMeta = computed(() => resolvePriorityMeta(task.value?.priority))
const ownerMember = computed(() => task.value?.members.find((item) => item.member_role === 'owner') || null)
const subtaskDoneCount = computed(() => task.value?.subtasks.filter((item) => item.status === 'done').length || 0)
const delayedMilestoneCount = computed(() => task.value?.milestones.filter((item) => milestoneMeta(item).code === 'delayed').length || 0)

const deliverySummary = computed(() => {
  if (!task.value?.notification_total) {
    return { label: '暂无', hint: '当前还没有送达对象' }
  }
  return {
    label: `${task.value.delivered_count}/${task.value.notification_total}`,
    hint: `送达率 ${Math.round((task.value.delivered_count / task.value.notification_total) * 100)}%`,
  }
})

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

const timelineItems = computed(() => {
  return (task.value?.events || []).map((item) => {
    const parsed = splitTimelineRemark(item.remark || '')
    return {
      id: item.id,
      title: item.to_status_text || '状态更新',
      created_at: item.created_at,
      sourceText: sourceText(item.source),
      sourceTone: sourceTone(item.source),
      summaryLabel: parsed.hasOriginalMail ? '已隐藏原始邮件正文' : '状态备注',
      summary: parsed.summary || '无备注',
      hasOriginalMail: parsed.hasOriginalMail,
      rawMail: parsed.rawMail,
    }
  })
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

function sourceText(source) {
  if (source === 'mail') return '邮件回执'
  if (source === 'import') return '导入初始化'
  return '系统操作'
}

function sourceTone(source) {
  if (source === 'mail') return 'status-tone status-tone-primary'
  if (source === 'import') return 'status-tone status-tone-soft'
  return 'status-tone status-tone-neutral'
}

function subtaskCountByStatus(status) {
  return task.value?.subtasks.filter((item) => item.status === status).length || 0
}

function milestoneMeta(milestone) {
  if (!milestone?.planned_at) {
    return {
      code: 'empty',
      label: '未设置时间',
      tone: 'status-tone status-tone-muted',
    }
  }
  if (milestone.status === 'done') {
    return {
      code: 'done',
      label: '已完成节点',
      tone: 'status-tone status-tone-success',
    }
  }
  if (new Date(milestone.planned_at).getTime() < Date.now()) {
    return {
      code: 'delayed',
      label: '已延期',
      tone: 'status-tone status-tone-danger',
    }
  }
  return {
    code: 'pending',
    label: '待执行节点',
    tone: 'status-tone status-tone-neutral',
  }
}

function decodeMailText(content) {
  if (!content) return ''
  const container = document.createElement('textarea')
  container.innerHTML = content
  return container.value.replace(/\u00a0/g, ' ')
}

function splitTimelineRemark(remark) {
  const normalized = decodeMailText(remark).replace(/\r\n/g, '\n').trim()
  if (!normalized) {
    return { summary: '', rawMail: '', hasOriginalMail: false }
  }
  const marker = '---原始邮件---'
  const markerIndex = normalized.indexOf(marker)
  if (markerIndex === -1) {
    return { summary: normalized, rawMail: '', hasOriginalMail: false }
  }
  const summary = normalized.slice(0, markerIndex).trim().replace(/\s*---\s*$/, '')
  const rawMail = normalized.slice(markerIndex + marker.length).trim()
  return { summary: summary || '本次状态变更来自邮件回执。', rawMail, hasOriginalMail: Boolean(rawMail) }
}

function openOriginalMail(item) {
  originalMailModal.visible = true
  originalMailModal.content = item.rawMail || ''
}

function closeOriginalMail() {
  originalMailModal.visible = false
  originalMailModal.content = ''
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
    return `已延期 ${Math.ceil(Math.abs(diffMs) / dayMs)} 天`
  }
  return `剩余 ${Math.ceil(diffMs / dayMs)} 天`
}

async function loadTask() {
  const { data } = await http.get(`/tasks/${route.params.id}`)
  task.value = data
  statusForm.main_status = data.main_status
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

async function remindSubtask(item) {
  if (!window.confirm(`确认提醒子任务“${item.title}”的执行人吗？`)) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/subtasks/${item.id}/remind`)
    await loadTask()
  } finally {
    actionLoading.value = false
  }
}

async function remindMilestone(item) {
  if (!window.confirm(`确认提醒里程碑“${item.name}”吗？`)) return
  actionLoading.value = true
  try {
    await http.post(`/tasks/${route.params.id}/milestones/${item.id}/remind`)
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

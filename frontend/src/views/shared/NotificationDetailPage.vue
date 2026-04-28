<template>
  <section class="page" v-if="detail">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">通知详情</div>
        <h1 class="workspace-title">{{ detail.task_title || `通知 #${detail.id}` }}</h1>
        <p class="workspace-subtitle">查看通知正文，以及每位成员的送达、邮件回复或即时消息已读状态。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="backPath">返回列表</router-link>
        <router-link
          v-if="detail.task_id"
          class="button"
          :to="taskPath"
        >
          查看任务
        </router-link>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">通知渠道</span>
        <strong>{{ detail.channel_text }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">提醒场景</span>
        <strong>{{ detail.notify_scene_text || detail.notify_type_text || notifyTypeText(detail.notify_type) }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">当前状态</span>
        <strong>{{ detail.status_text }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">创建时间</span>
        <strong>{{ formatDateTime(detail.created_at) }}</strong>
      </div>
    </div>

    <div class="detail-grid">
      <div class="panel">
        <h2>通知内容</h2>
        <pre class="detail-pre">{{ detail.content_snapshot || '暂无通知内容' }}</pre>
      </div>
      <div class="panel">
        <h2>汇总情况</h2>
        <div class="detail-summary-list">
          <div class="detail-summary-item">
            <span>提醒重点</span>
            <strong>{{ detail.remind_focus || '主任务整体进度跟进' }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>总接收人</span>
            <strong>{{ detail.recipient_total }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>已送达</span>
            <strong>{{ detail.delivered_count }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>{{ detail.feedback_label || '反馈' }}</span>
            <strong>{{ detail.read_count }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>重试次数</span>
            <strong>{{ detail.retry_total }}</strong>
          </div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>成员回执</h2>
          <p>按成员逐条查看送达、邮件回复或即时消息已读情况，以及错误信息。</p>
        </div>
        <div class="filter-chip-group notification-recipient-filters">
          <button
            v-for="item in recipientFilterOptions"
            :key="item.value"
            :class="['button secondary small filter-chip', { active: recipientFilter === item.value }]"
            @click="recipientFilter = item.value"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>成员</th>
            <th>角色</th>
            <th>接收内容</th>
            <th>送达状态</th>
            <th>{{ detail.feedback_label || '反馈' }}状态</th>
            <th>重试次数</th>
            <th>最后错误</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filteredRecipients.length === 0">
            <td colspan="7">当前没有成员回执记录。</td>
          </tr>
          <tr v-for="recipient in filteredRecipients" :key="`${detail.id}-${recipient.user_id}`">
            <td>
              <div>{{ recipient.name || '-' }}</div>
              <div class="subtle-text">{{ recipient.email || '未配置邮箱' }}</div>
            </td>
            <td>{{ recipient.recipient_role_text || recipient.recipient_role }}</td>
            <td>
              <pre class="detail-pre detail-pre-subtle">{{ recipient.content_snapshot || '沿用通知正文' }}</pre>
            </td>
            <td><span class="status-tone status-tone-soft">{{ recipient.delivery_status_text }}</span></td>
            <td><span class="status-tone status-tone-neutral">{{ recipient.read_status_text }}</span></td>
            <td>{{ recipient.retry_count }}</td>
            <td>{{ recipient.last_error || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import http from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatDateTime } from '../../utils/format'

const route = useRoute()
const auth = useAuthStore()
const detail = ref(null)
const recipientFilter = ref('all')

const defaultBackPath = computed(() => (auth.isAdmin ? '/admin/notifications' : '/member/notifications'))
const backPath = computed(() => route.query.from || defaultBackPath.value)
const taskPath = computed(() => {
  if (!detail.value?.task_id) return backPath.value
  return {
    path: auth.isAdmin ? `/admin/tasks/${detail.value.task_id}` : `/member/tasks/${detail.value.task_id}`,
    query: {
      from: route.fullPath,
    },
  }
})

const recipientFilterOptions = computed(() => {
  const recipients = detail.value?.recipients || []
  const pendingFeedbackCount = recipients.filter((item) => item.read_status !== 'read').length
  const deliveryFailedCount = recipients.filter((item) => item.delivery_status !== 'delivered').length
  return [
    { value: 'all', label: `全部 ${recipients.length}` },
    { value: 'pending_feedback', label: `未${detail.value?.feedback_label || '反馈'} ${pendingFeedbackCount}` },
    { value: 'delivery_failed', label: `送达异常 ${deliveryFailedCount}` },
  ]
})

const filteredRecipients = computed(() => {
  const recipients = detail.value?.recipients || []
  if (recipientFilter.value === 'pending_feedback') {
    return recipients.filter((item) => item.read_status !== 'read')
  }
  if (recipientFilter.value === 'delivery_failed') {
    return recipients.filter((item) => item.delivery_status !== 'delivered')
  }
  return recipients
})

async function loadDetail() {
  const { data } = await http.get(`/notifications/${route.params.id}`)
  detail.value = data
  recipientFilter.value = 'all'
}

onMounted(loadDetail)
</script>

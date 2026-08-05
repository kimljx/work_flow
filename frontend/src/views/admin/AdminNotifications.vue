<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">通知模块</div>
        <h1 class="workspace-title">通知中心</h1>
        <p class="workspace-subtitle">按任务查看邮件与即时消息通知，并进入详情页核对成员送达、邮件回复和即时消息已读状态。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" to="/admin/mail-events">查看邮件列表</router-link>
        <button class="button danger" type="button" :disabled="selectedNotificationIds.length === 0" @click="bulkDeleteNotifications">
          批量删除
        </button>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">通知总数</span>
        <strong>{{ notifications.length }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">已送达</span>
        <strong>{{ deliveredTotal }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">成员反馈</span>
        <strong>{{ readTotal }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">失败重试</span>
        <strong>{{ retryTotal }}</strong>
      </div>
    </div>

    <div class="panel filter-shell">
      <div class="filter-grid">
        <input v-model="keyword" placeholder="搜索任务名称" />
        <div class="multi-filter">
          <button class="button secondary small" type="button" @click="channelFilterOpen = !channelFilterOpen">{{ selectedChannelText }}</button>
          <div v-if="channelFilterOpen" class="multi-filter-menu">
            <label class="multi-filter-all">
              <span>全选</span>
              <input type="checkbox" :checked="isAllChannelsSelected" @change="toggleAllChannels" />
            </label>
            <label v-for="item in channelOptions" :key="item.value">
              <span>{{ item.label }}</span>
              <input v-model="channel" type="checkbox" :value="item.value" />
            </label>
          </div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>通知记录列表</h2>
          <p>已选择 {{ selectedNotificationIds.length }} 条通知记录。</p>
        </div>
        <div class="toolbar">
          <button class="button danger" type="button" :disabled="selectedNotificationIds.length === 0" @click="bulkDeleteNotifications">
            删除选中
          </button>
        </div>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th class="selection-cell">
              <input type="checkbox" :checked="isCurrentPageSelected" :disabled="pagedNotifications.length === 0" @change="toggleCurrentPageSelection" />
            </th>
            <th>任务</th>
            <th>渠道</th>
            <th>提醒场景</th>
            <th>状态</th>
            <th>送达</th>
            <th>反馈</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedNotifications.length === 0">
            <td colspan="9">当前没有通知记录。</td>
          </tr>
          <tr v-for="item in pagedNotifications" :key="item.id">
            <td class="selection-cell">
              <input v-model="selectedNotificationIds" type="checkbox" :value="item.id" />
            </td>
            <td>{{ item.task_title || '-' }}</td>
            <td>{{ item.channel_text }}</td>
            <td>
              <div>{{ item.notify_scene_text || item.notify_type_text || notifyTypeText(item.notify_type) }}</div>
              <div class="subtle-text" v-if="item.remind_focus">{{ item.remind_focus }}</div>
            </td>
            <td>{{ item.status_text }}</td>
            <td>{{ item.delivered_count }}/{{ item.recipient_total }}</td>
            <td>{{ item.read_count }} {{ item.feedback_label }}</td>
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>
              <button class="button secondary small" type="button" @click="openNotificationDetail(item.id)">查看详情</button>
              <button class="button danger small" type="button" @click="deleteNotification(item)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" v-model:page-size="pageSize" :total="filteredNotifications.length" />
    </div>

    <div v-if="detailNotificationId" class="modal-mask">
      <div class="modal-card notification-detail-modal">
        <NotificationDetailPage
          :notification-id="detailNotificationId"
          embedded
          @cancel="closeNotificationDetail"
          @open-task="openTaskDetail"
        />
      </div>
    </div>

    <div v-if="detailTaskId" class="modal-mask">
      <div class="modal-card task-modal-card task-detail-modal-card">
        <AdminTaskDetail :task-id="detailTaskId" @cancel="closeTaskDetail" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import http from '../../api/http'
import AdminTaskDetail from './AdminTaskDetail.vue'
import AppPagination from '../../components/AppPagination.vue'
import NotificationDetailPage from '../shared/NotificationDetailPage.vue'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatDateTime } from '../../utils/format'

const notifications = ref([])
const keyword = ref('')
const channel = ref([])
const channelFilterOpen = ref(false)
const channelOptions = [
  { value: 'email', label: '邮件' },
  { value: 'qax', label: '即时消息' },
]
const page = ref(1)
const pageSize = ref(20)
const selectedNotificationIds = ref([])
const detailNotificationId = ref(null)
const detailTaskId = ref(null)
const isAllChannelsSelected = computed(() => channel.value.length === channelOptions.length)
const isCurrentPageSelected = computed(() =>
  pagedNotifications.value.length > 0 && pagedNotifications.value.every((item) => selectedNotificationIds.value.includes(item.id))
)
const selectedChannelText = computed(() => {
  if (!channel.value.length) return '全部渠道'
  return channelOptions.filter((item) => channel.value.includes(item.value)).map((item) => item.label).join('、')
})

const filteredNotifications = computed(() =>
  notifications.value.filter((item) => {
    const query = keyword.value.trim()
    const matchKeyword = !query || (item.task_title || '').includes(query)
    const matchChannel = channel.value.length === 0 || channel.value.includes(item.channel)
    return matchKeyword && matchChannel
  })
)

const pagedNotifications = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredNotifications.value.slice(start, start + pageSize.value)
})

const deliveredTotal = computed(() =>
  notifications.value.reduce((total, item) => total + Number(item.delivered_count || 0), 0)
)
const readTotal = computed(() =>
  notifications.value.reduce((total, item) => total + Number(item.read_count || 0), 0)
)
const retryTotal = computed(() =>
  notifications.value.reduce((total, item) => total + Number(item.retry_total || 0), 0)
)

watch([keyword, channel], () => {
  page.value = 1
  selectedNotificationIds.value = []
}, { deep: true })

function toggleAllChannels() {
  channel.value = isAllChannelsSelected.value ? [] : channelOptions.map((item) => item.value)
}

function toggleCurrentPageSelection() {
  const pageIds = pagedNotifications.value.map((item) => item.id)
  if (isCurrentPageSelected.value) {
    selectedNotificationIds.value = selectedNotificationIds.value.filter((id) => !pageIds.includes(id))
  } else {
    selectedNotificationIds.value = Array.from(new Set([...selectedNotificationIds.value, ...pageIds]))
  }
}

function openNotificationDetail(id) {
  detailNotificationId.value = id
}

function closeNotificationDetail() {
  detailNotificationId.value = null
}

function openTaskDetail(taskId) {
  detailTaskId.value = taskId
}

function closeTaskDetail() {
  detailTaskId.value = null
}

async function loadNotifications() {
  const { data } = await http.get('/notifications')
  notifications.value = data
  const existingIds = new Set(data.map((item) => item.id))
  selectedNotificationIds.value = selectedNotificationIds.value.filter((id) => existingIds.has(id))
}

async function deleteNotification(item) {
  if (!window.confirm(`确认删除该通知记录吗？任务：${item.task_title || '-'}`)) return
  await http.delete(`/notifications/${item.id}`)
  if (detailNotificationId.value === item.id) {
    detailNotificationId.value = null
  }
  await loadNotifications()
}

async function bulkDeleteNotifications() {
  if (selectedNotificationIds.value.length === 0) return
  if (!window.confirm(`确认删除选中的 ${selectedNotificationIds.value.length} 条通知记录吗？`)) return
  await http.post('/notifications/bulk-delete', { ids: selectedNotificationIds.value })
  selectedNotificationIds.value = []
  if (detailNotificationId.value) {
    detailNotificationId.value = null
  }
  await loadNotifications()
}

function closeFloatingFilters(event) {
  if (event.target?.closest?.('.multi-filter')) return
  channelFilterOpen.value = false
}

onMounted(() => {
  document.addEventListener('click', closeFloatingFilters)
  loadNotifications()
})

onUnmounted(() => {
  document.removeEventListener('click', closeFloatingFilters)
})
</script>

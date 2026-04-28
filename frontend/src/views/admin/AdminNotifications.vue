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
        <select v-model="channel">
          <option value="">全部渠道</option>
          <option value="email">邮件</option>
          <option value="qax">即时消息</option>
        </select>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
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
            <td colspan="8">当前没有通知记录。</td>
          </tr>
          <tr v-for="item in pagedNotifications" :key="item.id">
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
              <router-link class="button secondary small" :to="{ path: `/admin/notifications/${item.id}`, query: { from: route.fullPath } }">查看详情</router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="filteredNotifications.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatDateTime } from '../../utils/format'

const route = useRoute()
const notifications = ref([])
const keyword = ref('')
const channel = ref('')
const page = ref(1)
const pageSize = 8

const filteredNotifications = computed(() =>
  notifications.value.filter((item) => {
    const query = keyword.value.trim()
    const matchKeyword = !query || (item.task_title || '').includes(query)
    const matchChannel = !channel.value || item.channel === channel.value
    return matchKeyword && matchChannel
  })
)

const pagedNotifications = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredNotifications.value.slice(start, start + pageSize)
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
})

async function loadNotifications() {
  const { data } = await http.get('/notifications')
  notifications.value = data
}

onMounted(loadNotifications)
</script>

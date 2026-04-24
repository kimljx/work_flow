<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">邮件列表</div>
        <h1 class="workspace-title">已匹配邮件</h1>
        <p class="workspace-subtitle">这里仅展示命中模板的邮件记录，并提供详情页查看匹配内容和业务动作。收件测试会根据当前启用的 IMAP 或 POP3 协议自动切换。</p>
      </div>
      <div class="toolbar">
        <button class="button secondary" @click="testMailSettings" :disabled="busy">
          测试 SMTP
        </button>
        <button class="button secondary" @click="testInboxSettings" :disabled="busy">
          测试收件配置
        </button>
        <button class="button secondary" @click="initializeBaseline" :disabled="busy">
          设置扫描基准
        </button>
        <button class="button" @click="pollInbox" :disabled="busy">
          手动收取邮件
        </button>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">收件协议</span>
        <strong>{{ pollState?.inbox_protocol_text || 'IMAP' }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">自动收取</span>
        <strong>{{ pollState?.auto_poll_enabled ? '已开启' : '未开启' }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">下次收取倒计时</span>
        <strong>{{ countdownText }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">上次收取时间</span>
        <strong>{{ formatDateTime(pollState?.last_scan_at) }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">匹配邮件数</span>
        <strong>{{ events.length }}</strong>
      </div>
    </div>

    <div class="panel" v-if="feedback.message">
      <h2>{{ feedback.title }}</h2>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>匹配结果列表</h2>
          <p>每条记录都可以进入详情查看匹配内容、模板和落库动作。</p>
        </div>
        <button class="button secondary small" @click="loadAll" :disabled="busy">刷新列表</button>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>收取时间</th>
            <th>发件人</th>
            <th>主题</th>
            <th>匹配模板</th>
            <th>处理状态</th>
            <th>关联任务</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedEvents.length === 0">
            <td colspan="7">当前没有匹配成功的邮件。</td>
          </tr>
          <tr v-for="item in pagedEvents" :key="item.id">
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>{{ item.from_addr }}</td>
            <td>
              <div>{{ item.subject || '-' }}</div>
              <div class="subtle-text clamp-2">{{ item.body_digest || '-' }}</div>
            </td>
            <td>
              <div>{{ item.template_name || '-' }}</div>
              <div class="subtle-text">{{ item.notify_type_text || notifyTypeText(item.notify_type) }}</div>
            </td>
            <td>{{ item.process_status_text }}</td>
            <td>
              <router-link v-if="item.task_id" :to="`/admin/tasks/${item.task_id}`">
                {{ item.task_title || `任务 #${item.task_id}` }}
              </router-link>
              <span v-else>-</span>
            </td>
            <td>
              <router-link class="button secondary small" :to="`/admin/mail-events/${item.id}`">查看详情</router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="events.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatCountdown, formatDateTime } from '../../utils/format'

const events = ref([])
const pollState = ref(null)
const page = ref(1)
const pageSize = 10
const busy = ref(false)
const feedback = ref({
  title: '',
  message: '',
  type: 'success',
})
const nowTick = ref(Date.now())

const pagedEvents = computed(() => {
  const start = (page.value - 1) * pageSize
  return events.value.slice(start, start + pageSize)
})

const countdownText = computed(() => {
  void nowTick.value
  if (!pollState.value?.auto_poll_enabled) return '自动收取未开启'
  return formatCountdown(pollState.value?.next_poll_at)
})

let timerId = null

async function loadEvents() {
  const { data } = await http.get('/admin/mail/events')
  events.value = data
}

async function loadPollState() {
  const { data } = await http.get('/admin/mail/poll-state')
  pollState.value = data
}

async function loadAll() {
  busy.value = true
  try {
    await Promise.all([loadEvents(), loadPollState()])
  } finally {
    busy.value = false
  }
}

function showFeedback(title, message, type = 'success') {
  feedback.value = { title, message, type }
}

async function testMailSettings() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/mail/test')
    showFeedback('SMTP 测试结果', data.message, data.status === 'success' ? 'success' : 'error')
  } catch (error) {
    showFeedback('SMTP 测试结果', error.response?.data?.detail || 'SMTP 测试失败', 'error')
  } finally {
    busy.value = false
  }
}

async function testInboxSettings() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/mail/inbox-test')
    showFeedback('收件配置测试结果', data.message, data.status === 'success' ? 'success' : 'error')
  } catch (error) {
    showFeedback('收件配置测试结果', error.response?.data?.detail || '收件配置测试失败', 'error')
  } finally {
    busy.value = false
  }
}

async function initializeBaseline() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/mail/baseline')
    showFeedback('扫描基准设置', data.message, data.status === 'success' ? 'success' : 'error')
    await loadPollState()
  } catch (error) {
    showFeedback('扫描基准设置', error.response?.data?.detail || '设置扫描基准失败', 'error')
  } finally {
    busy.value = false
  }
}

async function pollInbox() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/mail/poll')
    showFeedback('邮件收取结果', data.message, ['success', 'initialized'].includes(data.status) ? 'success' : 'error')
    await Promise.all([loadEvents(), loadPollState()])
  } catch (error) {
    showFeedback('邮件收取结果', error.response?.data?.detail || '邮件收取失败', 'error')
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await loadAll()
  timerId = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timerId) {
    window.clearInterval(timerId)
  }
})
</script>

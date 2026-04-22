<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>{{ text.title }}</h1>
        <p>{{ text.subtitle }}</p>
      </div>
      <div class="toolbar">
        <button class="button secondary" @click="testMailSettings" :disabled="mailTesting">
          {{ mailTesting ? text.testing : text.smtpTest }}
        </button>
        <button class="button secondary" @click="testInboxSettings" :disabled="inboxTesting">
          {{ inboxTesting ? text.testing : text.imapTest }}
        </button>
        <button class="button secondary" @click="initializeBaseline" :disabled="baselineInitializing">
          {{ baselineInitializing ? text.setting : text.baseline }}
        </button>
        <button class="button secondary" @click="pollInbox" :disabled="polling">
          {{ polling ? text.scanning : text.pollInbox }}
        </button>
        <router-link class="button secondary" to="/admin/mail-events">{{ text.mailEvents }}</router-link>
      </div>
    </div>

    <div class="panel" v-if="mailTestMessage">
      <h2>{{ text.smtpResult }}</h2>
      <p :class="mailTestStatus === 'success' ? 'success-text' : 'error-text'">{{ mailTestMessage }}</p>
    </div>

    <div class="panel" v-if="inboxTestMessage">
      <h2>{{ text.imapResult }}</h2>
      <p :class="inboxTestStatus === 'success' ? 'success-text' : 'error-text'">{{ inboxTestMessage }}</p>
    </div>

    <div class="panel" v-if="baselineMessage">
      <h2>{{ text.baselineTitle }}</h2>
      <p :class="baselineStatus === 'success' ? 'success-text' : 'error-text'">{{ baselineMessage }}</p>
    </div>

    <div class="panel" v-if="pollMessage">
      <h2>{{ text.pollResult }}</h2>
      <p :class="pollStatus === 'success' || pollStatus === 'initialized' ? 'success-text' : 'error-text'">{{ pollMessage }}</p>
    </div>

    <div class="panel">
      <div class="muted-block">{{ text.guide }}</div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <select v-model="channel">
          <option value="">{{ text.allChannels }}</option>
          <option value="email">{{ text.email }}</option>
          <option value="qax">QAX</option>
        </select>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>{{ text.task }}</th>
            <th>{{ text.channel }}</th>
            <th>{{ text.notifyType }}</th>
            <th>{{ text.status }}</th>
            <th>{{ text.delivery }}</th>
            <th>{{ text.createdAt }}</th>
            <th>{{ text.readCount }}</th>
            <th>{{ text.retry }}</th>
            <th>{{ text.lastError }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedNotifications.length === 0">
            <td colspan="9">{{ text.empty }}</td>
          </tr>
          <tr v-for="item in pagedNotifications" :key="item.id">
            <td>{{ item.task_title || '-' }}</td>
            <td>{{ item.channel_text }}</td>
            <td>{{ item.notify_type_text || notifyTypeText(item.notify_type) }}</td>
            <td>{{ item.status_text }}</td>
            <td>{{ item.delivered_count }}/{{ item.recipient_total }}</td>
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>{{ item.read_count }}</td>
            <td>{{ item.retry_total }}</td>
            <td>{{ item.last_error || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="filteredNotifications.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatDateTime } from '../../utils/format'

const text = {
  title: '通知中心',
  subtitle: '统一查看邮件和 QAX 通知记录。QAX 仅展示送达和已读状态，不回写任务主状态。',
  testing: '测试中...',
  smtpTest: '测试 SMTP 配置',
  imapTest: '测试 IMAP 配置',
  setting: '设置中...',
  baseline: '设置首次扫描基准时间',
  scanning: '扫描中...',
  pollInbox: '手动扫描收件箱',
  mailEvents: '查看最近扫描邮件',
  smtpResult: 'SMTP 测试结果',
  imapResult: 'IMAP 测试结果',
  baselineTitle: '首次扫描保护',
  pollResult: '收件扫描结果',
  guide: '首次接入建议先点击“设置首次扫描基准时间”。设置后，系统只会扫描该时间之后的新未读邮件，并且每次只检查最近限定数量的未读邮件，避免历史无用邮件被批量处理。',
  allChannels: '全部渠道',
  email: '邮件',
  task: '任务',
  channel: '渠道',
  notifyType: '通知类型',
  status: '状态',
  delivery: '送达/总人数',
  createdAt: '通知时间',
  readCount: '已读',
  retry: '重试次数',
  lastError: '最后错误',
  empty: '当前没有通知记录。',
}

const notifications = ref([])
const channel = ref('')
const page = ref(1)
const pageSize = 8

const mailTesting = ref(false)
const mailTestMessage = ref('')
const mailTestStatus = ref('')

const inboxTesting = ref(false)
const inboxTestMessage = ref('')
const inboxTestStatus = ref('')

const baselineInitializing = ref(false)
const baselineMessage = ref('')
const baselineStatus = ref('')

const polling = ref(false)
const pollMessage = ref('')
const pollStatus = ref('')

const filteredNotifications = computed(() =>
  notifications.value.filter((item) => !channel.value || item.channel === channel.value)
)

const pagedNotifications = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredNotifications.value.slice(start, start + pageSize)
})

watch(channel, () => {
  page.value = 1
})

async function loadNotifications() {
  const { data } = await http.get('/notifications')
  notifications.value = data
}

async function testMailSettings() {
  mailTesting.value = true
  try {
    const { data } = await http.post('/admin/mail/test')
    mailTestStatus.value = data.status
    mailTestMessage.value = data.message
  } catch (error) {
    mailTestStatus.value = 'failed'
    mailTestMessage.value = error.response?.data?.detail || '邮件配置测试失败'
  } finally {
    mailTesting.value = false
  }
}

async function testInboxSettings() {
  inboxTesting.value = true
  try {
    const { data } = await http.post('/admin/mail/inbox-test')
    inboxTestStatus.value = data.status
    inboxTestMessage.value = data.message
  } catch (error) {
    inboxTestStatus.value = 'failed'
    inboxTestMessage.value = error.response?.data?.detail || 'IMAP 配置测试失败'
  } finally {
    inboxTesting.value = false
  }
}

async function initializeBaseline() {
  baselineInitializing.value = true
  try {
    const { data } = await http.post('/admin/mail/baseline')
    baselineStatus.value = data.status
    baselineMessage.value = data.message
  } catch (error) {
    baselineStatus.value = 'failed'
    baselineMessage.value = error.response?.data?.detail || '设置首次扫描基准时间失败'
  } finally {
    baselineInitializing.value = false
  }
}

async function pollInbox() {
  polling.value = true
  try {
    const { data } = await http.post('/admin/mail/poll')
    pollStatus.value = data.status
    pollMessage.value = data.message
  } catch (error) {
    pollStatus.value = 'failed'
    pollMessage.value = error.response?.data?.detail || '收件扫描失败'
  } finally {
    polling.value = false
  }
}

onMounted(loadNotifications)
</script>

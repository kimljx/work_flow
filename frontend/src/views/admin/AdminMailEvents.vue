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
        <button class="button secondary" @click="collectQaxStatus" :disabled="busy">
          手动采集 QAX
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
        <span class="metric-label">落库邮件数</span>
        <strong>{{ events.length }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">未匹配落库</span>
        <strong>{{ unmatchedEvents.length }}</strong>
      </div>
    </div>

    <div class="panel" v-if="feedback.message">
      <h2>{{ feedback.title }}</h2>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>定时任务设置</h2>
          <p>按分钟配置后台自动采集节奏，并控制每次默认扫描邮件数量。</p>
        </div>
        <button class="button" @click="saveSchedulerSettings" :disabled="busy">保存设置</button>
      </div>
      <div class="scheduler-setting-grid">
        <label class="checkbox-row scheduler-setting-toggle">
          <input v-model="schedulerForm.mail_auto_poll_enabled" type="checkbox" />
          <span>自动收取邮件</span>
        </label>
        <div class="scheduler-setting-controls">
          <div>
            <label>邮件采集间隔（分钟）</label>
            <input v-model.number="schedulerForm.mail_auto_poll_interval_minutes" type="number" min="1" />
          </div>
          <div>
            <label>默认邮件扫描数量</label>
            <input v-model.number="schedulerForm.mail_inbox_max_scan" type="number" min="1" />
          </div>
          <div>
            <label>扫描基准时间（可选）</label>
            <input v-model="schedulerForm.mail_scan_baseline_at" type="datetime-local" />
          </div>
        </div>
        <label class="checkbox-row scheduler-setting-toggle">
          <input v-model="schedulerForm.qax_auto_collect_enabled" type="checkbox" />
          <span>自动采集 QAX</span>
        </label>
        <div class="scheduler-setting-controls">
          <div>
            <label>QAX 采集间隔（分钟）</label>
            <input v-model.number="schedulerForm.qax_auto_collect_interval_minutes" type="number" min="1" />
          </div>
          <label class="checkbox-row scheduler-inline-checkbox">
            <input v-model="schedulerForm.qax_browser_visible" type="checkbox" />
            <span>Playwright 界面可视化</span>
          </label>
        </div>
        <label class="checkbox-row scheduler-setting-toggle">
          <input v-model="schedulerForm.due_remind_enabled" type="checkbox" />
          <span>主任务提前提醒</span>
        </label>
        <div class="scheduler-setting-controls">
          <div>
            <label>当天定时任务时间点</label>
            <input v-model="schedulerForm.due_remind_run_at" type="time" />
          </div>
          <div class="subtle-text scheduler-setting-note">按主任务的“提前多少天提醒”配置，在该时间点生成到期提醒。</div>
        </div>

        <label class="checkbox-row scheduler-setting-toggle">
          <input v-model="schedulerForm.overdue_remind_enabled" type="checkbox" />
          <span>延期未完成任务提醒</span>
        </label>
        <div class="scheduler-setting-controls">
          <div>
            <label>当天定时任务时间点</label>
            <input v-model="schedulerForm.overdue_remind_run_at" type="time" />
          </div>
          <div class="subtle-text scheduler-setting-note">每天扫描已延期或已超过截止时间且未完成的主任务，并发送提醒。</div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>落库邮件列表</h2>
          <p>包含匹配成功和未匹配的落库邮件，可进入详情查看正文、模板和处理结果。</p>
        </div>
        <div class="toolbar">
          <button class="button secondary small" :class="{ active: eventFilter === 'all' }" @click="setEventFilter('all')">全部</button>
          <button class="button secondary small" :class="{ active: eventFilter === 'unmatched' }" @click="setEventFilter('unmatched')">未匹配</button>
          <button class="button secondary small" @click="loadAll" :disabled="busy">刷新列表</button>
        </div>
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
            <td colspan="7">当前没有符合条件的邮件。</td>
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
      <AppPagination v-model="page" :total="filteredEvents.length" :page-size="pageSize" />
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
const eventFilter = ref('all')
const feedback = ref({
  title: '',
  message: '',
  type: 'success',
})
const nowTick = ref(Date.now())
const schedulerForm = ref({
  mail_auto_poll_enabled: true,
  mail_auto_poll_interval_minutes: 5,
  mail_inbox_max_scan: 20,
  due_remind_enabled: true,
  due_remind_run_at: '09:00',
  overdue_remind_enabled: true,
  overdue_remind_run_at: '09:00',
  qax_auto_collect_enabled: false,
  qax_auto_collect_interval_minutes: 60,
  mail_scan_baseline_at: '',
  qax_browser_visible: false,
})

const unmatchedEvents = computed(() => events.value.filter((item) => item.process_status === 'UNMATCHED'))

const filteredEvents = computed(() => {
  if (eventFilter.value === 'unmatched') return unmatchedEvents.value
  return events.value
})

const pagedEvents = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredEvents.value.slice(start, start + pageSize)
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

async function loadSchedulerSettings() {
  const { data } = await http.get('/admin/scheduler/settings')
  schedulerForm.value = {
    mail_auto_poll_enabled: Boolean(data.mail_auto_poll_enabled),
    mail_auto_poll_interval_minutes: Math.max(1, Math.round(Number(data.mail_auto_poll_interval_seconds || 300) / 60)),
    mail_inbox_max_scan: Number(data.mail_inbox_max_scan || 20),
    due_remind_enabled: data.due_remind_enabled !== false,
    due_remind_run_at: data.due_remind_run_at || '09:00',
    overdue_remind_enabled: data.overdue_remind_enabled !== false,
    overdue_remind_run_at: data.overdue_remind_run_at || '09:00',
    qax_auto_collect_enabled: Boolean(data.qax_auto_collect_enabled),
    qax_auto_collect_interval_minutes: Math.max(1, Math.round(Number(data.qax_auto_collect_interval_seconds || 3600) / 60)),
    mail_scan_baseline_at: data.mail_scan_baseline_at ? String(data.mail_scan_baseline_at).slice(0, 16) : '',
    qax_browser_visible: Boolean(data.qax_browser_visible),
  }
}

async function loadAll() {
  busy.value = true
  try {
    await Promise.all([loadEvents(), loadPollState(), loadSchedulerSettings()])
  } finally {
    busy.value = false
  }
}

function showFeedback(title, message, type = 'success') {
  feedback.value = { title, message, type }
}

function setEventFilter(value) {
  eventFilter.value = value
  page.value = 1
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
    const payload = schedulerForm.value.mail_scan_baseline_at
      ? { baseline_at: new Date(schedulerForm.value.mail_scan_baseline_at).toISOString() }
      : {}
    const { data } = await http.post('/admin/mail/baseline', payload)
    showFeedback('扫描基准设置', data.message, data.status === 'success' ? 'success' : 'error')
    await loadPollState()
  } catch (error) {
    showFeedback('扫描基准设置', error.response?.data?.detail || '设置扫描基准失败', 'error')
  } finally {
    busy.value = false
  }
}

async function saveSchedulerSettings() {
  busy.value = true
  try {
    await http.put('/admin/scheduler/settings', {
      ...schedulerForm.value,
      mail_auto_poll_interval_seconds: Math.max(1, Number(schedulerForm.value.mail_auto_poll_interval_minutes || 5)) * 60,
      mail_inbox_max_scan: Math.max(1, Number(schedulerForm.value.mail_inbox_max_scan || 20)),
      qax_auto_collect_interval_seconds: Math.max(1, Number(schedulerForm.value.qax_auto_collect_interval_minutes || 60)) * 60,
      mail_scan_baseline_at: schedulerForm.value.mail_scan_baseline_at
        ? new Date(schedulerForm.value.mail_scan_baseline_at).toISOString()
        : null,
    })
    showFeedback('定时任务设置', '设置已保存', 'success')
    await loadPollState()
  } catch (error) {
    showFeedback('定时任务设置', error.response?.data?.detail || '保存失败', 'error')
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

async function collectQaxStatus() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/qax/collect')
    const statusType = data.status === 'success' ? 'success' : 'error'
    const summary = `本次采集：更新 ${data.updated_count || 0} 条，失败 ${data.failed_count || 0} 条`
    showFeedback('QAX 状态采集结果', `${data.message}；${summary}`, statusType)
    await loadAll()
  } catch (error) {
    showFeedback('QAX 状态采集结果', error.response?.data?.detail || 'QAX 状态采集失败', 'error')
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

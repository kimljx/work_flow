<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">计划任务</div>
        <h1 class="workspace-title">邮件与 QAX 调度中心</h1>
        <p class="workspace-subtitle">
          在这里统一维护自动收件、提醒任务、邮件收发配置和 QAX 采集配置，保存后测试和手动执行都会直接使用当前页面配置。
        </p>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">收件协议</span>
        <strong>{{ pollState?.inbox_protocol_text || protocolLabel(schedulerForm.mail_inbox_protocol) }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">自动收件</span>
        <strong>{{ pollState?.auto_poll_enabled ? '已开启' : '未开启' }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">下次收件倒计时</span>
        <strong>{{ countdownText }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">上次收件时间</span>
        <strong>{{ formatDateTime(pollState?.last_scan_at) }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">落库邮件数</span>
        <strong>{{ events.length }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">未匹配邮件</span>
        <strong>{{ unmatchedEvents.length }}</strong>
      </div>
    </div>

    <div v-if="feedback.message" class="panel">
      <h2>{{ feedback.title }}</h2>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <div v-if="collectState.running" class="panel task-collect-panel">
      <div class="section-head">
        <div>
          <h2>后台收集中</h2>
          <p>{{ collectState.message }}</p>
        </div>
      </div>
      <div class="subtle-text">页面可继续操作，列表会在采集结束后自动刷新。</div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>计划任务与运行配置</h2>
          <p>原来需要改 `.env` 的邮件和 QAX 参数，现在可以直接在这里维护。</p>
        </div>
        <div class="toolbar scheduler-modal-actions">
          <button class="button secondary" @click="testMailSettings" :disabled="busy">测试 SMTP</button>
          <button class="button secondary" @click="testInboxSettings" :disabled="busy">测试收件配置</button>
          <button class="button secondary" @click="initializeBaseline" :disabled="busy">设置扫描基准</button>
          <button class="button secondary" @click="collectQaxStatus" :disabled="busy || collectState.running">手动采集 QAX</button>
          <button class="button secondary" @click="pollInbox" :disabled="busy || collectState.running">手动收取邮件</button>
          <button class="button" @click="saveSchedulerSettings" :disabled="busy">保存设置</button>
        </div>
      </div>

      <div class="scheduler-config-stack">
        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>自动任务</h3>
              <p>控制自动收件、QAX 采集和提醒任务的执行节奏。</p>
            </div>
          </div>
          <div class="scheduler-setting-grid">
            <label class="scheduler-toggle-row">
              <span>自动收取邮件</span>
              <input v-model="schedulerForm.mail_auto_poll_enabled" type="checkbox" />
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

            <label class="scheduler-toggle-row">
              <span>自动采集 QAX</span>
              <input v-model="schedulerForm.qax_auto_collect_enabled" type="checkbox" />
            </label>
            <div class="scheduler-setting-controls">
              <div>
                <label>QAX 采集间隔（分钟）</label>
                <input v-model.number="schedulerForm.qax_auto_collect_interval_minutes" type="number" min="1" />
              </div>
              <label class="scheduler-toggle-row scheduler-inline-toggle">
                <span>显示 Playwright 浏览器</span>
                <input v-model="schedulerForm.qax_browser_visible" type="checkbox" />
              </label>
              <label class="scheduler-toggle-row scheduler-inline-toggle">
                <span>忽略 HTTPS 证书错误</span>
                <input v-model="schedulerForm.qax_ignore_https_errors" type="checkbox" />
              </label>
            </div>

            <label class="scheduler-toggle-row">
              <span>主任务到期前提醒</span>
              <input v-model="schedulerForm.due_remind_enabled" type="checkbox" />
            </label>
            <div class="scheduler-setting-controls">
              <div>
                <label>每天执行时间</label>
                <input v-model="schedulerForm.due_remind_run_at" type="time" />
              </div>
              <div class="subtle-text scheduler-setting-note">按主任务的“提前多少天提醒”配置，在该时间点生成到期提醒。</div>
            </div>

            <label class="scheduler-toggle-row">
              <span>延期未完成任务提醒</span>
              <input v-model="schedulerForm.overdue_remind_enabled" type="checkbox" />
            </label>
            <div class="scheduler-setting-controls">
              <div>
                <label>每天执行时间</label>
                <input v-model="schedulerForm.overdue_remind_run_at" type="time" />
              </div>
              <div class="subtle-text scheduler-setting-note">每天扫描已延期或已超过截止时间且未完成的主任务，并自动发送提醒。</div>
            </div>
          </div>
        </section>

        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>SMTP 发件配置</h3>
              <p>保存后，“测试 SMTP”和业务通知发送都会立即使用这里的参数。</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label>SMTP 主机</label>
              <input v-model.trim="schedulerForm.smtp_host" type="text" placeholder="如 smtp.qq.com" />
            </div>
            <div>
              <label>SMTP 端口</label>
              <input v-model.number="schedulerForm.smtp_port" type="number" min="1" />
            </div>
            <div>
              <label>SMTP 用户名</label>
              <input v-model.trim="schedulerForm.smtp_user" type="text" />
            </div>
            <div>
              <label>SMTP 密码 / 授权码</label>
              <input v-model="schedulerForm.smtp_password" type="password" />
            </div>
            <div>
              <label>发件人地址</label>
              <input v-model.trim="schedulerForm.smtp_from_address" type="text" />
            </div>
            <div>
              <label>SMTP 超时（秒）</label>
              <input v-model.number="schedulerForm.smtp_timeout_seconds" type="number" min="1" />
            </div>
          </div>
          <div class="scheduler-toggle-strip">
            <label class="scheduler-toggle-row scheduler-inline-toggle">
              <span>启用 STARTTLS</span>
              <input v-model="schedulerForm.smtp_use_tls" type="checkbox" />
            </label>
            <label class="scheduler-toggle-row scheduler-inline-toggle">
              <span>启用 SSL</span>
              <input v-model="schedulerForm.smtp_use_ssl" type="checkbox" />
            </label>
          </div>
        </section>

        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>收件配置</h3>
              <p>统一维护收件协议，以及 IMAP / POP3 两套参数。切换协议后，测试收件和手动收取会按当前选择执行。</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label>收件协议</label>
              <select v-model="schedulerForm.mail_inbox_protocol">
                <option value="imap">IMAP</option>
                <option value="pop3">POP3</option>
              </select>
            </div>
          </div>

          <div class="scheduler-dual-grid">
            <section class="scheduler-subcard">
              <h4>IMAP</h4>
              <div class="form-grid">
                <div>
                  <label>IMAP 主机</label>
                  <input v-model.trim="schedulerForm.imap_host" type="text" />
                </div>
                <div>
                  <label>IMAP 端口</label>
                  <input v-model.number="schedulerForm.imap_port" type="number" min="1" />
                </div>
                <div>
                  <label>IMAP 用户名</label>
                  <input v-model.trim="schedulerForm.imap_user" type="text" />
                </div>
                <div>
                  <label>IMAP 密码 / 授权码</label>
                  <input v-model="schedulerForm.imap_password" type="password" />
                </div>
              </div>
              <div class="scheduler-toggle-strip">
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>启用 STARTTLS</span>
                  <input v-model="schedulerForm.imap_use_tls" type="checkbox" />
                </label>
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>启用 SSL</span>
                  <input v-model="schedulerForm.imap_use_ssl" type="checkbox" />
                </label>
              </div>
            </section>

            <section class="scheduler-subcard">
              <h4>POP3</h4>
              <div class="form-grid">
                <div>
                  <label>POP3 主机</label>
                  <input v-model.trim="schedulerForm.pop3_host" type="text" />
                </div>
                <div>
                  <label>POP3 端口</label>
                  <input v-model.number="schedulerForm.pop3_port" type="number" min="1" />
                </div>
                <div>
                  <label>POP3 用户名</label>
                  <input v-model.trim="schedulerForm.pop3_user" type="text" />
                </div>
                <div>
                  <label>POP3 密码 / 授权码</label>
                  <input v-model="schedulerForm.pop3_password" type="password" />
                </div>
              </div>
              <div class="scheduler-toggle-strip">
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>启用 STLS / TLS</span>
                  <input v-model="schedulerForm.pop3_use_tls" type="checkbox" />
                </label>
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>启用 SSL</span>
                  <input v-model="schedulerForm.pop3_use_ssl" type="checkbox" />
                </label>
              </div>
            </section>
          </div>
        </section>

        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>QAX 配置</h3>
              <p>保存后，手动采集和自动采集都会直接读取这些参数。</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label>QAX 登录地址</label>
              <input v-model.trim="schedulerForm.qax_base_url" type="text" placeholder="如 https://127.0.0.1:28443/login" />
            </div>
            <div>
              <label>QAX 分组名称</label>
              <input v-model.trim="schedulerForm.qax_group_name" type="text" />
            </div>
            <div>
              <label>QAX 用户名</label>
              <input v-model.trim="schedulerForm.qax_username" type="text" />
            </div>
            <div>
              <label>QAX 密码</label>
              <input v-model="schedulerForm.qax_password" type="password" />
            </div>
          </div>
        </section>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>落库邮件列表</h2>
          <p>包含匹配成功和未匹配的落库邮件，可进入详情页查看正文、模板和处理结果。</p>
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
              <button v-if="item.task_id" class="link-button" type="button" @click="openTaskDetail(item.task_id)">
                {{ item.task_title || `任务 #${item.task_id}` }}
              </button>
              <span v-else>-</span>
            </td>
            <td>
              <button class="button secondary small" type="button" @click="openMailDetail(item.id)">查看详情</button>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="filteredEvents.length" :page-size="pageSize" />
    </div>

    <div v-if="detailMailEventId" class="modal-mask" @click.self="closeMailDetail">
      <div class="modal-card mail-event-detail-modal">
        <AdminMailEventDetail
          :event-id="detailMailEventId"
          embedded
          @cancel="closeMailDetail"
          @open-task="openTaskDetail"
        />
      </div>
    </div>

    <div v-if="detailTaskId" class="modal-mask" @click.self="closeTaskDetail">
      <div class="modal-card task-modal-card task-detail-modal-card">
        <AdminTaskDetail :task-id="detailTaskId" @cancel="closeTaskDetail" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import http from '../../api/http'
import AdminMailEventDetail from './AdminMailEventDetail.vue'
import AdminTaskDetail from './AdminTaskDetail.vue'
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
const schedulerForm = ref(buildDefaultSchedulerForm())
const collectState = ref({})
const detailMailEventId = ref(null)
const detailTaskId = ref(null)

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

function buildDefaultSchedulerForm() {
  return {
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
    qax_base_url: '',
    qax_username: '',
    qax_password: '',
    qax_group_name: '',
    qax_ignore_https_errors: true,
    smtp_host: '',
    smtp_port: 25,
    smtp_user: '',
    smtp_password: '',
    smtp_from_address: '',
    smtp_use_tls: false,
    smtp_use_ssl: false,
    smtp_timeout_seconds: 20,
    mail_inbox_protocol: 'imap',
    imap_host: '',
    imap_port: 993,
    imap_user: '',
    imap_password: '',
    imap_use_tls: false,
    imap_use_ssl: true,
    pop3_host: '',
    pop3_port: 110,
    pop3_user: '',
    pop3_password: '',
    pop3_use_tls: false,
    pop3_use_ssl: false,
  }
}

function protocolLabel(protocol) {
  return String(protocol || '').toLowerCase() === 'pop3' ? 'POP3' : 'IMAP'
}

function openMailDetail(id) {
  detailMailEventId.value = id
}

function closeMailDetail() {
  detailMailEventId.value = null
}

function openTaskDetail(taskId) {
  detailTaskId.value = taskId
}

function closeTaskDetail() {
  detailTaskId.value = null
}

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
    ...buildDefaultSchedulerForm(),
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
    qax_base_url: data.qax_base_url || '',
    qax_username: data.qax_username || '',
    qax_password: data.qax_password || '',
    qax_group_name: data.qax_group_name || '',
    qax_ignore_https_errors: data.qax_ignore_https_errors !== false,
    smtp_host: data.smtp_host || '',
    smtp_port: Number(data.smtp_port || 25),
    smtp_user: data.smtp_user || '',
    smtp_password: data.smtp_password || '',
    smtp_from_address: data.smtp_from_address || '',
    smtp_use_tls: Boolean(data.smtp_use_tls),
    smtp_use_ssl: Boolean(data.smtp_use_ssl),
    smtp_timeout_seconds: Number(data.smtp_timeout_seconds || 20),
    mail_inbox_protocol: ['imap', 'pop3'].includes(String(data.mail_inbox_protocol || '').toLowerCase())
      ? String(data.mail_inbox_protocol).toLowerCase()
      : 'imap',
    imap_host: data.imap_host || '',
    imap_port: Number(data.imap_port || 993),
    imap_user: data.imap_user || '',
    imap_password: data.imap_password || '',
    imap_use_tls: Boolean(data.imap_use_tls),
    imap_use_ssl: data.imap_use_ssl !== false,
    pop3_host: data.pop3_host || '',
    pop3_port: Number(data.pop3_port || 110),
    pop3_user: data.pop3_user || '',
    pop3_password: data.pop3_password || '',
    pop3_use_tls: Boolean(data.pop3_use_tls),
    pop3_use_ssl: Boolean(data.pop3_use_ssl),
  }
}

async function loadAll() {
  busy.value = true
  try {
    await Promise.all([loadEvents(), loadPollState(), loadSchedulerSettings(), loadCollectState()])
  } finally {
    busy.value = false
  }
}

async function loadCollectState() {
  const { data } = await http.get('/admin/collect/state', { skipGlobalLoading: true })
  const wasRunning = collectState.value?.running
  collectState.value = data
  if (wasRunning && !data.running) {
    await Promise.all([loadEvents(), loadPollState()])
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
      ? { baseline_at: schedulerForm.value.mail_scan_baseline_at }
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
      smtp_port: Math.max(1, Number(schedulerForm.value.smtp_port || 25)),
      smtp_timeout_seconds: Math.max(1, Number(schedulerForm.value.smtp_timeout_seconds || 20)),
      imap_port: Math.max(1, Number(schedulerForm.value.imap_port || 993)),
      pop3_port: Math.max(1, Number(schedulerForm.value.pop3_port || 110)),
      mail_inbox_protocol: ['imap', 'pop3'].includes(String(schedulerForm.value.mail_inbox_protocol || '').toLowerCase())
        ? String(schedulerForm.value.mail_inbox_protocol).toLowerCase()
        : 'imap',
      mail_scan_baseline_at: schedulerForm.value.mail_scan_baseline_at
        ? schedulerForm.value.mail_scan_baseline_at
        : null,
    })
    showFeedback('计划任务设置', '设置已保存', 'success')
    await Promise.all([loadPollState(), loadSchedulerSettings()])
  } catch (error) {
    showFeedback('计划任务设置', error.response?.data?.detail || '保存失败', 'error')
  } finally {
    busy.value = false
  }
}

async function pollInbox() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/mail/poll', {}, { skipGlobalLoading: true })
    collectState.value = data
    showFeedback('邮件收取结果', data.message || '邮件收取已进入后台执行', data.accepted === false ? 'error' : 'success')
    await loadCollectState()
  } catch (error) {
    showFeedback('邮件收取结果', error.response?.data?.detail || '邮件收取失败', 'error')
  } finally {
    busy.value = false
  }
}

async function collectQaxStatus() {
  busy.value = true
  try {
    const { data } = await http.post('/admin/qax/collect', {}, { skipGlobalLoading: true })
    collectState.value = data
    showFeedback('QAX 状态采集结果', data.message || 'QAX 采集已进入后台执行', data.accepted === false ? 'error' : 'success')
    await loadCollectState()
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
    loadCollectState()
  }, 1000)
})

onUnmounted(() => {
  if (timerId) {
    window.clearInterval(timerId)
  }
})
</script>

<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">系统设置</div>
        <h1 class="workspace-title">运行配置</h1>
        <p class="workspace-subtitle">邮件、QAX 和域名 IP 映射保存在数据库中，容器重建后会随 PostgreSQL 数据继续保留。</p>
      </div>
    </div>

    <div v-if="feedback.message" class="panel">
      <h2>{{ feedback.title }}</h2>
      <p :class="feedback.type === 'success' ? 'success-text' : 'error-text'">{{ feedback.message }}</p>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>邮件与 QAX</h2>
          <p>保存后，手动测试、自动任务和后台采集都会直接读取数据库中的新配置。</p>
        </div>
        <div class="toolbar scheduler-modal-actions">
          <button class="button secondary" type="button" :disabled="busy" @click="testMailSettings">测试 SMTP</button>
          <button class="button secondary" type="button" :disabled="busy" @click="testInboxSettings">测试收件</button>
          <button class="button" type="button" :disabled="busy" @click="saveSettings">保存设置</button>
        </div>
      </div>

      <div class="scheduler-config-stack">
        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>SMTP 发件</h3>
              <p>用于任务通知、延期审批和提醒邮件发送。</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label>SMTP 主机</label>
              <input v-model.trim="form.smtp_host" type="text" placeholder="smtp.example.internal" />
            </div>
            <div>
              <label>SMTP 端口</label>
              <input v-model.number="form.smtp_port" type="number" min="1" />
            </div>
            <div>
              <label>SMTP 用户名</label>
              <input v-model.trim="form.smtp_user" type="text" />
            </div>
            <div>
              <label>SMTP 密码 / 授权码</label>
              <input v-model="form.smtp_password" type="password" />
            </div>
            <div>
              <label>发件人地址</label>
              <input v-model.trim="form.smtp_from_address" type="text" />
            </div>
            <div>
              <label>超时秒数</label>
              <input v-model.number="form.smtp_timeout_seconds" type="number" min="1" />
            </div>
          </div>
          <div class="scheduler-toggle-strip">
            <label class="scheduler-toggle-row scheduler-inline-toggle">
              <span>STARTTLS</span>
              <input v-model="form.smtp_use_tls" type="checkbox" />
            </label>
            <label class="scheduler-toggle-row scheduler-inline-toggle">
              <span>SSL</span>
              <input v-model="form.smtp_use_ssl" type="checkbox" />
            </label>
          </div>
        </section>

        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>收件协议</h3>
              <p>选择 IMAP 或 POP3 后，收件测试与后台轮询会使用对应配置。</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label>收件协议</label>
              <select v-model="form.mail_inbox_protocol">
                <option value="imap">IMAP</option>
                <option value="pop3">POP3</option>
              </select>
            </div>
            <div>
              <label>单次扫描数量</label>
              <input v-model.number="form.mail_inbox_max_scan" type="number" min="1" />
            </div>
          </div>
          <div class="scheduler-dual-grid">
            <section class="scheduler-subcard">
              <h4>IMAP</h4>
              <div class="form-grid">
                <div>
                  <label>主机</label>
                  <input v-model.trim="form.imap_host" type="text" />
                </div>
                <div>
                  <label>端口</label>
                  <input v-model.number="form.imap_port" type="number" min="1" />
                </div>
                <div>
                  <label>用户名</label>
                  <input v-model.trim="form.imap_user" type="text" />
                </div>
                <div>
                  <label>密码 / 授权码</label>
                  <input v-model="form.imap_password" type="password" />
                </div>
              </div>
              <div class="scheduler-toggle-strip">
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>STARTTLS</span>
                  <input v-model="form.imap_use_tls" type="checkbox" />
                </label>
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>SSL</span>
                  <input v-model="form.imap_use_ssl" type="checkbox" />
                </label>
              </div>
            </section>
            <section class="scheduler-subcard">
              <h4>POP3</h4>
              <div class="form-grid">
                <div>
                  <label>主机</label>
                  <input v-model.trim="form.pop3_host" type="text" />
                </div>
                <div>
                  <label>端口</label>
                  <input v-model.number="form.pop3_port" type="number" min="1" />
                </div>
                <div>
                  <label>用户名</label>
                  <input v-model.trim="form.pop3_user" type="text" />
                </div>
                <div>
                  <label>密码 / 授权码</label>
                  <input v-model="form.pop3_password" type="password" />
                </div>
              </div>
              <div class="scheduler-toggle-strip">
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>TLS</span>
                  <input v-model="form.pop3_use_tls" type="checkbox" />
                </label>
                <label class="scheduler-toggle-row scheduler-inline-toggle">
                  <span>SSL</span>
                  <input v-model="form.pop3_use_ssl" type="checkbox" />
                </label>
              </div>
            </section>
          </div>
        </section>

        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>QAX</h3>
              <p>用于 QAX 状态采集，支持内网自签证书。</p>
            </div>
          </div>
          <div class="form-grid">
            <div>
              <label>登录地址</label>
              <input v-model.trim="form.qax_base_url" type="text" placeholder="https://qax.example.internal:28443/login" />
            </div>
            <div>
              <label>分组名称</label>
              <input v-model.trim="form.qax_group_name" type="text" />
            </div>
            <div>
              <label>用户名</label>
              <input v-model.trim="form.qax_username" type="text" />
            </div>
            <div>
              <label>密码</label>
              <input v-model="form.qax_password" type="password" />
            </div>
          </div>
          <div class="scheduler-toggle-strip">
            <label class="scheduler-toggle-row scheduler-inline-toggle">
              <span>显示浏览器</span>
              <input v-model="form.qax_browser_visible" type="checkbox" />
            </label>
            <label class="scheduler-toggle-row scheduler-inline-toggle">
              <span>忽略 HTTPS 证书错误</span>
              <input v-model="form.qax_ignore_https_errors" type="checkbox" />
            </label>
          </div>
        </section>

        <section class="scheduler-config-card">
          <div class="scheduler-config-header">
            <div>
              <h3>域名 IP 映射</h3>
              <p>开启自动解析后，保存时会解析已配置域名并写入数据库；DNS 不可用时可手动填写 IP。</p>
            </div>
            <button class="button secondary small" type="button" @click="addMapping">添加映射</button>
          </div>
          <label class="scheduler-toggle-row scheduler-inline-toggle">
            <span>保存时自动解析域名</span>
            <input v-model="form.dns_auto_resolve_enabled" type="checkbox" />
          </label>
          <div class="host-mapping-list">
            <div v-for="(item, index) in form.mail_host_mappings" :key="item.id || index" class="host-mapping-row">
              <input v-model.trim="item.host" type="text" placeholder="域名" />
              <input v-model.trim="item.ip" type="text" placeholder="IP，可留空自动解析" />
              <label class="scheduler-toggle-row scheduler-inline-toggle host-mapping-toggle">
                <span>启用</span>
                <input v-model="item.enabled" type="checkbox" />
              </label>
              <input v-model.trim="item.note" type="text" placeholder="备注" />
              <button class="button secondary small" type="button" @click="removeMapping(index)">删除</button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import http from '../../api/http'

const busy = ref(false)
const feedback = ref({ title: '', message: '', type: 'success' })
const form = ref(buildDefaultForm())

function buildDefaultForm() {
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
    dns_auto_resolve_enabled: true,
    mail_host_mappings: [],
  }
}

function applySettings(data) {
  form.value = {
    ...buildDefaultForm(),
    ...data,
    mail_auto_poll_interval_minutes: Math.max(1, Math.round(Number(data.mail_auto_poll_interval_seconds || 300) / 60)),
    qax_auto_collect_interval_minutes: Math.max(1, Math.round(Number(data.qax_auto_collect_interval_seconds || 3600) / 60)),
    mail_scan_baseline_at: data.mail_scan_baseline_at ? String(data.mail_scan_baseline_at).slice(0, 16) : '',
    smtp_port: Number(data.smtp_port || 25),
    smtp_timeout_seconds: Number(data.smtp_timeout_seconds || 20),
    imap_port: Number(data.imap_port || 993),
    pop3_port: Number(data.pop3_port || 110),
    mail_inbox_protocol: ['imap', 'pop3'].includes(String(data.mail_inbox_protocol || '').toLowerCase())
      ? String(data.mail_inbox_protocol).toLowerCase()
      : 'imap',
    dns_auto_resolve_enabled: data.dns_auto_resolve_enabled !== false,
    mail_host_mappings: Array.isArray(data.mail_host_mappings) ? data.mail_host_mappings : [],
  }
}

function buildPayload() {
  return {
    ...form.value,
    mail_auto_poll_interval_seconds: Math.max(1, Number(form.value.mail_auto_poll_interval_minutes || 5)) * 60,
    mail_inbox_max_scan: Math.max(1, Number(form.value.mail_inbox_max_scan || 20)),
    qax_auto_collect_interval_seconds: Math.max(1, Number(form.value.qax_auto_collect_interval_minutes || 60)) * 60,
    smtp_port: Math.max(1, Number(form.value.smtp_port || 25)),
    smtp_timeout_seconds: Math.max(1, Number(form.value.smtp_timeout_seconds || 20)),
    imap_port: Math.max(1, Number(form.value.imap_port || 993)),
    pop3_port: Math.max(1, Number(form.value.pop3_port || 110)),
    mail_inbox_protocol: ['imap', 'pop3'].includes(String(form.value.mail_inbox_protocol || '').toLowerCase())
      ? String(form.value.mail_inbox_protocol).toLowerCase()
      : 'imap',
    mail_scan_baseline_at: form.value.mail_scan_baseline_at || null,
    mail_host_mappings: form.value.mail_host_mappings
      .filter((item) => String(item.host || '').trim())
      .map((item) => ({
        id: item.id || null,
        host: String(item.host || '').trim(),
        ip: String(item.ip || '').trim(),
        enabled: item.enabled !== false,
        source: item.source || 'manual',
        note: item.note || '',
      })),
  }
}

async function loadSettings() {
  const { data } = await http.get('/admin/scheduler/settings')
  applySettings(data)
}

async function saveSettings() {
  busy.value = true
  try {
    const { data } = await http.put('/admin/scheduler/settings', buildPayload())
    applySettings(data)
    feedback.value = { title: '系统设置', message: '设置已保存到数据库。', type: 'success' }
  } catch (error) {
    feedback.value = { title: '系统设置', message: error.response?.data?.detail || '保存失败', type: 'error' }
  } finally {
    busy.value = false
  }
}

async function testMailSettings() {
  await saveSettings()
  if (feedback.value.type === 'error') return
  try {
    const { data } = await http.post('/admin/mail/test')
    feedback.value = { title: 'SMTP 测试', message: data.message, type: data.status === 'success' ? 'success' : 'error' }
  } catch (error) {
    feedback.value = { title: 'SMTP 测试', message: error.response?.data?.detail || '测试失败', type: 'error' }
  }
}

async function testInboxSettings() {
  await saveSettings()
  if (feedback.value.type === 'error') return
  try {
    const { data } = await http.post('/admin/mail/inbox-test')
    feedback.value = { title: '收件测试', message: data.message, type: data.status === 'success' ? 'success' : 'error' }
  } catch (error) {
    feedback.value = { title: '收件测试', message: error.response?.data?.detail || '测试失败', type: 'error' }
  }
}

function addMapping() {
  form.value.mail_host_mappings.push({ host: '', ip: '', enabled: true, source: 'manual', note: '' })
}

function removeMapping(index) {
  form.value.mail_host_mappings.splice(index, 1)
}

onMounted(loadSettings)
</script>

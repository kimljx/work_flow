<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>模板管理</h1>
        <p>统一维护邮件发送模板、QAX 发送模板和邮件回复模板，并为每种模板类型保留默认模板。</p>
      </div>
    </div>

    <div class="panel">
      <h2>模板使用规则</h2>
      <div class="stats">
        <div class="stat-card" v-for="rule in templateRules" :key="rule.title">
          <div>{{ rule.title }}</div>
          <strong style="font-size: 18px; margin-top: 8px;">{{ rule.keyword }}</strong>
          <p style="margin-top: 8px; color: var(--muted);">{{ rule.description }}</p>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="form-grid">
        <div>
          <label>模板名称</label>
          <input v-model="form.name" />
        </div>
        <div>
          <label>模板类型</label>
          <select v-model="form.template_kind">
            <option v-for="item in templateKindOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
        <div>
          <label>通知类型</label>
          <select v-model="form.notify_type">
            <option v-for="item in currentNotifyTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}（{{ item.value }}）
            </option>
          </select>
        </div>
        <div>
          <label>优先级</label>
          <input v-model.number="form.priority" type="number" />
        </div>
      </div>
      <div class="form-grid">
        <div>
          <label>主题匹配规则</label>
          <input v-model="form.subject_rule" />
        </div>
        <div>
          <label>正文匹配规则</label>
          <input v-model="form.body_rule" />
        </div>
      </div>
      <div>
        <label>模板内容</label>
        <textarea v-model="form.content" rows="5" />
      </div>
      <div class="toolbar">
        <button @click="submitTemplate">{{ editingId ? '保存模板' : '新增模板' }}</button>
        <button class="button secondary" v-if="editingId" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>模板名</th>
            <th>类型</th>
            <th>通知类型</th>
            <th>优先级</th>
            <th>版本</th>
            <th>启用状态</th>
            <th>默认模板</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedTemplates.length === 0">
            <td colspan="8">当前没有模板数据。</td>
          </tr>
          <tr v-for="item in pagedTemplates" :key="item.id">
            <td>{{ item.name }}</td>
            <td>{{ templateKindText(item.template_kind) }}</td>
            <td>{{ item.notify_type_text || notifyTypeText(item.notify_type) }}</td>
            <td>{{ item.priority }}</td>
            <td>{{ item.version }}</td>
            <td>{{ item.enabled ? '启用' : '停用' }}</td>
            <td>{{ item.is_default ? '是' : '否' }}</td>
            <td>
              <div class="toolbar">
                <button class="button secondary" @click="editTemplate(item)">编辑</button>
                <button class="button secondary" @click="setDefault(item.id)">设为默认</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="templates.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { notifyTypeText } from '../../constants/notifyTypes'

const templates = ref([])
const editingId = ref(null)
const templateKindOptions = ref([
  { value: 'MAIL_SEND', label: '邮件发送模板' },
  { value: 'QAX_SEND', label: 'QAX 发送模板' },
  { value: 'MAIL_REPLY', label: '邮件回复模板' },
])
const notifyTypeOptions = ref({
  MAIL_SEND: [
    { value: 'task_created', label: '任务创建通知' },
    { value: 'manual_remind', label: '手动提醒' },
    { value: 'due_remind', label: '到期提醒' },
    { value: 'delay_approval', label: '延期审批通知' },
  ],
  QAX_SEND: [
    { value: 'task_created', label: '任务创建通知' },
    { value: 'manual_remind', label: '手动提醒' },
    { value: 'due_remind', label: '到期提醒' },
    { value: 'delay_approval', label: '延期审批通知' },
  ],
  MAIL_REPLY: [
    { value: 'task_done', label: '邮件回执-已完成' },
    { value: 'task_in_progress', label: '邮件回执-进行中' },
    { value: 'delay_request', label: '邮件回执-延期申请' },
    { value: 'delay_approve', label: '邮件回执-延期审批' },
  ],
})
const page = ref(1)
const pageSize = 8
const templateRules = [
  {
    title: '邮件发送模板',
    keyword: 'MAIL_SEND',
    description: '用于任务创建、提醒等外发邮件正文。建议在正文中附带明确的回复指引，方便成员按格式回信。',
  },
  {
    title: 'QAX 发送模板',
    keyword: 'QAX_SEND',
    description: '用于桌面通知文案展示。QAX 只负责送达和已读展示，不直接回写任务主状态。',
  },
  {
    title: '邮件回复模板',
    keyword: 'MAIL_REPLY',
    description: '用于解析成员和管理员的邮件回复。系统按“先主题后正文，再按优先级、版本、模板编号”选择命中的模板。',
  },
]
const form = reactive({
  name: '',
  template_kind: 'MAIL_SEND',
  notify_type: 'task_created',
  priority: 100,
  version: 1,
  enabled: true,
  is_default: false,
  subject_rule: '',
  body_rule: '',
  content: '',
})

const currentNotifyTypeOptions = computed(() => notifyTypeOptions.value[form.template_kind] || [])

const pagedTemplates = computed(() => {
  const start = (page.value - 1) * pageSize
  return templates.value.slice(start, start + pageSize)
})

watch(
  () => templates.value.length,
  () => {
    page.value = 1
  }
)

function templateKindText(kind) {
  return {
    MAIL_SEND: '邮件发送模板',
    QAX_SEND: 'QAX 发送模板',
    MAIL_REPLY: '邮件回复模板',
  }[kind] || kind
}

function resetForm() {
  editingId.value = null
  const initialNotifyType = notifyTypeOptions.value.MAIL_SEND?.[0]?.value || 'task_created'
  Object.assign(form, {
    name: '',
    template_kind: 'MAIL_SEND',
    notify_type: initialNotifyType,
    priority: 100,
    version: 1,
    enabled: true,
    is_default: false,
    subject_rule: '',
    body_rule: '',
    content: '',
  })
}

async function loadTemplates() {
  const { data } = await http.get('/templates')
  templates.value = data
}

async function loadTemplateOptions() {
  const { data } = await http.get('/templates/options')
  if (Array.isArray(data.template_kind_options) && data.template_kind_options.length > 0) {
    templateKindOptions.value = data.template_kind_options
  }
  if (data.notify_type_options) {
    notifyTypeOptions.value = data.notify_type_options
  }
  if (!form.notify_type) {
    form.notify_type = (notifyTypeOptions.value[form.template_kind] || [])[0]?.value || ''
  }
}

function editTemplate(item) {
  editingId.value = item.id
  Object.assign(form, item)
}

async function submitTemplate() {
  if (editingId.value) {
    await http.put(`/templates/${editingId.value}`, form)
  } else {
    await http.post('/templates', form)
  }
  resetForm()
  await loadTemplates()
}

async function setDefault(id) {
  await http.post(`/templates/${id}/set-default`)
  await loadTemplates()
}

watch(
  () => form.template_kind,
  (kind) => {
    const options = notifyTypeOptions.value[kind] || []
    if (options.length > 0 && !options.some((item) => item.value === form.notify_type)) {
      form.notify_type = options[0].value
    }
  }
)

onMounted(async () => {
  await loadTemplateOptions()
  resetForm()
  await loadTemplates()
})
</script>

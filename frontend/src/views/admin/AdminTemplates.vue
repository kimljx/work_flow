<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>模板管理</h1>
        <p>统一维护邮件发送模板、即时消息发送模板和邮件回复模板，并为每种模板类型保留默认模板。</p>
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
        <div class="template-editor-shell">
          <div class="template-drop-hint">
            发送类模板支持点击或拖拽变量模块到下方文本框，自动插入占位符。
          </div>
          <div v-if="insertFeedback.visible" class="template-insert-feedback">
            已插入变量 {{ insertFeedback.token }}
          </div>
          <textarea
            ref="contentTextareaRef"
            v-model="form.content"
            rows="8"
            :class="{ 'template-editor-active': insertFeedback.visible }"
            @click="recordCursorPosition"
            @keyup="recordCursorPosition"
            @select="recordCursorPosition"
            @dragover.prevent="handleTemplateDragOver"
            @drop="handleTemplateDrop"
          />
        </div>
      </div>
      <div class="toolbar">
        <button @click="submitTemplate">{{ editingId ? '保存模板' : '新增模板' }}</button>
        <button class="button secondary" v-if="editingId" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>占位符说明与预览</h2>
          <p>发送类模板会按负责人、任务创建人和接收人的子任务动态渲染；回复类模板用于匹配，不直接发送正文。</p>
        </div>
      </div>
      <div class="task-split-grid">
        <div class="task-split-column">
          <h3>当前可用占位符</h3>
          <div class="variable-palette">
            <button
              v-for="item in activePlaceholderTips"
              :key="item.key"
              type="button"
              class="variable-card"
              :draggable="item.draggable"
              :disabled="!item.draggable"
              @click="insertPlaceholderToken(item.key)"
              @dragstart="handlePlaceholderDragStart($event, item.key)"
            >
              <div>
                <strong>{{ item.label }}</strong>
                <div class="subtle-text">{{ item.example }}</div>
              </div>
              <code>{{ item.key }}</code>
            </button>
          </div>
        </div>

        <div class="task-split-column">
          <h3>模板预览</h3>
          <div v-if="form.template_kind === 'MAIL_REPLY'" class="muted-block">
            邮件回复模板只参与主题和正文匹配，不直接发送通知正文。匹配时系统会自动忽略系统下发邮件中的回复指引和引用原文，避免误匹配。
          </div>
          <pre v-else class="detail-pre">{{ renderedTemplatePreview }}</pre>
        </div>
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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { notifyTypeText } from '../../constants/notifyTypes'

const templates = ref([])
const editingId = ref(null)
const templateKindOptions = ref([
  { value: 'MAIL_SEND', label: '邮件发送模板' },
  { value: 'QAX_SEND', label: '即时消息发送模板' },
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
let insertFeedbackTimer = null
const placeholderTips = {
  common: [
    { key: '{task_id}', label: '任务编号', example: '示例：任务通知提醒#128' },
    { key: '{task_title}', label: '任务标题', example: '示例：季度经营复盘' },
    { key: '{task_content}', label: '任务内容', example: '示例：整理经营数据并完成复盘材料' },
    { key: '{owner_name}', label: '负责人', example: '示例：张晓明' },
    { key: '{creator_name}', label: '任务创建人', example: '示例：李主管' },
    { key: '{recipient_name}', label: '当前接收人', example: '示例：王小雨' },
    { key: '{start_at}', label: '开始时间', example: '示例：2026-05-01 09:00' },
    { key: '{end_at}', label: '结束时间', example: '示例：2026-05-03 18:00' },
    { key: '{subtask_summary}', label: '接收人子任务清单', example: '示例：1. 汇总日报（执行人：王小雨）' },
    { key: '{subtask_brief}', label: '接收人子任务摘要', example: '示例：汇总日报；整理周报' },
    { key: '{reply_guide}', label: '回复指引', example: '示例：请按“任务ID + 状态关键词”回复' },
  ],
  delayApproval: [
    { key: '{delay_request_id}', label: '延期申请编号', example: '示例：58' },
    { key: '{applicant_name}', label: '延期申请人', example: '示例：王小雨' },
    { key: '{proposed_deadline}', label: '申请截止时间', example: '示例：2026-05-10' },
    { key: '{apply_reason}', label: '延期原因', example: '示例：等待外部数据回传' },
  ],
  mailReply: [
    { key: '主题匹配规则', label: '主题规则', example: '用于识别“已完成 / 进行中 / 延期申请 / 同意拒绝”等关键词' },
    { key: '正文匹配规则', label: '正文规则', example: '用于补充匹配上下文，系统会忽略回复指引与引用原文后再匹配' },
  ],
}
const templateRules = [
  {
    title: '邮件发送模板',
    keyword: 'MAIL_SEND',
    description: '用于任务创建、提醒等外发邮件正文。建议在正文中附带明确的回复指引，方便成员按格式回信。',
  },
  {
    title: '即时消息发送模板',
    keyword: 'QAX_SEND',
    description: '用于即时消息文案展示。即时消息只负责送达和已读展示，不直接回写任务主状态。',
  },
  {
    title: '邮件回复模板',
    keyword: 'MAIL_REPLY',
    description: '用于解析成员和管理员的邮件回复。系统按“先主题后正文，再按优先级、版本、模板编号”选择命中的模板，并自动忽略回复指引和引用原文。',
  },
]
const contentTextareaRef = ref(null)
const cursorPosition = ref(0)
const insertFeedback = reactive({
  visible: false,
  token: '',
})
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
const activePlaceholderTips = computed(() => {
  if (form.template_kind === 'MAIL_REPLY') {
    return placeholderTips.mailReply.map((item) => ({ ...item, draggable: false }))
  }
  const tips = [...placeholderTips.common]
  if (form.notify_type === 'delay_approval') {
    tips.push(...placeholderTips.delayApproval)
  }
  return tips.map((item) => ({ ...item, draggable: item.key.startsWith('{') }))
})
const previewContext = computed(() => ({
  task_id: '128',
  task_title: '季度经营复盘',
  task_content: '请整理经营数据、形成复盘摘要并完成汇报材料。',
  owner_name: '张晓明',
  creator_name: '李主管',
  recipient_name: '王小雨',
  start_at: '2026-05-01 09:00',
  end_at: '2026-05-03 18:00',
  subtask_summary: '1. 汇总日报（执行人：王小雨）：整理核心经营数据\n2. 输出周报（执行人：王小雨）：形成可汇报摘要',
  subtask_brief: '汇总日报；输出周报',
  reply_guide: '请按“任务ID + 状态关键词 + 说明”回复。',
  delay_request_id: '58',
  applicant_name: '王小雨',
  proposed_deadline: '2026-05-10',
  apply_reason: '等待外部数据回传，无法按原计划完成。',
}))
const renderedTemplatePreview = computed(() => {
  const content = form.content || defaultPreviewTemplate()
  let preview = content
  Object.entries(previewContext.value).forEach(([key, value]) => {
    preview = preview.replaceAll(`{${key}}`, value)
  })
  return preview
})

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
    QAX_SEND: '即时消息发送模板',
    MAIL_REPLY: '邮件回复模板',
  }[kind] || kind
}

/**
 * 返回当前模板类型的默认预览内容。
 * @returns {string} 用于空模板时的示例正文。
 */
function defaultPreviewTemplate() {
  if (form.notify_type === 'delay_approval') {
    return [
      '延期申请编号：{delay_request_id}',
      '任务标题：{task_title}',
      '负责人：{owner_name}',
      '任务创建人：{creator_name}',
      '申请人：{applicant_name}',
      '申请截止时间：{proposed_deadline}',
      '申请原因：{apply_reason}',
    ].join('\n')
  }
  return [
    '任务标题：{task_title}',
    '负责人：{owner_name}',
    '任务创建人：{creator_name}',
    '当前接收人：{recipient_name}',
    '开始时间：{start_at}',
    '结束时间：{end_at}',
    '子任务安排：',
    '{subtask_summary}',
    '{reply_guide}',
  ].join('\n')
}

/**
 * 记录模板正文文本框中的光标位置。
 * 变量拖拽或点击插入时会复用该位置，避免一律追加到末尾。
 * @param {Event} event 原生输入事件。
 * @returns {void}
 */
function recordCursorPosition(event) {
  cursorPosition.value = event?.target?.selectionStart ?? 0
}

/**
 * 将占位符插入模板内容中的当前光标位置。
 * 回复匹配模板不需要插入正文变量，因此在该模式下直接返回。
 * @param {string} token 要插入的占位符字符串。
 * @returns {Promise<void>}
 */
async function insertPlaceholderToken(token) {
  if (form.template_kind === 'MAIL_REPLY' || !token.startsWith('{')) {
    return
  }
  const textarea = contentTextareaRef.value
  const start = textarea?.selectionStart ?? cursorPosition.value ?? form.content.length
  const end = textarea?.selectionEnd ?? start
  const nextContent = `${form.content.slice(0, start)}${token}${form.content.slice(end)}`
  form.content = nextContent
  cursorPosition.value = start + token.length
  await nextTick()
  if (textarea) {
    textarea.focus()
    textarea.setSelectionRange(cursorPosition.value, cursorPosition.value)
  }
  showInsertFeedback(token)
}

/**
 * 在开始拖拽变量模块时写入占位符数据。
 * @param {DragEvent} event 拖拽事件。
 * @param {string} token 占位符字符串。
 * @returns {void}
 */
function handlePlaceholderDragStart(event, token) {
  if (!token.startsWith('{')) {
    return
  }
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setData('text/plain', token)
}

/**
 * 允许模板文本框接收拖拽插入。
 * @param {DragEvent} event 拖拽事件。
 * @returns {void}
 */
function handleTemplateDragOver(event) {
  event.dataTransfer.dropEffect = 'copy'
}

/**
 * 处理变量模块拖拽到模板文本框中的插入动作。
 * @param {DragEvent} event 拖拽放下事件。
 * @returns {Promise<void>}
 */
async function handleTemplateDrop(event) {
  event.preventDefault()
  cursorPosition.value = event.target?.selectionStart ?? cursorPosition.value
  const token = event.dataTransfer.getData('text/plain')
  await insertPlaceholderToken(token)
}

/**
 * 展示模板变量插入反馈，并高亮当前编辑器。
 * 短暂提示可以帮助用户确认变量是否落到了预期位置。
 * @param {string} token 刚插入的占位符。
 * @returns {void}
 */
function showInsertFeedback(token) {
  insertFeedback.token = token
  insertFeedback.visible = true
  if (insertFeedbackTimer) {
    clearTimeout(insertFeedbackTimer)
  }
  insertFeedbackTimer = window.setTimeout(() => {
    insertFeedback.visible = false
    insertFeedback.token = ''
    insertFeedbackTimer = null
  }, 1200)
}

/**
 * 重置模板编辑表单到默认状态。
 * @returns {void}
 */
function resetForm() {
  editingId.value = null
  insertFeedback.visible = false
  insertFeedback.token = ''
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

/**
 * 拉取模板列表。
 * @returns {Promise<void>}
 */
async function loadTemplates() {
  const { data } = await http.get('/templates')
  templates.value = data
}

/**
 * 拉取模板类型与通知类型选项。
 * @returns {Promise<void>}
 */
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

/**
 * 将指定模板加载到编辑表单中。
 * @param {object} item 模板列表项。
 * @returns {void}
 */
function editTemplate(item) {
  editingId.value = item.id
  Object.assign(form, item)
}

/**
 * 提交模板新增或保存请求。
 * @returns {Promise<void>}
 */
async function submitTemplate() {
  if (editingId.value) {
    await http.put(`/templates/${editingId.value}`, form)
  } else {
    await http.post('/templates', form)
  }
  resetForm()
  await loadTemplates()
}

/**
 * 将模板设置为当前通知类型的默认模板。
 * @param {number} id 模板编号。
 * @returns {Promise<void>}
 */
async function setDefault(id) {
  await http.post(`/templates/${id}/set-default`)
  await loadTemplates()
}

onBeforeUnmount(() => {
  if (insertFeedbackTimer) {
    clearTimeout(insertFeedbackTimer)
  }
})

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

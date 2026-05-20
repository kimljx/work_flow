<template>
  <div class="task-editor-shell">
    <div class="section-head">
      <div>
        <h2>{{ isEdit ? '编辑任务' : '新建任务' }}</h2>
        <p>保留任务名称、任务内容、负责人、时间和子任务这些核心字段。</p>
      </div>
      <button type="button" class="button secondary small" :disabled="submitting" @click="$emit('cancel')">关闭</button>
    </div>

    <form class="page" @submit.prevent="submit">
      <div class="form-grid">
        <div>
          <label>任务名称</label>
          <input v-model="form.title" required />
        </div>
        <div>
          <label>优先级</label>
          <select v-model="form.priority">
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
        </div>
        <div v-if="isEdit">
          <label>开始时间</label>
          <input v-model="form.start_at" type="datetime-local" required />
        </div>
        <div>
          <label>截止时间</label>
          <input v-model="form.end_at" type="datetime-local" required />
        </div>
        <div>
          <label>到期前提醒天数</label>
          <input v-model.number="form.due_remind_days" type="number" min="0" />
        </div>
      </div>

      <div>
        <label>任务内容</label>
        <textarea v-model="form.content" rows="4" required />
      </div>

      <div class="panel">
        <div class="section-head">
          <div>
            <h3>负责人</h3>
            <p>选择收到任务通知的人。系统会自动将首位负责人作为主负责人，子任务也会直接放在这张负责人卡片中维护。</p>
          </div>
        </div>

        <div class="task-simple-list">
          <div
            v-for="user in users"
            :key="user.id"
            class="task-simple-row task-responsible-card"
            :class="{ 'task-responsible-card-active': responsibleSelection.includes(String(user.id)) }"
          >
            <label class="task-responsible-toggle">
              <span class="task-simple-check">
                <input v-model="responsibleSelection" type="checkbox" :value="String(user.id)" />
              </span>
              <span class="task-simple-main">
                <strong>{{ user.name }}</strong>
                <span class="subtle-text">{{ user.role_text }} / {{ user.email }}</span>
              </span>
            </label>

            <div v-if="responsibleSelection.includes(String(user.id))" class="task-responsible-subtasks">
              <div class="task-responsible-subtasks-head">
                <div>
                  <strong>子任务</strong>
                </div>
                <button
                  type="button"
                  class="button secondary small"
                  :disabled="submitting"
                  @click.stop="addSubtask(user.id)"
                >
                  新增子任务
                </button>
              </div>

              <div v-if="subtasksForUser(user.id).length > 0" class="task-responsible-subtask-list">
                <div
                  v-for="(item, index) in subtasksForUser(user.id)"
                  :key="item.local_key"
                  class="task-responsible-subtask-item"
                >
                  <span class="task-responsible-subtask-index">{{ index + 1 }}</span>
                  <input
                    v-model="item.title"
                    placeholder="请输入子任务内容"
                    @click.stop
                  />
                  <button
                    type="button"
                    class="button danger small"
                    :disabled="submitting"
                    @click.stop="removeSubtask(item.local_key)"
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="toolbar modal-actions">
        <button type="button" class="button secondary" :disabled="submitting" @click="$emit('cancel')">取消</button>
        <button type="submit" :disabled="submitting">{{ submitting ? '提交中...' : (isEdit ? '保存修改' : '创建任务') }}</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import http from '../../api/http'
import { toBackendDateTime, toDateTimeLocal } from '../../utils/format'

const props = defineProps({
  taskId: {
    type: [Number, String],
    default: null,
  },
})

const emit = defineEmits(['cancel', 'saved'])

const users = ref([])
const submitting = ref(false)
const responsibleSelection = ref([])
const subtaskSeed = ref(0)

const isEdit = computed(() => Boolean(props.taskId))
const responsibleOptions = computed(() => {
  const selectedIds = new Set(responsibleSelection.value.map((item) => Number(item)))
  return users.value.filter((item) => selectedIds.has(item.id))
})

const form = reactive({
  title: '',
  content: '',
  start_at: '',
  end_at: '',
  due_remind_days: 2,
  priority: 'medium',
  milestones: [],
  subtasks: [],
})

watch(responsibleSelection, () => {
  const selectedIds = new Set(responsibleSelection.value.map((item) => Number(item)))
  for (const item of form.subtasks) {
    if (!selectedIds.has(Number(item.assignee_id)) && responsibleOptions.value[0]) {
      item.assignee_id = responsibleOptions.value[0].id
    }
  }
}, { deep: true })

function nextSubtaskKey() {
  subtaskSeed.value += 1
  return `subtask-${Date.now()}-${subtaskSeed.value}`
}

function buildDefaultTaskDateTime(hour, minute = 0) {
  const now = new Date()
  now.setHours(hour, minute, 0, 0)
  return toDateTimeLocal(now)
}

function buildDefaultEndDateTime() {
  const now = new Date()
  const end = new Date()
  end.setHours(18, 0, 0, 0)
  if (end <= now) {
    end.setDate(end.getDate() + 1)
  }
  return toDateTimeLocal(end)
}

function subtasksForUser(userId) {
  return form.subtasks.filter((item) => Number(item.assignee_id) === Number(userId))
}

function addSubtask(userId) {
  if (!responsibleSelection.value.includes(String(userId))) {
    return
  }
  form.subtasks.push({
    id: null,
    local_key: nextSubtaskKey(),
    title: '',
    assignee_id: Number(userId),
  })
}

function removeSubtask(localKey) {
  form.subtasks = form.subtasks.filter((item) => item.local_key !== localKey)
}

function addMilestone() {
  form.milestones.push({
    name: '',
    planned_at: form.end_at || form.start_at || buildDefaultTaskDateTime(18),
    remind_offsets_text: '1',
  })
}

function removeMilestone(index) {
  form.milestones.splice(index, 1)
}

async function loadUsers() {
  const { data } = await http.get('/admin/users')
  users.value = data.filter((item) => item.is_active)
}

async function loadTask() {
  if (!isEdit.value) {
    form.start_at = toDateTimeLocal(new Date())
    form.end_at = buildDefaultEndDateTime()
    form.due_remind_days = 2
    return
  }
  const { data } = await http.get(`/tasks/${props.taskId}`)
  form.title = data.title
  form.content = data.content
  form.start_at = toDateTimeLocal(data.start_at)
  form.end_at = toDateTimeLocal(data.end_at)
  form.due_remind_days = Number(data.due_remind_days || 0)
  form.priority = data.priority
  responsibleSelection.value = data.members.map((item) => String(item.user_id))
  form.milestones = (data.milestones || []).map((item) => ({
    name: item.name,
    planned_at: toDateTimeLocal(item.planned_at),
    remind_offsets_text: Array.isArray(item.remind_offsets) ? item.remind_offsets.join(',') : '1',
  }))
  form.subtasks = (data.subtasks || []).map((item) => ({
    id: item.id,
    local_key: nextSubtaskKey(),
    title: item.title,
    assignee_id: item.assignee_id || data.members?.[0]?.user_id || Number(responsibleSelection.value[0]),
  }))
}

async function submit() {
  const responsibleIds = responsibleSelection.value.map((item) => Number(item)).filter(Boolean)
  if (responsibleIds.length === 0) {
    window.alert('请至少选择一位负责人')
    return
  }
  const startAt = toBackendDateTime(form.start_at)
  const createStartAt = isEdit.value ? startAt : toBackendDateTime(new Date())
  const endAt = toBackendDateTime(form.end_at)
  if (!createStartAt || !endAt) {
    window.alert('请填写完整的截止时间')
    return
  }
  const milestones = []
  for (let index = 0; index < form.milestones.length; index += 1) {
    const item = form.milestones[index]
    if (!item.name.trim() && !item.planned_at) {
      continue
    }
    const plannedAt = toBackendDateTime(item.planned_at)
    if (!item.name.trim() || !plannedAt) {
      window.alert(`第 ${index + 1} 个里程碑未填写完整`)
      return
    }
    milestones.push({
      name: item.name.trim(),
      planned_at: plannedAt,
      remind_offsets: item.remind_offsets_text
        .split(',')
        .map((value) => Number(value.trim()))
        .filter((value) => !Number.isNaN(value)),
      sort_order: index,
    })
  }
  const subtasks = []
  for (let index = 0; index < form.subtasks.length; index += 1) {
    const item = form.subtasks[index]
    if (!item.title.trim()) {
      window.alert(`第 ${index + 1} 个子任务内容不能为空`)
      return
    }
    subtasks.push({
      id: item.id || null,
      title: item.title.trim(),
      content: '',
      assignee_id: Number(item.assignee_id),
      sort_order: index,
      status: 'pending',
    })
  }
  const payload = {
    title: form.title,
    content: form.content,
    owner_id: responsibleIds[0],
    participant_ids: responsibleIds.slice(1),
    start_at: createStartAt,
    end_at: endAt,
    due_remind_days: Math.max(0, Number(form.due_remind_days || 0)),
    priority: form.priority,
    remark: '',
    milestones,
    subtasks,
  }
  submitting.value = true
  try {
    const { data } = isEdit.value
      ? await http.put(`/tasks/${props.taskId}`, payload)
      : await http.post('/tasks', payload)
    emit('saved', data)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadUsers()
  await loadTask()
})
</script>

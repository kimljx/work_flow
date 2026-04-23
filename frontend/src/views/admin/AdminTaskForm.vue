<template>
  <section class="page">
    <div class="panel">
      <div class="hero">
        <div>
          <h1>{{ isEdit ? '编辑任务' : '新建任务' }}</h1>
          <p>先确定主任务负责人，再通过按钮添加参与人员，并在同一区域内继续给成员分配子任务。</p>
        </div>
        <router-link class="button secondary" :to="backTarget">{{ backText }}</router-link>
      </div>

      <form class="page" @submit.prevent="submit">
        <div class="form-grid">
          <div>
            <label>任务标题</label>
            <input v-model="form.title" required />
          </div>
          <div>
            <label>负责人</label>
            <select v-model.number="form.owner_id" required>
              <option :value="0">请选择负责人</option>
              <option v-for="user in users" :key="user.id" :value="user.id">{{ user.name }}（{{ user.role_text }}）</option>
            </select>
          </div>
          <div>
            <label>开始时间</label>
            <input v-model="form.start_at" type="datetime-local" required />
          </div>
          <div>
            <label>结束时间</label>
            <input v-model="form.end_at" type="datetime-local" required />
          </div>
          <div>
            <label>到期前提醒天数</label>
            <input v-model.number="form.due_remind_days" type="number" min="0" />
            <div class="subtle-text">填 0 表示不自动提醒。</div>
          </div>
          <div>
            <label>优先级</label>
            <select v-model="form.priority">
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </div>
        </div>

        <div class="panel">
          <div class="section-head">
            <div>
              <h2>主任务参与人员与子任务</h2>
              <p>成员选中后即可在该成员卡片内直接添加子任务，不再拆成两个独立模块。</p>
            </div>
            <button type="button" class="button secondary" :disabled="!form.owner_id || submitting" @click="openParticipantPicker">
              添加参与人员
            </button>
          </div>

          <div v-if="!form.owner_id" class="muted-block">请先选择负责人，再添加参与人员和子任务。</div>
          <div v-else class="section-block">
            <article v-for="member in selectedTaskMembers" :key="member.id" class="participant-subtask-card">
              <div class="participant-subtask-head">
                <div>
                  <h3>{{ member.name }}</h3>
                  <div class="subtle-text">{{ member.roleText }} / {{ member.email || '未配置邮箱' }}</div>
                </div>
                <div class="toolbar">
                  <button type="button" class="button secondary small" :disabled="submitting" @click="addSubtaskForMember(member.id)">
                    添加子任务
                  </button>
                  <button
                    v-if="member.memberRole === 'participant'"
                    type="button"
                    class="button danger small"
                    :disabled="submitting"
                    @click="removeParticipant(member.id)"
                  >
                    移除成员
                  </button>
                </div>
              </div>

              <div class="subtle-text">
                {{ member.memberRole === 'owner' ? '负责人默认保留在主任务中，也可以直接给负责人分配子任务。' : '移除成员时，该成员名下的子任务也会一起移除。' }}
              </div>

              <div v-if="memberSubtasks(member.id).length === 0" class="muted-block">
                当前还没有分配给 {{ member.name }} 的子任务。
              </div>
              <div v-else class="section-block">
                <div class="subtask-card" v-for="(item, index) in memberSubtasks(member.id)" :key="item.local_key">
                  <div class="participant-subtask-row">
                    <strong>子任务 {{ index + 1 }}</strong>
                    <span :class="resolveSubtaskStatusMeta(item.status, item.status_text).tone">
                      {{ resolveSubtaskStatusMeta(item.status, item.status_text).label }}
                    </span>
                  </div>
                  <div class="form-grid">
                    <div>
                      <label>子任务标题</label>
                      <input v-model="item.title" placeholder="例如：整理原始数据" />
                    </div>
                    <div>
                      <label>状态</label>
                      <input :value="resolveSubtaskStatusMeta(item.status, item.status_text).label" disabled />
                      <div class="subtle-text">后续邮件回执会自动推进该成员名下子任务状态。</div>
                    </div>
                  </div>
                  <div>
                    <label>子任务内容</label>
                    <textarea v-model="item.content" rows="3" placeholder="补充执行要求、交付内容或注意事项" />
                  </div>
                  <div class="toolbar">
                    <button type="button" class="button danger small" :disabled="submitting" @click="removeSubtask(item.local_key)">删除子任务</button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </div>

        <div>
          <label>任务内容</label>
          <textarea v-model="form.content" rows="4" required />
        </div>

        <div>
          <label>备注</label>
          <textarea v-model="form.remark" rows="3" />
        </div>

        <div class="panel">
          <div class="hero">
            <div>
              <h2>里程碑</h2>
              <p>里程碑使用具体时间点管理，便于和主任务时间范围保持一致。</p>
            </div>
            <button type="button" class="button secondary" :disabled="submitting" @click="addMilestone">新增里程碑</button>
          </div>
          <div class="milestone-grid" v-for="(item, index) in form.milestones" :key="index">
            <input v-model="item.name" placeholder="里程碑名称" />
            <input v-model="item.planned_at" type="datetime-local" />
            <input v-model="item.remind_offsets_text" placeholder="提醒天数，如 1,3,5" />
            <button type="button" class="button danger" :disabled="submitting" @click="removeMilestone(index)">删除</button>
          </div>
        </div>

        <div class="toolbar">
          <button type="submit" :disabled="submitting">{{ submitting ? '正在提交...' : (isEdit ? '保存修改' : '创建任务') }}</button>
        </div>
      </form>
    </div>

    <div v-if="participantPickerOpen" class="modal-mask" @click.self="closeParticipantPicker">
      <div class="modal-card">
        <div class="section-head">
          <div>
            <h2>添加参与人员</h2>
            <p>勾选后点击“完成添加”，成员卡片和对应可分配子任务区域会同步出现。</p>
          </div>
          <button type="button" class="button secondary small" :disabled="submitting" @click="closeParticipantPicker">关闭</button>
        </div>
        <div class="member-pick-grid">
          <label class="member-pick-card" v-for="user in participantOptions" :key="user.id">
            <input type="checkbox" :value="String(user.id)" v-model="tempParticipantSelection" />
            <div>
              <strong>{{ user.name }}</strong>
              <div class="subtle-text">{{ user.role_text }} / {{ user.email }}</div>
            </div>
          </label>
        </div>
        <div class="toolbar modal-actions">
          <button type="button" class="button secondary" :disabled="submitting" @click="closeParticipantPicker">取消</button>
          <button type="button" :disabled="submitting" @click="applyParticipantPicker">完成添加</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { resolveSubtaskStatusMeta } from '../../constants/taskUi'
import { toBackendDateTime, toDateTimeLocal } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))
const users = ref([])
const participantSelection = ref([])
const tempParticipantSelection = ref([])
const participantPickerOpen = ref(false)
const submitting = ref(false)
const subtaskSeed = ref(0)

const form = reactive({
  title: '',
  content: '',
  owner_id: 0,
  start_at: '',
  end_at: '',
  due_remind_days: 0,
  priority: 'medium',
  remark: '',
  milestones: [],
  subtasks: [],
})

const participantOptions = computed(() => users.value.filter((item) => item.id !== form.owner_id))
const selectedTaskMembers = computed(() => {
  const memberIds = [Number(form.owner_id), ...participantSelection.value.map((item) => Number(item))]
  return memberIds
    .filter(Boolean)
    .map((id) => {
      const user = users.value.find((item) => item.id === id)
      if (!user) return null
      return {
        id: user.id,
        name: user.name,
        email: user.email,
        memberRole: user.id === Number(form.owner_id) ? 'owner' : 'participant',
        roleText: user.id === Number(form.owner_id) ? '负责人' : '参与人员',
      }
    })
    .filter(Boolean)
})
const backTarget = computed(() => route.query.from || (isEdit.value ? `/admin/tasks/${route.params.id}` : '/admin/tasks'))
const backText = computed(() => '返回上页')

watch(
  () => form.owner_id,
  () => {
    participantSelection.value = participantSelection.value.filter((id) => String(id) !== String(form.owner_id))
    tempParticipantSelection.value = participantSelection.value.slice()
    pruneSubtasksByMembers()
  }
)

watch(
  participantSelection,
  () => {
    pruneSubtasksByMembers()
  },
  { deep: true }
)

function buildDefaultTaskDateTime(hour, minute = 0) {
  const now = new Date()
  now.setHours(hour, minute, 0, 0)
  return toDateTimeLocal(now)
}

function nextSubtaskKey() {
  subtaskSeed.value += 1
  return `subtask-${Date.now()}-${subtaskSeed.value}`
}

function selectedMemberIdsSet() {
  return new Set(selectedTaskMembers.value.map((item) => Number(item.id)))
}

function pruneSubtasksByMembers() {
  const availableIds = selectedMemberIdsSet()
  form.subtasks = form.subtasks.filter((item) => availableIds.has(Number(item.assignee_id)))
}

function memberSubtasks(memberId) {
  return form.subtasks.filter((item) => Number(item.assignee_id) === Number(memberId))
}

function openParticipantPicker() {
  tempParticipantSelection.value = participantSelection.value.slice()
  participantPickerOpen.value = true
}

function closeParticipantPicker() {
  participantPickerOpen.value = false
}

function applyParticipantPicker() {
  participantSelection.value = tempParticipantSelection.value.slice()
  participantPickerOpen.value = false
}

function removeParticipant(memberId) {
  participantSelection.value = participantSelection.value.filter((item) => Number(item) !== Number(memberId))
  form.subtasks = form.subtasks.filter((item) => Number(item.assignee_id) !== Number(memberId))
}

function addSubtaskForMember(memberId) {
  form.subtasks.push({
    id: null,
    local_key: nextSubtaskKey(),
    title: '',
    content: '',
    assignee_id: Number(memberId),
    sort_order: form.subtasks.length,
    status: 'pending',
    status_text: '待开始',
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
  if (!isEdit.value) return
  const { data } = await http.get(`/tasks/${route.params.id}`)
  form.title = data.title
  form.content = data.content
  form.owner_id = data.members.find((item) => item.member_role === 'owner')?.user_id || 0
  form.start_at = toDateTimeLocal(data.start_at)
  form.end_at = toDateTimeLocal(data.end_at)
  form.due_remind_days = Number(data.due_remind_days || 0)
  form.priority = data.priority
  form.remark = data.remark || ''
  participantSelection.value = data.members
    .filter((item) => item.member_role === 'participant')
    .map((item) => String(item.user_id))
  tempParticipantSelection.value = participantSelection.value.slice()
  form.milestones = data.milestones.map((item) => ({
    name: item.name,
    planned_at: toDateTimeLocal(item.planned_at),
    remind_offsets_text: Array.isArray(item.remind_offsets) ? item.remind_offsets.join(',') : item.remind_offsets,
  }))
  form.subtasks = (data.subtasks || []).map((item) => ({
    id: item.id,
    local_key: nextSubtaskKey(),
    title: item.title,
    content: item.content || '',
    assignee_id: item.assignee_id,
    sort_order: item.sort_order || 0,
    status: item.status || 'pending',
    status_text: item.status_text || '待开始',
  }))
}

async function submit() {
  const startAt = toBackendDateTime(form.start_at)
  const endAt = toBackendDateTime(form.end_at)
  if (!startAt || !endAt) {
    window.alert('开始时间或结束时间格式无效')
    return
  }

  const milestones = []
  for (let index = 0; index < form.milestones.length; index += 1) {
    const item = form.milestones[index]
    const plannedAt = toBackendDateTime(item.planned_at)
    if (!plannedAt) {
      window.alert(`第 ${index + 1} 个里程碑时间格式无效`)
      return
    }
    milestones.push({
      name: item.name,
      planned_at: plannedAt,
      remind_offsets: item.remind_offsets_text
        .split(',')
        .map((value) => Number(value.trim()))
        .filter((value) => !Number.isNaN(value)),
      sort_order: index,
    })
  }

  const normalizedSubtasks = form.subtasks.map((item, index) => ({
    id: item.id || null,
    title: item.title,
    content: item.content || '',
    assignee_id: Number(item.assignee_id),
    sort_order: index,
    status: item.status || 'pending',
  }))

  for (let index = 0; index < normalizedSubtasks.length; index += 1) {
    const item = normalizedSubtasks[index]
    if (!item.title.trim()) {
      window.alert(`第 ${index + 1} 个子任务标题不能为空`)
      return
    }
    if (!item.assignee_id) {
      window.alert(`第 ${index + 1} 个子任务缺少执行人`)
      return
    }
  }

  const payload = {
    title: form.title,
    content: form.content,
    owner_id: Number(form.owner_id),
    participant_ids: participantSelection.value.map((item) => Number(item)),
    start_at: startAt,
    end_at: endAt,
    due_remind_days: Math.max(0, Number(form.due_remind_days || 0)),
    priority: form.priority,
    remark: form.remark,
    milestones,
    subtasks: normalizedSubtasks,
  }

  submitting.value = true
  try {
    if (isEdit.value) {
      await http.put(`/tasks/${route.params.id}`, payload)
      router.push(route.query.from || `/admin/tasks/${route.params.id}`)
      return
    }
    const { data } = await http.post('/tasks', payload)
    router.push({
      path: `/admin/tasks/${data.id}`,
      query: {
        from: route.query.from || '/admin/tasks',
      },
    })
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadUsers()
  await loadTask()
  if (!isEdit.value && !form.start_at) {
    form.start_at = buildDefaultTaskDateTime(9)
    form.end_at = buildDefaultTaskDateTime(18)
  }
  if (form.milestones.length === 0) {
    addMilestone()
  }
})
</script>

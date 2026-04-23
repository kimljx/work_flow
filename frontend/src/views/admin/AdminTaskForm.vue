<template>
  <section class="page">
    <div class="panel">
      <div class="hero">
        <div>
          <h1>{{ isEdit ? '编辑任务' : '新建任务' }}</h1>
          <p>配置任务基础信息、负责人、参与者和多个里程碑节点。</p>
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
            <label>开始日期</label>
            <input v-model="form.start_at" type="date" required />
          </div>
          <div>
            <label>结束日期</label>
            <input v-model="form.end_at" type="date" required />
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
          <div>
            <label>参与者</label>
            <div class="multi-select">
              <button type="button" class="button secondary" @click="participantDropdownOpen = !participantDropdownOpen">
                {{ participantSummary }}
              </button>
              <div v-if="participantDropdownOpen" class="multi-select-menu">
                <label class="multi-select-item" v-for="user in participantOptions" :key="user.id">
                  <input type="checkbox" :value="String(user.id)" v-model="participantSelection" />
                  <span>{{ user.name }}</span>
                </label>
                <div class="subtle-text" v-if="participantOptions.length === 0">暂无可选参与者</div>
              </div>
            </div>
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
              <p>里程碑按日期管理，默认按当日 24:00 进入提醒判定。</p>
            </div>
            <button type="button" class="button secondary" @click="addMilestone">新增里程碑</button>
          </div>
          <div class="milestone-grid" v-for="(item, index) in form.milestones" :key="index">
            <input v-model="item.name" placeholder="里程碑名称" />
            <input v-model="item.planned_at" type="date" />
            <input v-model="item.remind_offsets_text" placeholder="提醒天数，如 1,3,5" />
            <button type="button" class="button danger" @click="removeMilestone(index)">删除</button>
          </div>
        </div>

        <div class="toolbar">
          <button type="submit">{{ isEdit ? '保存修改' : '创建任务' }}</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { toBackendEndOfDay, toBackendStartOfDay, toDateOnly } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))
const users = ref([])
const participantSelection = ref([])
const participantDropdownOpen = ref(false)
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
})

const participantOptions = computed(() => users.value.filter((item) => item.id !== form.owner_id))
const backTarget = computed(() => route.query.from || (isEdit.value ? `/admin/tasks/${route.params.id}` : '/admin/tasks'))
const backText = computed(() => '返回上页')
const participantSummary = computed(() => {
  if (participantSelection.value.length === 0) return '请选择参与者'
  const names = participantSelection.value
    .map((id) => users.value.find((user) => String(user.id) === String(id))?.name)
    .filter(Boolean)
  return names.length > 0 ? `已选择：${names.join('、')}` : '请选择参与者'
})

watch(
  () => form.owner_id,
  () => {
    participantSelection.value = participantSelection.value.filter(
      (id) => String(id) !== String(form.owner_id)
    )
  }
)

function toDisplayDateFromEndBoundary(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  if (date.getHours() === 0 && date.getMinutes() === 0 && date.getSeconds() === 0) {
    date.setDate(date.getDate() - 1)
  }
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function addMilestone() {
  form.milestones.push({
    name: '',
    planned_at: form.end_at || form.start_at || '',
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
  form.start_at = toDateOnly(data.start_at)
  form.end_at = toDisplayDateFromEndBoundary(data.end_at)
  form.due_remind_days = Number(data.due_remind_days || 0)
  form.priority = data.priority
  form.remark = data.remark || ''
  participantSelection.value = data.members
    .filter((item) => item.member_role === 'participant')
    .map((item) => String(item.user_id))
  form.milestones = data.milestones.map((item) => ({
    name: item.name,
    planned_at: toDisplayDateFromEndBoundary(item.planned_at),
    remind_offsets_text: Array.isArray(item.remind_offsets) ? item.remind_offsets.join(',') : item.remind_offsets,
  }))
}

async function submit() {
  const startAt = toBackendStartOfDay(form.start_at)
  const endAt = toBackendEndOfDay(form.end_at)
  if (!startAt || !endAt) {
    window.alert('开始日期或结束日期格式无效')
    return
  }

  const milestones = []
  for (let index = 0; index < form.milestones.length; index += 1) {
    const item = form.milestones[index]
    const plannedAt = toBackendEndOfDay(item.planned_at)
    if (!plannedAt) {
      window.alert(`第 ${index + 1} 个里程碑日期格式无效`)
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
  }
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
}

onMounted(async () => {
  await loadUsers()
  await loadTask()
  if (!isEdit.value && !form.start_at) {
    const today = new Date()
    const pad = (item) => String(item).padStart(2, '0')
    const value = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`
    form.start_at = value
    form.end_at = value
  }
  if (form.milestones.length === 0) {
    addMilestone()
  }
})
</script>

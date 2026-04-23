<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">任务模块</div>
        <h1 class="workspace-title">任务排期与执行视图</h1>
        <p class="workspace-subtitle">集中查看任务起止时间、优先级、当前状态和送达情况，支持直接进入详情、提醒和删除。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="{ path: '/admin/import-export', query: { from: route.fullPath } }">导入任务</router-link>
        <router-link class="button" :to="{ path: '/admin/tasks/new', query: { from: route.fullPath } }">新建任务</router-link>
      </div>
    </div>

    <div class="panel filter-shell">
      <div class="filter-grid">
        <input v-model="keyword" placeholder="搜索任务标题或负责人" />
        <select v-model="status">
          <option value="">全部状态</option>
          <option value="not_started">未开始</option>
          <option value="in_progress">进行中</option>
          <option value="done">已完成</option>
          <option value="canceled">已取消</option>
        </select>
      </div>
      <div class="filter-summary">当前展示 {{ filteredTasks.length }} 条任务</div>
    </div>

    <div class="task-stack">
      <article v-if="pagedTasks.length === 0" class="panel empty-state">
        <h2>暂无符合条件的任务</h2>
        <p>可以调整筛选条件，或直接创建新的任务计划。</p>
      </article>

      <article
        v-for="task in pagedTasks"
        :key="task.id"
        class="task-work-card"
      >
        <div :class="statusUi(task).dot"></div>
        <div class="task-work-main">
          <div class="task-work-heading">
            <div>
              <div class="task-work-kicker">任务编号 #{{
                task.id
              }}</div>
              <h2>{{ task.title }}</h2>
              <p>{{ task.content }}</p>
            </div>
            <span :class="resolvePriorityMeta(task.priority).tone">
              {{ resolvePriorityMeta(task.priority).label }}
            </span>
          </div>

          <div class="task-info-grid">
            <div class="info-cell">
              <span class="info-label">负责人</span>
              <strong>{{ task.owner_name || '-' }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">参与成员</span>
              <strong>{{ task.participant_count }} 人</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">开始时间</span>
              <strong>{{ formatDateTime(task.start_at) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">结束时间</span>
              <strong>{{ formatDateTime(task.end_at) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">计划用时</span>
              <strong>{{ formatMinutes(task.planned_minutes) }}</strong>
            </div>
            <div class="info-cell">
              <span class="info-label">通知送达</span>
              <strong>{{ task.delivered_count }}/{{ task.notification_total }}</strong>
            </div>
          </div>
        </div>

        <div class="task-work-side">
          <span :class="statusUi(task).tone">{{ statusUi(task).text }}</span>
          <div class="task-side-note">优先级 {{ task.priority_text }}</div>
          <div class="task-side-note">提醒设置 {{ task.due_remind_days > 0 ? `提前 ${task.due_remind_days} 天` : '未开启' }}</div>
          <div class="toolbar task-actions">
            <router-link class="button secondary" :to="{ path: `/admin/tasks/${task.id}`, query: { from: route.fullPath } }">详情</router-link>
            <button class="button secondary" @click="remind(task.id)">提醒</button>
            <button class="button danger" @click="removeTask(task.id)">删除</button>
          </div>
        </div>
      </article>
    </div>

    <AppPagination v-model="page" :total="filteredTasks.length" :page-size="pageSize" />
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { resolvePriorityMeta, resolveTaskStatusTone } from '../../constants/taskUi'
import { formatDateTime, formatMinutes } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const tasks = ref([])
const keyword = ref('')
const status = ref('')
const page = ref(1)
const pageSize = 8

const filteredTasks = computed(() =>
  tasks.value.filter((item) => {
    const query = keyword.value.trim()
    const matchKeyword =
      !query ||
      item.title.includes(query) ||
      (item.owner_name || '').includes(query)
    const matchStatus = !status.value || item.main_status === status.value
    return matchKeyword && matchStatus
  })
)

const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})

watch([keyword, status], () => {
  page.value = 1
})

function statusUi(task) {
  return resolveTaskStatusTone(task)
}

async function loadTasks() {
  const { data } = await http.get('/tasks')
  tasks.value = data
}

async function handleRouteRefresh() {
  if (route.query.refresh !== 'import') {
    return
  }
  await loadTasks()
  const successCount = Number(route.query.import_success_count || 0)
  const failureCount = Number(route.query.import_failure_count || 0)
  window.alert(`任务导入完成：成功 ${successCount} 条，失败 ${failureCount} 条`)
  router.replace({ path: route.path, query: {} })
}

async function remind(taskId) {
  if (!window.confirm('确认要对该任务发送手动提醒吗？')) return
  await http.post(`/tasks/${taskId}/remind`)
  window.alert('已创建提醒通知。')
  await loadTasks()
}

async function removeTask(taskId) {
  if (!window.confirm('删除任务会保留审计记录，是否继续？')) return
  await http.delete(`/tasks/${taskId}`)
  await loadTasks()
}

onMounted(async () => {
  await loadTasks()
  await handleRouteRefresh()
})
</script>

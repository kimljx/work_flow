<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>任务列表</h1>
        <p>按关键词和状态筛选任务，支持查看详情、手动提醒和删除。</p>
      </div>
      <div class="toolbar">
        <button class="button secondary" @click="runDueRemind">执行到期提醒</button>
        <router-link class="button" to="/admin/tasks/new">新建任务</router-link>
      </div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <input v-model="keyword" placeholder="输入任务标题关键词" />
        <select v-model="status">
          <option value="">全部状态</option>
          <option value="not_started">未开始</option>
          <option value="in_progress">进行中</option>
          <option value="done">已完成</option>
          <option value="canceled">已取消</option>
        </select>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>任务名称</th>
            <th>负责人</th>
            <th>参与人数</th>
            <th>状态</th>
            <th>已送达/总通知</th>
            <th>计划用时</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedTasks.length === 0">
            <td colspan="7">当前没有符合条件的任务。</td>
          </tr>
          <tr v-for="task in pagedTasks" :key="task.id">
            <td>{{ task.title }}</td>
            <td>{{ task.owner_name || '-' }}</td>
            <td>{{ task.participant_count }}</td>
            <td>{{ task.status_text }}</td>
            <td>{{ task.delivered_count }}/{{ task.notification_total }}</td>
            <td>{{ formatMinutes(task.planned_minutes) }}</td>
            <td>
              <div class="toolbar">
                <router-link class="button secondary" :to="`/admin/tasks/${task.id}`">详情</router-link>
                <button class="button secondary" @click="remind(task.id)">提醒</button>
                <button class="button danger" @click="removeTask(task.id)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="filteredTasks.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { formatMinutes } from '../../utils/format'

const tasks = ref([])
const keyword = ref('')
const status = ref('')
const page = ref(1)
const pageSize = 8

const filteredTasks = computed(() =>
  tasks.value.filter((item) => {
    const matchKeyword = !keyword.value || item.title.includes(keyword.value)
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

async function loadTasks() {
  const { data } = await http.get('/tasks')
  tasks.value = data
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

async function runDueRemind() {
  const { data } = await http.post('/tasks/due-remind/run')
  window.alert(data.message || '到期提醒已执行')
  await loadTasks()
}

onMounted(loadTasks)
</script>

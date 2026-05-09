<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>我的任务</h1>
        <p>这里只展示你负责或参与的任务，页面保持只读，不提供管理操作。</p>
      </div>
    </div>
    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>负责人</th>
            <th>结束时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedTasks.length === 0">
            <td colspan="5">当前没有分配给你的任务。</td>
          </tr>
          <tr v-for="task in pagedTasks" :key="task.id">
            <td>{{ task.title }}</td>
            <td>{{ task.status_text }}</td>
            <td>{{ task.owner_name || '-' }}</td>
            <td>
              <div>{{ formatDateTime(task.end_at) }}</div>
              <div v-if="delayStatus(task).text" :class="delayStatus(task).className">{{ delayStatus(task).text }}</div>
            </td>
            <td><router-link class="button secondary" :to="`/member/tasks/${task.id}`">查看详情</router-link></td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="tasks.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { formatDateTime } from '../../utils/format'

const tasks = ref([])
const page = ref(1)
const pageSize = 8

const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return tasks.value.slice(start, start + pageSize)
})

function delayStatus(task) {
  if (!task || ['done', 'canceled'].includes(task.main_status)) {
    return { text: '', className: '' }
  }
  const delayDays = Number(task.delay_days || 0)
  if (delayDays > 0) {
    return { text: `已延期${delayDays}天`, className: 'error-text task-delay-text' }
  }
  const endDate = new Date(task.end_at)
  if (Number.isNaN(endDate.getTime())) {
    return { text: '', className: '' }
  }
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const endDay = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate()).getTime()
  const daysToDue = Math.ceil((endDay - startOfToday) / 86400000)
  if (daysToDue < 0) {
    return { text: `已延期${Math.abs(daysToDue)}天`, className: 'error-text task-delay-text' }
  }
  if (daysToDue >= 0 && daysToDue <= 3) {
    return { text: '即将延期', className: 'warning-text task-delay-text' }
  }
  return { text: '', className: '' }
}

watch(
  () => tasks.value.length,
  () => {
    page.value = 1
  }
)

onMounted(async () => {
  const { data } = await http.get('/tasks')
  tasks.value = data
})
</script>

<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>我的通知</h1>
        <p>查看与你相关的邮件和 QAX 通知记录，以及送达和已读状态。</p>
      </div>
    </div>
    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>任务</th>
            <th>渠道</th>
            <th>类型</th>
            <th>状态</th>
            <th>送达/已读</th>
            <th>通知时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedNotifications.length === 0">
            <td colspan="6">当前没有通知记录。</td>
          </tr>
          <tr v-for="item in pagedNotifications" :key="item.id">
            <td>{{ item.task_title || '-' }}</td>
            <td>{{ item.channel_text }}</td>
            <td>{{ item.notify_type_text || notifyTypeText(item.notify_type) }}</td>
            <td>{{ item.status_text }}</td>
            <td>{{ item.delivered_count }}/{{ item.read_count }}</td>
            <td>{{ formatDateTime(item.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="notifications.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatDateTime } from '../../utils/format'

const notifications = ref([])
const page = ref(1)
const pageSize = 8

const pagedNotifications = computed(() => {
  const start = (page.value - 1) * pageSize
  return notifications.value.slice(start, start + pageSize)
})

watch(
  () => notifications.value.length,
  () => {
    page.value = 1
  }
)

onMounted(async () => {
  const { data } = await http.get('/notifications')
  notifications.value = data
})
</script>

<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>审计日志</h1>
        <p>记录关键操作的时间和对象，便于后续追踪与核查。</p>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>动作</th>
            <th>对象</th>
            <th>对象 ID</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedLogs.length === 0">
            <td colspan="4">当前没有审计日志。</td>
          </tr>
          <tr v-for="item in pagedLogs" :key="item.id">
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>{{ item.action_type }}</td>
            <td>{{ item.target_type }}</td>
            <td>{{ item.target_id ?? '-' }}</td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="logs.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { formatDateTime } from '../../utils/format'

const logs = ref([])
const page = ref(1)
const pageSize = 10

const pagedLogs = computed(() => {
  const start = (page.value - 1) * pageSize
  return logs.value.slice(start, start + pageSize)
})

watch(
  () => logs.value.length,
  () => {
    page.value = 1
  }
)

onMounted(async () => {
  const { data } = await http.get('/audit-logs')
  logs.value = data
})
</script>

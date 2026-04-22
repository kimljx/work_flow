<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>{{ text.title }}</h1>
        <p>{{ text.subtitle }}</p>
      </div>
      <div class="toolbar">
        <button class="button secondary" @click="loadEvents" :disabled="loading">
          {{ loading ? text.loading : text.refresh }}
        </button>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>{{ text.createdAt }}</th>
            <th>{{ text.from }}</th>
            <th>{{ text.subject }}</th>
            <th>{{ text.template }}</th>
            <th>{{ text.processStatus }}</th>
            <th>{{ text.action }}</th>
            <th>{{ text.task }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedEvents.length === 0">
            <td colspan="7">{{ text.empty }}</td>
          </tr>
          <tr v-for="item in pagedEvents" :key="item.id">
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>{{ item.from_addr }}</td>
            <td>
              <div>{{ item.subject || '-' }}</div>
              <div class="subtle-text">{{ item.body_digest || '-' }}</div>
            </td>
            <td>
              <div>{{ item.template_name || text.unmatched }}</div>
              <div class="subtle-text" v-if="item.notify_type_text">{{ item.notify_type_text }}</div>
            </td>
            <td>{{ item.process_status_text }}</td>
            <td>
              <div>{{ item.action_type || '-' }}</div>
              <div class="subtle-text" v-if="item.action_status_text">{{ item.action_status_text }}</div>
              <pre v-if="item.action_result_json" class="code-block">{{ item.action_result_json }}</pre>
            </td>
            <td>
              <router-link v-if="item.task_id" :to="`/admin/tasks/${item.task_id}`">{{ item.task_title || `${text.taskPrefix}${item.task_id}` }}</router-link>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="events.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { formatDateTime } from '../../utils/format'

const text = {
  title: '最近扫描邮件',
  subtitle: '查看系统最近从收件箱扫描到的邮件、匹配到的模板，以及已经落下的业务动作。',
  loading: '刷新中...',
  refresh: '刷新列表',
  createdAt: '时间',
  from: '发件人',
  subject: '主题',
  template: '模板',
  processStatus: '处理状态',
  action: '业务动作',
  task: '关联任务',
  empty: '当前还没有扫描到邮件。',
  unmatched: '未匹配模板',
  taskPrefix: '任务 #',
}

const events = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = 10

const pagedEvents = computed(() => {
  const start = (page.value - 1) * pageSize
  return events.value.slice(start, start + pageSize)
})

async function loadEvents() {
  loading.value = true
  try {
    const { data } = await http.get('/admin/mail/events')
    events.value = data
  } finally {
    loading.value = false
  }
}

onMounted(loadEvents)
</script>

<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>延期审批中心</h1>
        <p>支持管理员在 Web 端直接审批延期申请。若其他审批先行生效，系统会返回明确冲突提示。</p>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>任务</th>
            <th>申请人</th>
            <th>申请原因</th>
            <th>原截止</th>
            <th>申请截止</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedRequests.length === 0">
            <td colspan="7">当前没有延期审批记录。</td>
          </tr>
          <tr v-for="item in pagedRequests" :key="item.id">
            <td>{{ item.task_title }}</td>
            <td>{{ item.applicant_name }}</td>
            <td>{{ item.apply_reason }}</td>
            <td>{{ formatDateTime(item.original_deadline) }}</td>
            <td>{{ formatDateTime(item.proposed_deadline) }}</td>
            <td>{{ item.approval_status_text }}</td>
            <td>
              <div class="toolbar" v-if="item.approval_status === 'PENDING'">
                <button @click="approve(item)">同意</button>
                <button class="button danger" @click="reject(item)">拒绝</button>
              </div>
              <span v-else>已处理</span>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="requests.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { formatDateTime, toBackendDateTime } from '../../utils/format'

const requests = ref([])
const page = ref(1)
const pageSize = 8

const pagedRequests = computed(() => {
  const start = (page.value - 1) * pageSize
  return requests.value.slice(start, start + pageSize)
})

watch(
  () => requests.value.length,
  () => {
    page.value = 1
  }
)

async function loadRequests() {
  const { data } = await http.get('/delay-requests/pending')
  requests.value = data
}

async function approve(item) {
  const approvedDeadline = window.prompt('请输入新的截止时间（格式：2026-05-01T18:00）', '')
  if (!approvedDeadline) return
  const approvedDeadlineValue = toBackendDateTime(approvedDeadline)
  if (!approvedDeadlineValue) {
    window.alert('截止时间格式无效')
    return
  }
  const remark = window.prompt('请输入审批备注（可选）', '') || ''
  try {
    await http.post(`/delay-requests/${item.id}/approve`, {
      action: 'APPROVE',
      request_id: `web-${item.id}-${Date.now()}`,
      version: item.version,
      remark,
      approved_deadline: approvedDeadlineValue,
    })
    await loadRequests()
  } catch (error) {
    window.alert(error.response?.data?.detail || '审批失败')
  }
}

async function reject(item) {
  const remark = window.prompt('请输入拒绝原因', '') || ''
  try {
    await http.post(`/delay-requests/${item.id}/approve`, {
      action: 'REJECT',
      request_id: `web-${item.id}-${Date.now()}`,
      version: item.version,
      remark,
      approved_deadline: null,
    })
    await loadRequests()
  } catch (error) {
    window.alert(error.response?.data?.detail || '审批失败')
  }
}

onMounted(loadRequests)
</script>

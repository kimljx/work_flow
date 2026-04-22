<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>管理员看板</h1>
        <p>集中查看任务推进、延期风险、通知效果与常用操作入口。</p>
      </div>
      <div class="toolbar">
        <router-link class="button" to="/admin/tasks/new">新建任务</router-link>
        <router-link class="button secondary" to="/admin/import-export">导入导出</router-link>
        <router-link class="button secondary" to="/admin/delay-requests">待审批延期</router-link>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card" v-for="item in stats" :key="item.label">
        <div>{{ item.label }}</div>
        <strong>{{ item.value }}</strong>
      </div>
    </div>

    <div class="panel">
      <h2>图表说明</h2>
      <p>V1 版本先打通真实统计数据与核心管理动作。后续我们可以在这里补上负责人完成趋势、状态分布图和延期趋势图。</p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../../api/http'

const summary = ref({
  task_total: 0,
  in_progress_total: 0,
  done_total: 0,
  canceled_total: 0,
  delayed_total: 0,
  email_success_rate: 0,
  qax_delivery_rate: 0,
  qax_read_rate: 0,
  retry_total: 0,
})

const stats = computed(() => [
  { label: '任务总数', value: summary.value.task_total },
  { label: '进行中', value: summary.value.in_progress_total },
  { label: '已完成', value: summary.value.done_total },
  { label: '已取消', value: summary.value.canceled_total },
  { label: '延期任务', value: summary.value.delayed_total },
  { label: '邮件发送成功率', value: `${summary.value.email_success_rate}%` },
  { label: '即时消息送达率', value: `${summary.value.qax_delivery_rate}%` },
  { label: '即时消息已读率', value: `${summary.value.qax_read_rate}%` },
  { label: '失败重试数', value: summary.value.retry_total },
])

onMounted(async () => {
  const { data } = await http.get('/dashboard/summary')
  summary.value = data
})
</script>

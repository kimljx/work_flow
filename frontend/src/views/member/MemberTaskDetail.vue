<template>
  <section class="page" v-if="task">
    <div class="panel hero">
      <div>
        <h1>{{ task.title }}</h1>
        <p>{{ task.status_text }}，截止时间：{{ formatDateTime(task.end_at) }}</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="backPath">返回上页</router-link>
      </div>
    </div>

    <div class="panel">
      <h2>任务内容</h2>
      <p>{{ task.content }}</p>
      <p>开始时间：{{ formatDateTime(task.start_at) }}</p>
      <p>结束时间：{{ formatDateTime(task.end_at) }}</p>
      <p>计划用时：{{ formatMinutes(task.planned_minutes) }}</p>
      <p>实际用时：{{ formatMinutes(task.actual_minutes) }}</p>
      <p>子任务数量：{{ task.subtask_count || 0 }}</p>
      <p>到期提醒：{{ task.due_remind_days > 0 ? `提前 ${task.due_remind_days} 天` : '未开启' }}</p>
    </div>

    <div class="panel">
      <h2>里程碑</h2>
      <table class="table">
        <thead>
          <tr>
            <th>节点</th>
            <th>时间</th>
            <th>提醒规则</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in task.milestones" :key="item.id">
            <td>{{ item.name }}</td>
            <td>{{ formatDateTime(item.planned_at) }}</td>
            <td>提前 {{ item.remind_offsets.join('、') }} 天</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>子任务</h2>
      <table class="table">
        <thead>
          <tr>
            <th>子任务标题</th>
            <th>状态</th>
            <th>执行人</th>
            <th>内容</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="task.subtasks.length === 0">
            <td colspan="4">当前没有子任务。</td>
          </tr>
          <tr v-for="item in task.subtasks" :key="item.id">
            <td>{{ item.title }}</td>
            <td>
              <span :class="resolveSubtaskStatusMeta(item.status, item.status_text).tone">
                {{ resolveSubtaskStatusMeta(item.status, item.status_text).label }}
              </span>
            </td>
            <td>
              <div>{{ item.assignee_name || '-' }}</div>
              <div class="subtle-text">{{ item.assignee_email || '未配置邮箱' }}</div>
            </td>
            <td>{{ item.content || '暂无说明' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>通知状态</h2>
      <table class="table">
        <thead>
          <tr>
            <th>渠道</th>
            <th>类型</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in task.notifications" :key="item.id">
            <td>{{ item.channel_text }}</td>
            <td>{{ item.notify_type_text }}</td>
            <td>{{ item.status_text }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import http from '../../api/http'
import { resolveSubtaskStatusMeta } from '../../constants/taskUi'
import { formatDateTime, formatMinutes } from '../../utils/format'

const route = useRoute()
const task = ref(null)
const backPath = computed(() => route.query.from || '/member/tasks')

onMounted(async () => {
  const { data } = await http.get(`/tasks/${route.params.id}`)
  task.value = data
})
</script>

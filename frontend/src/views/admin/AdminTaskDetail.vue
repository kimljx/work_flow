<template>
  <section class="page" v-if="task">
    <div class="panel hero">
      <div>
        <h1>{{ task.title }}</h1>
        <p>{{ task.status_text }}，负责人：{{ task.owner_name || '-' }}</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="`/admin/tasks/${task.id}/edit`">编辑计划</router-link>
        <button class="button secondary" @click="remindTask">手动提醒</button>
      </div>
    </div>

    <div class="panel detail-grid">
      <div>
        <h2>基础信息</h2>
        <p>任务内容：{{ task.content }}</p>
        <p>优先级：{{ task.priority_text }}</p>
        <p>计划用时：{{ formatMinutes(task.planned_minutes) }}</p>
        <p>实际用时：{{ formatMinutes(task.actual_minutes) }}</p>
        <p>到期提醒：{{ task.due_remind_days > 0 ? `提前 ${task.due_remind_days} 天` : '未开启' }}</p>
        <p>状态锁定：{{ task.state_locked ? '已锁定' : '未锁定' }}</p>
      </div>
      <div>
        <h2>状态操作</h2>
        <div class="toolbar">
          <select v-model="statusForm.main_status">
            <option value="not_started">未开始</option>
            <option value="in_progress">进行中</option>
            <option value="done">已完成</option>
            <option value="canceled">已取消</option>
          </select>
          <input v-model="statusForm.remark" placeholder="状态备注" />
          <button @click="changeStatus">更新状态</button>
        </div>
        <div class="toolbar">
          <button class="button secondary" v-if="!task.state_locked" @click="toggleLock(true)">锁定状态</button>
          <button class="button secondary" v-else @click="toggleLock(false)">解除锁定</button>
          <button class="button danger" @click="removeTask">删除任务</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>成员信息</h2>
      <table class="table">
        <thead>
          <tr>
            <th>姓名</th>
            <th>邮箱</th>
            <th>角色</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="member in task.members" :key="member.id">
            <td>{{ member.name }}</td>
            <td>{{ member.email }}</td>
            <td>{{ member.member_role_text }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>里程碑</h2>
      <table class="table">
        <thead>
          <tr>
            <th>节点</th>
            <th>计划时间</th>
            <th>提醒设置</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="milestone in task.milestones" :key="milestone.id">
            <td>{{ milestone.name }}</td>
            <td>{{ formatDateTime(milestone.planned_at) }}</td>
            <td>提前 {{ milestone.remind_offsets.join('、') }} 天</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>通知记录</h2>
      <table class="table">
        <thead>
          <tr>
            <th>渠道</th>
            <th>类型</th>
            <th>状态</th>
            <th>送达/已读</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in task.notifications" :key="item.id">
            <td>{{ item.channel_text }}</td>
            <td>{{ item.notify_type_text }}</td>
            <td>{{ item.status_text }}</td>
            <td>{{ item.delivered_count }}/{{ item.read_count }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>延期记录</h2>
      <table class="table">
        <thead>
          <tr>
            <th>申请人</th>
            <th>申请原因</th>
            <th>原截止</th>
            <th>申请截止</th>
            <th>审批状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="task.delay_requests.length === 0">
            <td colspan="5">当前没有延期申请记录。</td>
          </tr>
          <tr v-for="item in task.delay_requests" :key="item.id">
            <td>{{ item.applicant_name }}</td>
            <td>{{ item.apply_reason }}</td>
            <td>{{ formatDateTime(item.original_deadline) }}</td>
            <td>{{ formatDateTime(item.proposed_deadline) }}</td>
            <td>{{ item.approval_status_text }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>状态时间线</h2>
      <ul class="timeline">
        <li v-for="item in task.events" :key="item.id">
          <strong>{{ item.to_status_text }}</strong>
          <span>{{ formatDateTime(item.created_at) }}</span>
          <div>{{ item.remark || '无备注' }}</div>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { formatDateTime, formatMinutes } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const task = ref(null)
const statusForm = reactive({
  main_status: 'not_started',
  remark: '',
})

async function loadTask() {
  const { data } = await http.get(`/tasks/${route.params.id}`)
  task.value = data
  statusForm.main_status = data.main_status
}

async function remindTask() {
  if (!window.confirm('确认要发送手动提醒吗？')) return
  await http.post(`/tasks/${route.params.id}/remind`)
  await loadTask()
}

async function changeStatus() {
  if (!window.confirm('确认要修改任务状态吗？本操作将写入审计日志。')) return
  await http.post(`/tasks/${route.params.id}/status`, statusForm)
  await loadTask()
}

async function toggleLock(shouldLock) {
  if (!window.confirm(`确认要${shouldLock ? '锁定' : '解除锁定'}任务状态吗？`)) return
  await http.post(`/tasks/${route.params.id}/${shouldLock ? 'lock' : 'unlock'}`)
  await loadTask()
}

async function removeTask() {
  if (!window.confirm('确认删除该任务吗？删除后仍会保留审计日志。')) return
  await http.delete(`/tasks/${route.params.id}`)
  router.push('/admin/tasks')
}

onMounted(loadTask)
</script>

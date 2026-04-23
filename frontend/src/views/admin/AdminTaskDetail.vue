<template>
  <section class="page" v-if="task">
    <div class="panel hero">
      <div>
        <h1>{{ task.title }}</h1>
        <p>{{ task.status_text }}，负责人：{{ task.owner_name || '-' }}</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="backTarget">返回上页</router-link>
        <router-link class="button secondary" :to="{ path: `/admin/tasks/${task.id}/edit`, query: { from: route.fullPath } }">编辑计划</router-link>
        <button class="button secondary" @click="remindTask">手动提醒</button>
      </div>
    </div>

    <div class="panel detail-grid">
      <div>
        <h2>基础信息</h2>
        <p>任务内容：{{ task.content }}</p>
        <p>开始时间：{{ formatDateTime(task.start_at) }}</p>
        <p>结束时间：{{ formatDateTime(task.end_at) }}</p>
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
            <th>送达</th>
            <th>已读</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="task.notifications.length === 0">
            <td colspan="7">当前没有通知记录。</td>
          </tr>
          <tr v-for="item in task.notifications" :key="item.id">
            <td>{{ item.channel_text }}</td>
            <td>{{ item.notify_type_text }}</td>
            <td>{{ item.status_text }}</td>
            <td>{{ item.delivered_count }}/{{ item.recipient_total }}</td>
            <td>{{ item.read_count }}</td>
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>
              <router-link class="button secondary small" :to="{ path: `/admin/notifications/${item.id}`, query: { from: route.fullPath } }">查看详情</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>延期记录</h2>
      <div v-if="task.delay_requests.length === 0" class="empty-state approval-empty">
        <h3>当前没有延期申请记录</h3>
        <p>成员提交延期申请后，会在这里同步展示审批结果和处理信息。</p>
      </div>
      <div v-else class="section-block">
        <article
          v-for="item in task.delay_requests"
          :key="item.id"
          class="approval-card task-delay-card"
        >
          <div class="approval-avatar">
            {{ applicantInitial(item.applicant_name) }}
          </div>

          <div class="approval-main">
            <div class="approval-topline">
              <div>
                <div class="approval-user">{{ item.applicant_name || '未知申请人' }}</div>
                <div class="subtle-text">申请编号 #{{ item.id }}</div>
              </div>
              <span :class="delayStatusTone(item.approval_status)">{{ item.approval_status_text }}</span>
            </div>

            <div class="approval-meta-grid">
              <div class="info-cell">
                <span class="info-label">原截止时间</span>
                <strong>{{ formatDateTime(item.original_deadline) }}</strong>
              </div>
              <div class="info-cell">
                <span class="info-label">申请截止时间</span>
                <strong>{{ formatDateTime(item.proposed_deadline) }}</strong>
              </div>
              <div class="info-cell">
                <span class="info-label">最终截止时间</span>
                <strong>{{ formatDateTime(item.approved_deadline || item.proposed_deadline) }}</strong>
              </div>
            </div>

            <div class="approval-reason">
              <span class="info-label">申请原因</span>
              <p>{{ item.apply_reason || '未填写申请原因' }}</p>
            </div>
          </div>

          <div class="approval-action task-delay-summary">
            <label>审批人</label>
            <div>{{ item.approver_name || '待处理' }}</div>
            <label>审批渠道</label>
            <div>{{ decisionChannelText(item.decided_by_channel) }}</div>
            <label>审批时间</label>
            <div>{{ formatDateTime(item.decided_at) }}</div>
            <label>审批备注</label>
            <div class="task-delay-remark">{{ item.approve_remark || '暂无审批备注' }}</div>
            <div class="toolbar approval-action-buttons">
              <router-link class="button secondary small" :to="{ path: '/admin/delay-requests', query: { from: route.fullPath } }">前往审批工作台</router-link>
            </div>
          </div>
        </article>
      </div>
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
const backTarget = route.query.from || '/admin/tasks'

function applicantInitial(name) {
  return (name || '成员').slice(0, 2)
}

function delayStatusTone(status) {
  if (status === 'APPROVED') return 'status-tone status-tone-success'
  if (status === 'REJECTED') return 'status-tone status-tone-danger'
  return 'status-tone status-tone-warning'
}

function decisionChannelText(channel) {
  if (channel === 'web') return '系统审批'
  if (channel === 'mail') return '邮件审批'
  return '待处理'
}

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
  router.push(backTarget)
}

onMounted(loadTask)
</script>

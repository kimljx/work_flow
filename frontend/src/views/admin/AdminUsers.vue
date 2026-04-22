<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>用户管理</h1>
        <p>仅管理员可配置成员和管理员账号，支持新增、编辑、启停和重置密码。</p>
      </div>
    </div>

    <div class="panel">
      <div class="form-grid">
        <div><label>用户名</label><input v-model="form.username" :disabled="Boolean(editingId)" /></div>
        <div><label>姓名</label><input v-model="form.name" /></div>
        <div>
          <label>角色</label>
          <select v-model="form.role">
            <option value="admin">管理员</option>
            <option value="member">成员</option>
          </select>
        </div>
        <div><label>邮箱</label><input v-model="form.email" /></div>
        <div><label>IP 地址</label><input v-model="form.ip_address" /></div>
      </div>
      <div class="toolbar">
        <button @click="submitUser">{{ editingId ? '保存用户' : '新增用户' }}</button>
        <button class="button secondary" v-if="editingId" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>姓名</th>
            <th>角色</th>
            <th>邮箱</th>
            <th>IP</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in pagedUsers" :key="item.id">
            <td>{{ item.username }}</td>
            <td>{{ item.name }}</td>
            <td>{{ item.role_text }}</td>
            <td>{{ item.email }}</td>
            <td>{{ item.ip_address }}</td>
            <td>{{ item.is_active ? '启用' : '禁用' }}</td>
            <td>
              <div class="toolbar">
                <button class="button secondary" @click="editUser(item)">编辑</button>
                <button class="button secondary" v-if="item.is_active" @click="toggleUser(item, false)">禁用</button>
                <button class="button secondary" v-else @click="toggleUser(item, true)">启用</button>
                <button class="button danger" @click="resetPassword(item.id)">重置密码</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" :total="users.length" :page-size="pageSize" />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'

const users = ref([])
const editingId = ref(null)
const page = ref(1)
const pageSize = 8
const form = reactive({
  username: '',
  name: '',
  role: 'member',
  email: '',
  ip_address: '',
  is_active: true,
})

const pagedUsers = computed(() => {
  const start = (page.value - 1) * pageSize
  return users.value.slice(start, start + pageSize)
})

watch(
  () => users.value.length,
  () => {
    page.value = 1
  }
)

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    username: '',
    name: '',
    role: 'member',
    email: '',
    ip_address: '',
    is_active: true,
  })
}

async function loadUsers() {
  const { data } = await http.get('/admin/users')
  users.value = data
}

function editUser(item) {
  editingId.value = item.id
  Object.assign(form, item)
}

async function submitUser() {
  if (editingId.value) {
    await http.put(`/admin/users/${editingId.value}`, {
      role: form.role,
      name: form.name,
      email: form.email,
      ip_address: form.ip_address,
      is_active: form.is_active,
    })
  } else {
    await http.post('/admin/users', {
      username: form.username,
      role: form.role,
      name: form.name,
      email: form.email,
      ip_address: form.ip_address,
    })
  }
  resetForm()
  await loadUsers()
}

async function toggleUser(item, enabled) {
  if (!window.confirm(`确认要${enabled ? '启用' : '禁用'}该用户吗？本操作将记录审计日志。`)) return
  await http.post(`/admin/users/${item.id}/${enabled ? 'enable' : 'disable'}`)
  await loadUsers()
}

async function resetPassword(userId) {
  if (!window.confirm('确认要将该用户密码重置为默认密码吗？')) return
  await http.post(`/admin/users/${userId}/reset-password`)
  window.alert('密码已重置为默认密码。')
}

onMounted(loadUsers)
</script>

<template>
  <section class="page">
    <div class="panel login-panel">
      <div class="hero">
        <div>
          <h1>系统登录</h1>
          <p>请输入管理员分配的账号和密码。首次部署后可使用默认管理员账号进入系统。</p>
        </div>
      </div>
      <form class="page" @submit.prevent="submit">
        <div>
          <label>用户名</label>
          <input v-model="form.username" />
        </div>
        <div>
          <label>密码</label>
          <input v-model="form.password" type="password" />
        </div>
        <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
        <p class="error-text" v-if="error">{{ error }}</p>
        <div class="muted-block">
          <div>默认管理员账号：`admin`</div>
          <div>默认密码：`ChangeMe123`</div>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: 'admin', password: 'ChangeMe123' })
const error = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    error.value = ''
    await auth.login(form)
    router.push(auth.isAdmin ? '/admin/dashboard' : '/member/tasks')
  } catch (err) {
    error.value = err.response?.data?.detail || '用户名或密码错误'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="login-page">
    <div class="login-page-overlay" />
    <header class="login-brand" aria-label="平台标识">
      <span class="login-brand-mark" :style="{ backgroundImage: `url(${stateGridMark})` }" aria-hidden="true" />
      <span class="login-brand-name">{{ LOGIN_BRAND }}</span>
      <span class="login-brand-divider" aria-hidden="true" />
      <span class="login-brand-platform">{{ APP_NAME }}</span>
    </header>
    <main class="login-main">
      <form class="login-card" @submit.prevent="submit">
        <div class="login-card-heading">
          <h1>欢迎登录</h1>
          <p>{{ APP_NAME }}</p>
        </div>
        <label class="login-field">
          <span>用户名</span>
          <input v-model.trim="form.username" autocomplete="username" placeholder="请输入用户名" />
        </label>
        <label class="login-field">
          <span>密码</span>
          <input v-model="form.password" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </label>
        <p v-if="error" class="error-text login-error">{{ error }}</p>
        <button class="login-submit" type="submit" :disabled="loading">
          {{ loading ? '正在登录...' : '登录' }}
        </button>
      </form>
    </main>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { APP_NAME, LOGIN_BRAND } from '../../constants/app'
import stateGridMark from '../../assets/images/state-grid-logo.svg'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
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

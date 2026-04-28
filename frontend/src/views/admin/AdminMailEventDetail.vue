<template>
  <section class="page" v-if="detail">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">邮件详情</div>
        <h1 class="workspace-title">{{ detail.template_name || `匹配邮件 #${detail.id}` }}</h1>
        <p class="workspace-subtitle">查看匹配到的邮件内容、命中的模板和落库后的业务动作。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" to="/admin/mail-events">返回邮件列表</router-link>
        <router-link v-if="detail.task_id" class="button" :to="`/admin/tasks/${detail.task_id}`">查看任务</router-link>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">发件人</span>
        <strong>{{ detail.from_addr }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">处理状态</span>
        <strong>{{ detail.process_status_text }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">匹配类型</span>
        <strong>{{ detail.notify_type_text || notifyTypeText(detail.notify_type) }}</strong>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">收取时间</span>
        <strong>{{ formatDateTime(detail.created_at) }}</strong>
      </div>
    </div>

    <div class="panel">
      <h2>邮件主题</h2>
      <p>{{ detail.subject || '-' }}</p>
    </div>

    <div class="detail-grid">
      <div class="panel">
        <div class="section-head">
          <div>
            <h2>匹配内容</h2>
            <p>默认先看结构化摘要，避免原始邮件正文直接铺满页面。</p>
          </div>
          <button class="button secondary small" @click="showOriginalMail = true">查看原始邮件</button>
        </div>
        <pre class="detail-pre">{{ decodedBodyDigest || '暂无内容摘要' }}</pre>
      </div>
      <div class="panel">
        <h2>命中模板</h2>
        <div class="detail-summary-list">
          <div class="detail-summary-item">
            <span>模板名称</span>
            <strong>{{ detail.template_name || '-' }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>模板类型</span>
            <strong>{{ detail.template_kind || '-' }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>动作类型</span>
            <strong>{{ detail.action_type || '-' }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>动作状态</span>
            <strong>{{ detail.action_status_text || '-' }}</strong>
          </div>
        </div>
        <pre class="detail-pre detail-pre-subtle">{{ decodedTemplateContent || '当前没有可展示的模板正文' }}</pre>
      </div>
    </div>

    <div class="panel">
      <h2>业务动作结果</h2>
      <pre class="detail-pre dark">{{ prettyActionResult }}</pre>
    </div>

    <div v-if="showOriginalMail" class="modal-mask" @click.self="showOriginalMail = false">
      <div class="modal-card mail-original-modal">
        <div class="section-head">
          <div>
            <h2>原始邮件</h2>
            <p>这里展示系统收件后解析出的完整正文，默认隐藏以减少详情页干扰。</p>
          </div>
          <button class="button secondary small" @click="showOriginalMail = false">关闭</button>
        </div>
        <pre class="detail-pre mail-original-pre">{{ decodedOriginalBody || '当前没有可展示的原始邮件正文' }}</pre>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import http from '../../api/http'
import { notifyTypeText } from '../../constants/notifyTypes'
import { formatDateTime } from '../../utils/format'

const route = useRoute()
const detail = ref(null)
const showOriginalMail = ref(false)

const prettyActionResult = computed(() => {
  if (!detail.value?.action_result_json) return '暂无业务动作结果'
  try {
    return JSON.stringify(JSON.parse(detail.value.action_result_json), null, 2)
  } catch (error) {
    return detail.value.action_result_json
  }
})

const decodedBodyDigest = computed(() => decodeMailText(detail.value?.body_digest || ''))
const decodedTemplateContent = computed(() => decodeMailText(detail.value?.content || ''))
const decodedOriginalBody = computed(() => decodeMailText(detail.value?.original_body || ''))

function decodeMailText(content) {
  // 邮件正文可能混入 HTML 实体，这里统一转回普通文本，避免把 &nbsp; 直接展示给用户。
  if (!content) return ''
  const container = document.createElement('textarea')
  container.innerHTML = content
  return container.value.replace(/\u00a0/g, ' ')
}

async function loadDetail() {
  const { data } = await http.get(`/admin/mail/events/${route.params.id}`)
  detail.value = data
}

onMounted(loadDetail)
</script>

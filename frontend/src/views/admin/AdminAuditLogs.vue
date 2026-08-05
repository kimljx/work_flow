<template>
  <section class="page">
    <div class="panel workspace-header">
      <div>
        <div class="workspace-eyebrow">系统日志</div>
        <h1 class="workspace-title">系统维护日志中心</h1>
        <p class="workspace-subtitle">
          集中查看管理员操作、后台任务、异常结果和自动清理记录，便于系统管理员排障与追溯。
        </p>
      </div>
      <div class="toolbar">
        <button class="button secondary" :disabled="cleaning" @click="handleCleanup">
          {{ cleaning ? '清理中...' : '清理过期日志' }}
        </button>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card compact">
        <span class="metric-label">日志总数</span>
        <strong>{{ logs.length }}</strong>
        <div class="subtle-text">当前已载入的系统日志记录</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">错误/告警</span>
        <strong>{{ warningTotal }}</strong>
        <div class="subtle-text">`WARNING` 与 `ERROR` 级别日志</div>
      </div>
      <div class="stat-card compact">
        <span class="metric-label">后台任务</span>
        <strong>{{ schedulerTotal }}</strong>
        <div class="subtle-text">来自定时任务与维护线程的记录</div>
      </div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <input v-model.trim="keyword" class="input" placeholder="搜索动作、模块、摘要、操作人或对象" />
        <div class="multi-filter">
          <button class="button secondary small" type="button" @click="levelFilterOpen = !levelFilterOpen">{{ selectedLevelText }}</button>
          <div v-if="levelFilterOpen" class="multi-filter-menu">
            <label class="multi-filter-all">
              <span>全选</span>
              <input type="checkbox" :checked="isAllLevelsSelected" @change="toggleAllLevels" />
            </label>
            <label v-for="item in levelOptions" :key="item">
              <span>{{ item }}</span>
              <input v-model="levelFilter" type="checkbox" :value="item" />
            </label>
          </div>
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>等级</th>
            <th>模块</th>
            <th>摘要</th>
            <th>操作人</th>
            <th>对象</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedLogs.length === 0">
            <td colspan="7">当前没有符合条件的系统日志。</td>
          </tr>
          <tr v-for="item in pagedLogs" :key="item.id">
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td><span :class="levelClass(item.log_level)">{{ item.log_level }}</span></td>
            <td>{{ item.module_name || '-' }}</td>
            <td>{{ item.message || item.action_type }}</td>
            <td>{{ item.operator_name || '系统后台' }}</td>
            <td>{{ formatTarget(item) }}</td>
            <td>
              <button class="button secondary small" @click="openDetail(item)">查看详情</button>
            </td>
          </tr>
        </tbody>
      </table>
      <AppPagination v-model="page" v-model:page-size="pageSize" :total="filteredLogs.length" />
    </div>

    <div v-if="detailLog" class="modal-mask">
      <div class="modal-card system-log-modal">
        <div class="section-head compact">
          <div>
            <h2>系统日志详情</h2>
            <p>查看完整日志上下文、来源信息和变更快照，便于维护排查。</p>
          </div>
          <button class="button secondary small" @click="closeDetail">关闭</button>
        </div>

        <div class="system-log-modal-grid">
          <div class="info-cell">
            <span class="info-label">时间</span>
            <strong>{{ formatDateTime(detailLog.created_at) }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">等级</span>
            <strong>{{ detailLog.log_level }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">模块</span>
            <strong>{{ detailLog.module_name || '-' }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">动作类型</span>
            <strong>{{ detailLog.action_type || '-' }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">操作人</span>
            <strong>{{ detailLog.operator_name || '系统后台' }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">对象</span>
            <strong>{{ formatTarget(detailLog) }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">来源 IP</span>
            <strong>{{ detailLog.source_ip || '-' }}</strong>
          </div>
          <div class="info-cell">
            <span class="info-label">摘要</span>
            <strong>{{ detailLog.message || detailLog.action_type }}</strong>
          </div>
        </div>

        <div class="system-log-modal-stack">
          <div class="info-cell">
            <span class="info-label">详情扩展</span>
            <pre class="system-log-pre">{{ formatJson(detailLog.detail_json) }}</pre>
          </div>
          <div class="info-cell">
            <span class="info-label">变更前</span>
            <pre class="system-log-pre">{{ formatJson(detailLog.before_json) }}</pre>
          </div>
          <div class="info-cell">
            <span class="info-label">变更后</span>
            <pre class="system-log-pre">{{ formatJson(detailLog.after_json) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../../components/AppPagination.vue'
import { formatDateTime } from '../../utils/format'

const logs = ref([])
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const levelFilter = ref([])
const levelFilterOpen = ref(false)
const levelOptions = ['INFO', 'WARNING', 'ERROR']
const cleaning = ref(false)
const detailLog = ref(null)

const warningTotal = computed(() => logs.value.filter((item) => ['WARNING', 'ERROR'].includes(item.log_level)).length)
const schedulerTotal = computed(() => logs.value.filter((item) => (item.module_name || '').startsWith('scheduler.')).length)
const isAllLevelsSelected = computed(() => levelFilter.value.length === levelOptions.length)
const selectedLevelText = computed(() => levelFilter.value.length ? levelFilter.value.join('、') : '全部等级')

const filteredLogs = computed(() => {
  const text = keyword.value.toLowerCase()
  return logs.value.filter((item) => {
    if (levelFilter.value.length && !levelFilter.value.includes(item.log_level)) return false
    if (!text) return true
    const source = [
      item.action_type,
      item.message,
      item.module_name,
      item.operator_name,
      item.target_type,
      item.source_ip,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return source.includes(text)
  })
})

const pagedLogs = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredLogs.value.slice(start, start + pageSize.value)
})

watch(
  () => [logs.value.length, keyword.value, levelFilter.value],
  () => {
    page.value = 1
  },
  { deep: true }
)

function toggleAllLevels() {
  levelFilter.value = isAllLevelsSelected.value ? [] : [...levelOptions]
}

function levelClass(level) {
  if (level === 'ERROR') return 'status-tone status-tone-danger'
  if (level === 'WARNING') return 'status-tone status-tone-warning'
  return 'status-tone status-tone-primary'
}

function formatTarget(item) {
  if (item.target_id == null) return item.target_type || '-'
  return `${item.target_type} #${item.target_id}`
}

function formatJson(text) {
  try {
    return JSON.stringify(JSON.parse(text || '{}'), null, 2)
  } catch (error) {
    return text || '{}'
  }
}

function openDetail(item) {
  detailLog.value = item
}

function closeDetail() {
  detailLog.value = null
}

async function loadLogs() {
  const { data } = await http.get('/system-logs')
  logs.value = data
}

async function handleCleanup() {
  if (!window.confirm('确认立即清理超过保留期的系统日志吗？')) return
  cleaning.value = true
  try {
    await http.post('/system-logs/cleanup')
    await loadLogs()
  } finally {
    cleaning.value = false
  }
}

function closeFloatingFilters(event) {
  if (event.target?.closest?.('.multi-filter')) return
  levelFilterOpen.value = false
}

onMounted(() => {
  document.addEventListener('click', closeFloatingFilters)
  loadLogs()
})

onUnmounted(() => {
  document.removeEventListener('click', closeFloatingFilters)
})
</script>

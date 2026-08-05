<template>
  <div class="task-editor-shell">
    <div class="section-head">
      <div>
        <h2>导入任务</h2>
        <p>按当前 Excel 模板导入任务，缺失字段会自动补默认值。</p>
      </div>
      <button type="button" class="button secondary small" :disabled="submitting" @click="$emit('cancel')">关闭</button>
    </div>

    <div class="panel">
      <div class="toolbar">
        <button :disabled="submitting" @click="downloadFile('/tasks/import-template', 'task-import-template.xlsx')">下载模板</button>
      </div>
      <div class="form-grid">
        <div>
          <label>选择 Excel 文件</label>
          <input type="file" accept=".xlsx" :disabled="submitting" @change="handleFileChange" />
          <div class="subtle-text">{{ selectedFile ? selectedFile.name : '仅支持 .xlsx 文件' }}</div>
        </div>
      </div>
      <div class="toolbar modal-actions">
        <button class="button secondary" :disabled="submitting" @click="$emit('cancel')">取消</button>
        <button :disabled="!selectedFile || submitting" @click="submitImport(false)">{{ submitting ? '导入中...' : '开始导入' }}</button>
      </div>
    </div>

    <div v-if="duplicatePreview?.needs_confirmation" class="duplicate-warning-card">
      <h3>检测到高重复导入</h3>
      <p>{{ duplicatePreview.message }}</p>
      <div class="toolbar">
        <button :disabled="submitting" @click="submitImport(true)">继续导入</button>
        <button class="button secondary" :disabled="submitting" @click="duplicatePreview = null">取消</button>
      </div>
    </div>

    <div v-if="result" class="panel">
      <div class="stats">
        <div class="stat-card compact">
          <span class="metric-label">成功</span>
          <strong>{{ result.success_count || 0 }}</strong>
        </div>
        <div class="stat-card compact">
          <span class="metric-label">失败</span>
          <strong>{{ result.failure_count || 0 }}</strong>
        </div>
      </div>
      <div class="muted-block">{{ result.message }}</div>
      <table v-if="(result.failures || []).length > 0" class="table">
        <thead>
          <tr>
            <th>行号</th>
            <th>任务</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in pagedFailures" :key="`${item.row_number}-${item.title}`">
            <td>{{ item.row_number }}</td>
            <td>{{ item.title || '-' }}</td>
            <td>{{ item.reason }}</td>
          </tr>
        </tbody>
      </table>
      <AppPagination
        v-if="(result.failures || []).length > 0"
        v-model="failurePage"
        v-model:page-size="failurePageSize"
        :total="(result.failures || []).length"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import http from '../../api/http'
import AppPagination from '../AppPagination.vue'

const emit = defineEmits(['cancel', 'imported'])

const selectedFile = ref(null)
const submitting = ref(false)
const result = ref(null)
const duplicatePreview = ref(null)
const failurePage = ref(1)
const failurePageSize = ref(20)

const pagedFailures = computed(() => {
  const failures = result.value?.failures || []
  const start = (failurePage.value - 1) * failurePageSize.value
  return failures.slice(start, start + failurePageSize.value)
})

function handleFileChange(event) {
  const [file] = event.target.files || []
  selectedFile.value = file || null
  duplicatePreview.value = null
}

async function downloadFile(url, filename) {
  const response = await http.get(url, { responseType: 'blob' })
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(blobUrl)
}

async function submitImport(confirmDuplicate) {
  if (!selectedFile.value) {
    return
  }
  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('confirm_duplicate', confirmDuplicate ? 'true' : 'false')
  submitting.value = true
  try {
    const { data } = await http.post('/tasks/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    if (data.needs_confirmation) {
      duplicatePreview.value = data
      return
    }
    duplicatePreview.value = null
    result.value = data
    failurePage.value = 1
    selectedFile.value = null
    emit('imported', data)
  } finally {
    submitting.value = false
  }
}

watch(result, () => {
  failurePage.value = 1
})
</script>

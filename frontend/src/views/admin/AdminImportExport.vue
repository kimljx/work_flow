<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>导入导出</h1>
        <p>下载任务导入 Excel 模板，上传后系统会按任务创建规则校验字段，并回显成功数量和失败行。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="backPath">返回上页</router-link>
      </div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <button @click="downloadFile('/tasks/import-template', 'task-import-template.xlsx')">下载 Excel 导入模板</button>
        <button class="button secondary" @click="downloadFile('/reports/export', 'task-report.csv')">导出任务报表</button>
      </div>
      <div class="muted-block">
        模板中已包含任务字段、填写说明和示例数据。请优先下载模板后填写，再上传 `.xlsx` 文件。
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>导入任务</h2>
          <p>上传 Excel 模板后，系统会自动校验负责人、参与者、时间格式、优先级和里程碑字段。</p>
        </div>
      </div>

      <div class="form-grid">
        <div>
          <label>选择 Excel 文件</label>
          <input type="file" accept=".xlsx" @change="handleFileChange" />
          <div class="subtle-text">{{ selectedFile ? `当前文件：${selectedFile.name}` : '仅支持 .xlsx 文件' }}</div>
        </div>
      </div>

      <div class="toolbar">
        <button :disabled="!selectedFile || submitting" @click="submitImport">
          {{ submitting ? '正在导入...' : '开始导入' }}
        </button>
      </div>

      <div v-if="result" class="section-block">
        <div class="stats">
          <div class="stat-card compact">
            <span class="metric-label">成功导入</span>
            <strong>{{ result.success_count || 0 }}</strong>
          </div>
          <div class="stat-card compact">
            <span class="metric-label">失败行数</span>
            <strong>{{ result.failure_count || 0 }}</strong>
          </div>
        </div>

        <div class="muted-block">{{ result.message }}</div>

        <table class="table" v-if="(result.failures || []).length > 0">
          <thead>
            <tr>
              <th>Excel 行号</th>
              <th>任务标题</th>
              <th>失败原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in result.failures" :key="`${item.row_number}-${item.title}`">
              <td>{{ item.row_number }}</td>
              <td>{{ item.title || '-' }}</td>
              <td>{{ item.reason }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'

const route = useRoute()
const router = useRouter()
const backPath = computed(() => route.query.from || '/admin/tasks')
const selectedFile = ref(null)
const submitting = ref(false)
const result = ref(null)

function handleFileChange(event) {
  const [file] = event.target.files || []
  selectedFile.value = file || null
}

async function submitImport() {
  if (!selectedFile.value) {
    window.alert('请先选择要导入的 Excel 文件')
    return
  }

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  submitting.value = true
  try {
    const { data } = await http.post('/tasks/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    result.value = data
    // 导入成功后回到任务列表，由列表页根据 query 参数完成刷新与提示。
    await router.push({
      path: '/admin/tasks',
      query: {
        refresh: 'import',
        import_success_count: String(data.success_count || 0),
        import_failure_count: String(data.failure_count || 0),
      },
    })
  } catch (error) {
    window.alert(error.response?.data?.detail || '导入失败，请检查模板内容')
  } finally {
    submitting.value = false
  }
}

async function downloadFile(url, filename) {
  try {
    const response = await http.get(url, {
      responseType: 'blob',
    })
    const blobUrl = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    link.click()
    window.URL.revokeObjectURL(blobUrl)
  } catch (error) {
    window.alert(error.response?.data?.detail || '下载失败，请稍后重试')
  }
}
</script>

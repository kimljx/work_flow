<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>导入导出</h1>
        <p>下载任务导入 Excel 模板、查看导入历史，并在高重叠导入时进行二次确认，避免重复导入。</p>
      </div>
      <div class="toolbar">
        <router-link class="button secondary" :to="backPath">返回上页</router-link>
      </div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <button :disabled="submitting" @click="downloadFile('/tasks/import-template', 'task-import-template.xlsx')">下载 Excel 导入模板</button>
        <button class="button secondary" :disabled="submitting" @click="downloadFile('/reports/export', 'task-report.csv')">导出任务报表</button>
      </div>
      <div class="muted-block">
        模板中已包含主任务、里程碑、子任务字段和填写说明。导入时负责人、参与人员和子任务执行人都应填写系统中的姓名，而不是用户名。
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>导入任务</h2>
          <p>上传 Excel 模板后，系统会自动校验姓名、时间格式、优先级、里程碑和子任务字段，并在高重叠时先提醒确认。</p>
        </div>
      </div>

      <div class="form-grid">
        <div>
          <label>选择 Excel 文件</label>
          <input type="file" accept=".xlsx" :disabled="submitting" @change="handleFileChange" />
          <div class="subtle-text">{{ selectedFile ? `当前文件：${selectedFile.name}` : '仅支持 .xlsx 文件' }}</div>
        </div>
      </div>

      <div class="toolbar">
        <button :disabled="!selectedFile || submitting" @click="submitImport(false)">
          {{ submitting ? '正在导入...' : '开始导入' }}
        </button>
      </div>

      <div v-if="duplicatePreview?.needs_confirmation" class="duplicate-warning-card">
        <h3>检测到高度重复导入</h3>
        <p>{{ duplicatePreview.message }}</p>
        <div class="detail-summary-list">
          <div class="detail-summary-item">
            <span>重叠条数</span>
            <strong>{{ duplicatePreview.overlap_count }}</strong>
          </div>
          <div class="detail-summary-item">
            <span>重叠比例</span>
            <strong>{{ Math.round((duplicatePreview.overlap_rate || 0) * 100) }}%</strong>
          </div>
        </div>
        <div v-if="(duplicatePreview.overlap_samples || []).length > 0" class="section-block">
          <h3>重叠样例</h3>
          <table class="table">
            <thead>
              <tr>
                <th>当前 Excel 行</th>
                <th>任务标题</th>
                <th>负责人</th>
                <th>结束时间</th>
                <th>历史批次</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in duplicatePreview.overlap_samples" :key="`${item.current_row_number}-${item.title}`">
                <td>{{ item.current_row_number || '-' }}</td>
                <td>{{ item.title || '-' }}</td>
                <td>{{ item.owner_name || '-' }}</td>
                <td>{{ item.end_at || '-' }}</td>
                <td>{{ item.history_filename || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="toolbar">
          <button :disabled="!selectedFile || submitting" @click="submitImport(true)">确认继续导入</button>
          <button class="button secondary" :disabled="submitting" @click="duplicatePreview = null">取消本次导入</button>
        </div>
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
          <div class="stat-card compact">
            <span class="metric-label">历史重叠</span>
            <strong>{{ result.overlap_count || 0 }}</strong>
          </div>
        </div>

        <div class="muted-block">{{ result.message }}</div>

        <table class="table" v-if="(result.overlap_samples || []).length > 0">
          <thead>
            <tr>
              <th>重叠样例</th>
              <th>负责人</th>
              <th>结束时间</th>
              <th>历史批次</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in result.overlap_samples" :key="`result-${item.current_row_number}-${item.title}`">
              <td>{{ item.title || '-' }}（第 {{ item.current_row_number || '-' }} 行）</td>
              <td>{{ item.owner_name || '-' }}</td>
              <td>{{ item.end_at || '-' }}</td>
              <td>{{ item.history_filename || '-' }}</td>
            </tr>
          </tbody>
        </table>

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

    <div class="panel">
      <div class="section-head">
        <div>
          <h2>导入历史</h2>
          <p>用于回看最近导入批次，判断是否已导过同一批数据。</p>
        </div>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>导入时间</th>
            <th>文件名</th>
            <th>操作人</th>
            <th>总行数</th>
            <th>成功</th>
            <th>失败</th>
            <th>重叠</th>
            <th>重复确认</th>
            <th>明细</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="importHistories.length === 0">
            <td colspan="9">当前还没有导入历史。</td>
          </tr>
          <tr v-for="item in importHistories" :key="item.id">
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>{{ item.filename }}</td>
            <td>{{ item.operator_name || '-' }}</td>
            <td>{{ item.total_rows }}</td>
            <td>{{ item.success_count }}</td>
            <td>{{ item.failure_count }}</td>
            <td>{{ item.overlap_count }}</td>
            <td>{{ item.confirmed_duplicate ? '已确认' : '否' }}</td>
            <td>
              <button
                v-if="(item.overlap_samples || []).length > 0 || (item.failure_samples || []).length > 0"
                class="button secondary small"
                @click="openHistoryDetail(item)"
              >
                查看详情
              </button>
              <span v-else class="subtle-text">无</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selectedHistory" class="modal-mask" @click.self="closeHistoryDetail">
      <div class="modal-card">
        <div class="section-head">
          <div>
            <h2>导入批次详情</h2>
            <p>查看该批次的导入结果、重复风险和失败摘要，便于判断是否需要补录或回滚。</p>
          </div>
          <button class="button secondary small" @click="closeHistoryDetail">关闭</button>
        </div>

        <div class="stats">
          <div class="stat-card compact">
            <span class="metric-label">文件名</span>
            <strong>{{ selectedHistory.filename || '-' }}</strong>
          </div>
          <div class="stat-card compact">
            <span class="metric-label">操作人</span>
            <strong>{{ selectedHistory.operator_name || '-' }}</strong>
          </div>
          <div class="stat-card compact">
            <span class="metric-label">导入时间</span>
            <strong>{{ formatDateTime(selectedHistory.created_at) }}</strong>
          </div>
          <div class="stat-card compact">
            <span class="metric-label">重复确认</span>
            <strong>{{ selectedHistory.confirmed_duplicate ? '已确认继续导入' : '未触发确认' }}</strong>
          </div>
        </div>

        <div class="history-detail-layout">
          <div class="panel">
            <h3>重叠样例</h3>
            <table class="table" v-if="(selectedHistory.overlap_samples || []).length > 0">
              <thead>
                <tr>
                  <th>Excel 行</th>
                  <th>任务标题</th>
                  <th>负责人</th>
                  <th>历史批次</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sample in selectedHistory.overlap_samples" :key="`${selectedHistory.id}-${sample.current_row_number}-${sample.title}`">
                  <td>{{ sample.current_row_number || '-' }}</td>
                  <td>{{ sample.title || '-' }}</td>
                  <td>{{ sample.owner_name || '-' }}</td>
                  <td>{{ sample.history_filename || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="muted-block">该批次没有命中重叠样例。</div>
          </div>

          <div class="panel">
            <h3>失败摘要</h3>
            <table class="table" v-if="(selectedHistory.failure_samples || []).length > 0">
              <thead>
                <tr>
                  <th>Excel 行</th>
                  <th>任务标题</th>
                  <th>失败原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sample in selectedHistory.failure_samples" :key="`${selectedHistory.id}-${sample.row_number}-${sample.title}`">
                  <td>{{ sample.row_number || '-' }}</td>
                  <td>{{ sample.title || '-' }}</td>
                  <td>{{ sample.reason || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="muted-block">该批次没有失败记录。</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { formatDateTime } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const backPath = computed(() => route.query.from || '/admin/tasks')
const selectedFile = ref(null)
const submitting = ref(false)
const result = ref(null)
const duplicatePreview = ref(null)
const importHistories = ref([])
const selectedHistory = ref(null)

/**
 * 处理本地 Excel 文件选择，并清空旧的预检结果。
 * @param {Event} event 文件选择事件。
 * @returns {void}
 */
function handleFileChange(event) {
  const [file] = event.target.files || []
  selectedFile.value = file || null
  duplicatePreview.value = null
}

/**
 * 拉取最近导入批次列表。
 * @returns {Promise<void>}
 */
async function loadHistories() {
  const { data } = await http.get('/tasks/import-histories')
  importHistories.value = data
}

/**
 * 提交 Excel 导入请求。
 * @param {boolean} confirmDuplicate 是否确认继续导入高重叠批次。
 * @returns {Promise<void>}
 */
async function submitImport(confirmDuplicate) {
  if (!selectedFile.value) {
    window.alert('请先选择要导入的 Excel 文件')
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
      result.value = null
      return
    }
    duplicatePreview.value = null
    result.value = data
    await loadHistories()
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

/**
 * 下载导入模板或导出报表文件。
 * @param {string} url 接口地址。
 * @param {string} filename 默认下载文件名。
 * @returns {Promise<void>}
 */
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

/**
 * 打开导入批次详情弹窗。
 * @param {object} item 当前批次记录。
 * @returns {void}
 */
function openHistoryDetail(item) {
  selectedHistory.value = item
}

/**
 * 关闭导入批次详情弹窗。
 * @returns {void}
 */
function closeHistoryDetail() {
  selectedHistory.value = null
}

onMounted(loadHistories)
</script>

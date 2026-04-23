// 时间与文案格式化工具，供任务、通知、邮件和审批页面统一复用。

export function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function formatDateRange(startAt, endAt) {
  // 起止时间有任意一端存在时仍然展示，避免列表信息被完全吞掉。
  if (!startAt && !endAt) return '-'
  return `${formatDateTime(startAt)} - ${formatDateTime(endAt)}`
}

export function toDateTimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function toBackendDateTime(value) {
  // 后端统一接收无时区的秒级时间字符串，这里做一次格式归一化。
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function toDateOnly(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function toBackendStartOfDay(dateValue) {
  if (!dateValue) return null
  const date = new Date(`${dateValue}T00:00:00`)
  if (Number.isNaN(date.getTime())) return null
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T00:00:00`
}

export function toBackendEndOfDay(dateValue) {
  if (!dateValue) return null
  const date = new Date(`${dateValue}T00:00:00`)
  if (Number.isNaN(date.getTime())) return null
  // 结束日期按“次日零点”传给后端，便于后端以左闭右开区间处理筛选。
  date.setDate(date.getDate() + 1)
  const pad = (item) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T00:00:00`
}

export function formatMinutes(value) {
  if (!value) return '0 分钟'
  const hours = Math.floor(value / 60)
  const minutes = value % 60
  if (hours === 0) return `${minutes} 分钟`
  if (minutes === 0) return `${hours} 小时`
  return `${hours} 小时 ${minutes} 分钟`
}

export function formatCountdown(targetTime) {
  // 邮件自动收件倒计时需要秒级刷新，因此这里直接返回适合列表页展示的短文案。
  if (!targetTime) return '未开始计时'
  const target = new Date(targetTime)
  if (Number.isNaN(target.getTime())) return '时间未知'
  const diffMs = target.getTime() - Date.now()
  if (diffMs <= 0) return '即将执行'
  const totalSeconds = Math.floor(diffMs / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}小时 ${minutes}分 ${seconds}秒`
  if (minutes > 0) return `${minutes}分 ${seconds}秒`
  return `${seconds}秒`
}

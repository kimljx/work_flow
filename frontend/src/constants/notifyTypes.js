export const notifyTypeLabels = {
  task_created: '任务创建通知',
  task_updated: '任务更新通知',
  manual_remind: '手动提醒',
  due_remind: '到期提醒',
  task_done: '邮件回执-已完成',
  task_in_progress: '邮件回执-进行中',
}

export function notifyTypeText(value) {
  return notifyTypeLabels[value] || value || '-'
}

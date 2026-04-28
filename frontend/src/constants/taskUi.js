// 任务与子任务展示元数据。
// 这里统一维护状态色和优先级色映射，避免多个页面各自写一套判断分支。
export const taskStatusMeta = {
  not_started: {
    tone: 'status-tone status-tone-neutral',
    dot: 'task-dot task-dot-neutral',
  },
  in_progress: {
    tone: 'status-tone status-tone-primary',
    dot: 'task-dot task-dot-primary',
  },
  done: {
    tone: 'status-tone status-tone-success',
    dot: 'task-dot task-dot-success',
  },
  canceled: {
    tone: 'status-tone status-tone-muted',
    dot: 'task-dot task-dot-muted',
  },
}

export const subtaskStatusMeta = {
  pending: {
    label: '待开始',
    tone: 'status-tone status-tone-neutral',
  },
  in_progress: {
    label: '进行中',
    tone: 'status-tone status-tone-primary',
  },
  done: {
    label: '已完成',
    tone: 'status-tone status-tone-success',
  },
  canceled: {
    label: '已取消',
    tone: 'status-tone status-tone-muted',
  },
}

export const priorityMeta = {
  high: {
    label: '高',
    tone: 'priority-text priority-text-high',
  },
  medium: {
    label: '中',
    tone: 'priority-text priority-text-medium',
  },
  low: {
    label: '低',
    tone: 'priority-text priority-text-low',
  },
}

export function resolveTaskStatusTone(task) {
  const meta = taskStatusMeta[task?.main_status] || taskStatusMeta.not_started
  return {
    ...meta,
    text: task?.status_text || '-',
  }
}

export function resolveSubtaskStatusMeta(status, statusText) {
  const meta = subtaskStatusMeta[status] || subtaskStatusMeta.pending
  return {
    ...meta,
    label: statusText || meta.label,
  }
}

export function resolvePriorityMeta(priority) {
  return priorityMeta[priority] || priorityMeta.medium
}

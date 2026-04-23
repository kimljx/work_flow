// 任务状态与优先级展示元数据。
// 这里统一维护颜色和文案映射，避免多个页面各自写一套判断分支。

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
  // 延期中的任务优先使用风险态展示，即使主状态仍然是“进行中”。
  if (task?.delay_days > 0 && task?.main_status !== 'done' && task?.main_status !== 'canceled') {
    return {
      tone: 'status-tone status-tone-danger',
      dot: 'task-dot task-dot-danger',
      text: `延迟 ${task.delay_days} 天`,
    }
  }
  const meta = taskStatusMeta[task?.main_status] || taskStatusMeta.not_started
  return {
    ...meta,
    text: task?.status_text || '-',
  }
}

export function resolvePriorityMeta(priority) {
  return priorityMeta[priority] || priorityMeta.medium
}

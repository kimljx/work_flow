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
    label: 'HIGH',
    tone: 'priority-text priority-text-high',
  },
  medium: {
    label: 'MEDIUM',
    tone: 'priority-text priority-text-medium',
  },
  low: {
    label: 'LOW',
    tone: 'priority-text priority-text-low',
  },
}

export function resolveTaskStatusTone(task) {
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

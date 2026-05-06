<template>
  <section class="page">
    <div class="panel">
      <TaskEditorForm :task-id="route.params.id" @cancel="goBack" @saved="handleSaved" />
    </div>
  </section>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import TaskEditorForm from '../../components/admin/TaskEditorForm.vue'

const route = useRoute()
const router = useRouter()

function goBack() {
  router.push(route.query.from || '/admin/tasks')
}

function handleSaved(task) {
  router.push(route.query.from || `/admin/tasks/${task.id}`)
}
</script>

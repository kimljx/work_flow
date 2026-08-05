<template>
  <div v-if="total > 0" class="pagination">
    <span class="pagination-total">共 {{ total }} 条</span>

    <label class="pagination-size">
      <select :value="pageSize" @change="changePageSize">
        <option v-for="size in pageSizeOptions" :key="size" :value="size">
          {{ size }}条/页
        </option>
      </select>
    </label>

    <button class="pagination-icon-button" :disabled="currentPage <= 1" type="button" @click="goTo(currentPage - 1)">
      ‹
    </button>

    <button
      v-for="pageItem in visiblePages"
      :key="pageItem.key"
      :class="['pagination-page-button', { active: pageItem.value === currentPage }]"
      :disabled="pageItem.ellipsis"
      type="button"
      @click="!pageItem.ellipsis && goTo(pageItem.value)"
    >
      {{ pageItem.label }}
    </button>

    <button class="pagination-icon-button" :disabled="currentPage >= totalPages" type="button" @click="goTo(currentPage + 1)">
      ›
    </button>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Number,
    required: true,
  },
  total: {
    type: Number,
    required: true,
  },
  pageSize: {
    type: Number,
    default: 20,
  },
  pageSizeOptions: {
    type: Array,
    default: () => [20, 40, 60, 80, 100],
  },
})

const emit = defineEmits(['update:modelValue', 'update:pageSize'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const currentPage = computed(() => Math.min(Math.max(props.modelValue, 1), totalPages.value))

const visiblePages = computed(() => {
  const pages = []
  const total = totalPages.value
  const current = currentPage.value
  const addPage = (value) => pages.push({ key: `page-${value}`, value, label: String(value), ellipsis: false })
  const addEllipsis = (key) => pages.push({ key, value: 0, label: '...', ellipsis: true })

  if (total <= 7) {
    for (let page = 1; page <= total; page += 1) addPage(page)
    return pages
  }

  addPage(1)
  if (current > 4) addEllipsis('ellipsis-left')

  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  for (let page = start; page <= end; page += 1) addPage(page)

  if (current < total - 3) addEllipsis('ellipsis-right')
  addPage(total)
  return pages
})

function goTo(page) {
  emit('update:modelValue', Math.min(Math.max(page, 1), totalPages.value))
}

function changePageSize(event) {
  emit('update:pageSize', Number(event.target.value))
  emit('update:modelValue', 1)
}

watch(totalPages, (nextTotalPages) => {
  if (props.modelValue > nextTotalPages) {
    emit('update:modelValue', nextTotalPages)
  }
})
</script>

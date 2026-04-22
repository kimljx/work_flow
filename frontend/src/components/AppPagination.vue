<template>
  <div class="pagination" v-if="totalPages > 1">
    <button class="button secondary small" :disabled="currentPage <= 1" @click="$emit('update:modelValue', currentPage - 1)">
      上一页
    </button>
    <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
    <button class="button secondary small" :disabled="currentPage >= totalPages" @click="$emit('update:modelValue', currentPage + 1)">
      下一页
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

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
    default: 10,
  },
})

defineEmits(['update:modelValue'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const currentPage = computed(() => Math.min(props.modelValue, totalPages.value))
</script>

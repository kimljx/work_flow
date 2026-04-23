import { defineStore } from 'pinia'

export const useLoadingStore = defineStore('loading', {
  state: () => ({
    pendingCount: 0,
  }),
  getters: {
    isBusy: (state) => state.pendingCount > 0,
  },
  actions: {
    start() {
      this.pendingCount += 1
    },
    finish() {
      this.pendingCount = Math.max(0, this.pendingCount - 1)
    },
    reset() {
      this.pendingCount = 0
    },
  },
})

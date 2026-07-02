/**
 * LLM 状态 Pinia store
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getLLMStatus, switchLLMMode, type LLMStatus } from '@/api/llm'

export const useLLMStore = defineStore('llm', () => {
  const status = ref<LLMStatus | null>(null)
  const loading = ref(false)
  const switching = ref(false)

  async function refresh() {
    loading.value = true
    try {
      status.value = await getLLMStatus()
    } finally {
      loading.value = false
    }
  }

  async function switchMode(mode: 'cloud' | 'local') {
    switching.value = true
    try {
      const result = await switchLLMMode(mode)
      await refresh()
      return result
    } finally {
      switching.value = false
    }
  }

  return { status, loading, switching, refresh, switchMode }
})

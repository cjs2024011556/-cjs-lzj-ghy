/**
 * 通用 localStorage 同步层（替代 3 个 store 重复的 try/catch + JSON.parse + debounce）
 *
 * 用法：
 *   const value = useStorage('a1_auth', defaultUser, { debounceMs: 200 })
 *   value.value = newData  // 自动持久化
 */
import { ref, watch, onUnmounted } from 'vue'

export interface UseStorageOptions<T> {
  /** 防抖时间（ms），0 表示同步写入 */
  debounceMs?: number
  /** 序列化函数，默认 JSON.stringify */
  serializer?: (v: T) => string
  /** 反序列化函数，默认 JSON.parse */
  deserializer?: (raw: string) => T
}

export function useStorage<T>(
  key: string,
  defaultValue: T,
  options: UseStorageOptions<T> = {},
) {
  const {
    debounceMs = 200,
    serializer = JSON.stringify,
    deserializer = (raw: string) => JSON.parse(raw) as T,
  } = options

  // 初始化
  const stored = (() => {
    try {
      const raw = localStorage.getItem(key)
      return raw !== null ? deserializer(raw) : defaultValue
    } catch (e) {
      console.warn(`[useStorage] read ${key} failed:`, e)
      return defaultValue
    }
  })()

  const data = ref(stored) as { value: T }

  let timer: number | null = null
  const writeNow = () => {
    try {
      localStorage.setItem(key, serializer(data.value))
    } catch (e) {
      console.warn(`[useStorage] write ${key} failed:`, e)
    }
  }

  watch(
    data,
    () => {
      if (debounceMs > 0) {
        if (timer) clearTimeout(timer)
        timer = window.setTimeout(writeNow, debounceMs)
      } else {
        writeNow()
      }
    },
    { deep: true },
  )

  // 主动立即写（如登出清理时）
  function flush() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    writeNow()
  }

  // 主动删除（如登出）
  function clear() {
    if (timer) clearTimeout(timer)
    try {
      localStorage.removeItem(key)
    } catch {}
    data.value = defaultValue
  }

  onUnmounted(() => {
    if (timer) clearTimeout(timer)
  })

  return { data, flush, clear }
}

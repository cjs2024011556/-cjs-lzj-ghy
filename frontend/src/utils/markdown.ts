/**
 * 安全 Markdown 渲染（marked + DOMPurify）
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'u', 'code', 'pre',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'ul', 'ol', 'li', 'blockquote',
  'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'hr', 'span', 'div',
] as const

const ALLOWED_ATTR = ['href', 'title', 'class', 'target', 'rel'] as const

marked.setOptions({ gfm: true, breaks: true })

/**
 * 把 markdown 文本转成安全 HTML（防 XSS）
 */
export function renderSafeMarkdown(text: string): string {
  if (!text) return ''
  try {
    const raw = marked.parse(text, { async: false, breaks: true }) as string
    return DOMPurify.sanitize(raw, {
      ALLOWED_TAGS: [...ALLOWED_TAGS],
      ALLOWED_ATTR: [...ALLOWED_ATTR],
    })
  } catch {
    return DOMPurify.sanitize(text.replace(/\n/g, '<br>'))
  }
}

/**
 * 简单缓存（用闭包 Map，避免 WeakMap object key 限制）
 */
const cache = new Map<string, string>()
const MAX_CACHE = 200

export function renderSafeMarkdownCached(text: string): string {
  if (!text) return ''
  if (cache.has(text)) return cache.get(text)!
  const html = renderSafeMarkdown(text)
  if (cache.size >= MAX_CACHE) {
    // 简单 LRU：删最早插入的 1 个
    const firstKey = cache.keys().next().value
    if (firstKey !== undefined) cache.delete(firstKey)
  }
  cache.set(text, html)
  return html
}

import { useSyncExternalStore } from 'react'
import type { ReactNode } from 'react'
import zh from '../../shared/locales/zh.json'
import claims from '../../shared/locales/claims.json'
import templates from '../../shared/locales/patterns.json'

export type Language = 'en' | 'zh'
const storageKey = 'vehicle-npi-language'
const listeners = new Set<() => void>()
let language: Language = 'en'
try { language = localStorage.getItem(storageKey) === 'zh' ? 'zh' : 'en' } catch { /* Storage can be disabled. */ }

export function getLanguage(): Language { return language }
export function setLanguage(next: Language) {
  if (next === language) return
  language = next
  try { localStorage.setItem(storageKey, next) } catch { /* The current tab still works. */ }
  document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en'
  document.title = next === 'zh' ? '汽车新产品导入 · Cloudera AI' : 'Vehicle NPI · Cloudera AI'
  listeners.forEach(listener => listener())
}
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } }
export function useLanguage() { return useSyncExternalStore(subscribe, getLanguage, () => 'en' as Language) }

const catalog = zh as Record<string, string>
const escaped = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const phrases = Object.keys(catalog).filter(key => key && key !== catalog[key]).sort((a, b) => b.length - a.length)
const phrasePattern = new RegExp(`(?<![A-Za-z0-9_])(?:${phrases.map(escaped).join('|')})(?![A-Za-z0-9_])`, 'gi')
const folded = Object.fromEntries(Object.entries(catalog).map(([key, value]) => [key.toLowerCase(), value]))
const patterns = [...claims.map(([source, target]) => ({ pattern: new RegExp(source, 'gi'), target })), ...templates.map(([source, target]) => {
  const pieces = source.split(/(\{\d+\})/)
  const expression = pieces.map((part, index) => /^\{\d+\}$/.test(part)
    ? (index === 1 && !pieces[0] ? '(\\d+)' : '([^\\n]+?)') : escaped(part)).join('')
  return { pattern: new RegExp(`(?<![A-Za-z0-9_])${expression}(?=$|[\\s,;])`, 'g'), target }
})]
const cache = new Map<string, string>()

/** Translate display text only. Keys, IDs, measurements and source records stay canonical. */
export function t(value: string): string {
  if (language === 'en' || !value) return value
  if (Object.hasOwn(catalog, value)) return catalog[value]
  const trimmed = value.trim()
  if (Object.hasOwn(catalog, trimmed)) return value.replace(trimmed, catalog[trimmed])
  if (cache.has(value)) return cache.get(value)!
  const original = value
  for (const { pattern, target } of patterns) {
    value = value.replace(pattern, (...args: unknown[]) => target.replace(/\{(\d+)\}/g, (_, slot: string) => t(String(args[Number(slot) + 1]))))
  }
  const protectedValues: string[] = []
  const protectedText = value.replace(/https?:\/\/[^\s<>]+|\b[A-Z][A-Z0-9]*(?:[-:@][A-Za-z0-9_.:@/-]+)+\b|\b[a-f0-9]{32,64}\b|\b[a-z][a-z0-9]*(?:-[a-z0-9]+){2,}\b/g,
    match => { protectedValues.push(match); return `\uE000${protectedValues.length - 1}\uE001` })
  const translated = protectedText.replace(phrasePattern, match => folded[match.toLowerCase()] ?? match)
    .replace(/\uE000(\d+)\uE001/g, (_, index: string) => protectedValues[Number(index)])
  if (cache.size > 4000) cache.clear()
  cache.set(original, translated)
  return translated
}

export function tNode(value: ReactNode): ReactNode {
  if (typeof value === 'string') return t(value)
  if (Array.isArray(value)) return value.map(tNode)
  return value
}

if (typeof document !== 'undefined') {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
  document.title = language === 'zh' ? '汽车新产品导入 · Cloudera AI' : 'Vehicle NPI · Cloudera AI'
}

/** Render readable field labels without modifying machine identifiers in values. */
export function formatDetails(value: unknown): string {
  const canonical = /(^id$|_id$|_ids$|_key$|_keys$|sha256$|_url$|^url$|^key$|version$|^tokenizer$|^model$|^unit$|^method$|^extraction_method$|^source_file$)/
  function display(item: unknown, field = ''): unknown {
    if (Array.isArray(item)) return item.map(child => display(child, field))
    if (item && typeof item === 'object') return Object.fromEntries(Object.entries(item).map(([key, child]) => [t(key), display(child, key)]))
    if (typeof item === 'string' && !canonical.test(field)) return t(item)
    return item
  }
  return JSON.stringify(display(value), null, 2)
}

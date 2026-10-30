import { useState } from 'react'
import { searchAll } from '../lib/search'
import type { Command } from '../data/commands'
import type { SearchHit } from '../lib/search'

interface Props {
  searchId: string
  onNavigateSection: (id: string) => void
  onOpenCommand: (c: Command) => void
}

/** 顶部搜索：命令 + 章节 联合匹配；↑/↓ 选择，Enter 跳转，Esc 清空 */
export function SearchBox({ searchId, onNavigateSection, onOpenCommand }: Props) {
  const [q, setQ] = useState('')
  const [cursor, setCursor] = useState(0)
  const [focused, setFocused] = useState(false)
  const hits: SearchHit[] = q.trim() ? searchAll(q) : []
  const open = focused && hits.length > 0

  const activate = (h: SearchHit) => {
    if (h.type === 'section') onNavigateSection(h.id)
    else if (h.command) onOpenCommand(h.command)
    setQ('')
    setCursor(0)
  }

  return (
    <div className="relative">
      <input
        id={searchId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={`${searchId}-listbox`}
        aria-label="搜索命令与章节（快捷键 /）"
        placeholder="搜索命令或章节…（按 / 聚焦）"
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setCursor(0)
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => window.setTimeout(() => setFocused(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setCursor((c) => Math.min(c + 1, hits.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setCursor((c) => Math.max(c - 1, 0))
          } else if (e.key === 'Enter') {
            e.preventDefault()
            if (hits[cursor]) activate(hits[cursor])
          } else if (e.key === 'Escape') {
            setQ('')
            ;(e.target as HTMLInputElement).blur()
          }
        }}
        className="w-full rounded border border-line bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
      />
      {open && (
        <ul
          id={`${searchId}-listbox`}
          role="listbox"
          aria-label="搜索结果"
          className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded border border-line bg-card py-1 shadow-lg"
        >
          {hits.map((h, i) => (
            <li key={`${h.type}-${h.id}`} role="option" aria-selected={i === cursor}>
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault()
                  activate(h)
                }}
                onMouseEnter={() => setCursor(i)}
                className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm ${
                  i === cursor ? 'bg-accent-soft text-accent-deep' : 'text-ink'
                }`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className={`font-mono text-xs ${h.type === 'command' ? 'text-accent' : 'text-ink-faint'}`}>
                    {h.type === 'command' ? '⌘' : '§'}
                  </span>
                  <span className="truncate font-medium">{h.title}</span>
                  <span className="truncate text-xs text-ink-faint">{h.subtitle}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function SearchHint() {
  return (
    <p className="mt-2 flex items-center gap-1 text-xs text-ink-faint">
      <kbd className="rounded border border-line bg-card px-1 font-mono">/</kbd> 聚焦搜索
      <kbd className="ml-2 rounded border border-line bg-card px-1 font-mono">Esc</kbd> 清空
    </p>
  )
}

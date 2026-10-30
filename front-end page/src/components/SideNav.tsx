import { Menu, X } from 'lucide-react'
import { SECTIONS } from '../data/sections'
import { SearchBox, SearchHint } from './SearchBox'
import type { Command } from '../data/commands'

interface NavProps {
  active: string
  onNavigate: (id: string) => void
  onOpenCommand: (c: Command) => void
  searchId: string
}

/** 导航列表（桌面侧栏与移动抽屉共用） */
export function SideNav({ active, onNavigate, onOpenCommand, searchId }: NavProps) {
  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div>
        <p className="font-display text-lg font-semibold tracking-wide">Impeccable 指南</p>
        <p className="mt-0.5 text-xs text-ink-faint">给编码智能体的设计词汇表</p>
      </div>
      <div>
        <SearchBox searchId={searchId} onNavigateSection={onNavigate} onOpenCommand={onOpenCommand} />
        <SearchHint />
      </div>
      <nav aria-label="页面导航" className="flex-1">
        <ul className="space-y-0.5">
          {SECTIONS.map((s) => {
            const isActive = s.id === active
            return (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  aria-current={isActive ? 'true' : undefined}
                  onClick={(e) => {
                    e.preventDefault()
                    onNavigate(s.id)
                  }}
                  className={`group flex items-baseline gap-2 border-l-2 py-1.5 pl-3 text-sm transition-colors ${
                    isActive ? 'border-accent font-medium text-ink' : 'border-transparent text-ink-soft hover:border-line hover:text-ink'
                  }`}
                >
                  <span className={`font-mono text-xs ${isActive ? 'text-accent' : 'text-ink-faint'}`}>{s.num}</span>
                  {s.label}
                </a>
              </li>
            )
          })}
        </ul>
      </nav>
      <p className="border-t border-line pt-3 text-[11px] leading-5 text-ink-faint">
        基于上游 pbakaus/impeccable
        <br />
        commit 02523ae · Apache-2.0
      </p>
    </div>
  )
}

/** 移动端顶栏（<lg 显示） */
export function MobileBar({ onOpen }: { onOpen: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-paper/95 px-4 py-2.5 backdrop-blur lg:hidden">
      <div>
        <p className="font-display text-base font-semibold leading-tight">Impeccable 指南</p>
        <p className="text-[11px] text-ink-faint">给编码智能体的设计词汇表</p>
      </div>
      <button
        type="button"
        aria-label="打开导航菜单"
        onClick={onOpen}
        className="rounded border border-line bg-card p-2 text-ink hover:border-accent"
      >
        <Menu size={18} aria-hidden />
      </button>
    </header>
  )
}

/** 移动端抽屉容器 */
export function MobileDrawer({
  open,
  onClose,
  active,
  onNavigate,
  onOpenCommand,
}: NavProps & { open: boolean; onClose: () => void }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="导航菜单">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="absolute inset-y-0 left-0 w-72 overflow-y-auto border-r border-line bg-paper shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-2">
          <span className="text-sm font-medium">导航</span>
          <button type="button" aria-label="关闭导航菜单" onClick={onClose} className="rounded border border-line bg-card p-1.5 text-ink hover:border-accent">
            <X size={16} aria-hidden />
          </button>
        </div>
        <SideNav
          active={active}
          searchId="search-mobile"
          onNavigate={(id) => {
            onClose()
            onNavigate(id)
          }}
          onOpenCommand={(c) => {
            onClose()
            onOpenCommand(c)
          }}
        />
      </div>
    </div>
  )
}

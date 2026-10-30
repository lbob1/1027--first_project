import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { CATEGORY_LABELS, CATEGORY_ORDER, type Command, type CommandCategory } from '../data/commands'
import { filterCommands } from '../lib/search'
import { Pill, SectionHeader } from '../components/ui'

interface Props {
  onOpenCommand: (c: Command) => void
  sectionSearchId: string
}

type Cat = CommandCategory | 'all'

/** 命令速查：搜索框 + 类别 pill 筛选 + 命令列表 + 详情抽屉（由 App 挂载） */
export function CommandReferenceSection({ onOpenCommand, sectionSearchId }: Props) {
  const [query, setQuery] = useState('')
  const [cat, setCat] = useState<Cat>('all')
  const results = useMemo(() => filterCommands(query, cat), [query, cat])

  const counts = useMemo(() => {
    const m = new Map<Cat, number>()
    for (const c of filterCommands(query, 'all')) m.set(c.category, (m.get(c.category) ?? 0) + 1)
    return m
  }, [query])

  return (
    <section id="commands" aria-label="命令速查" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="03 / 命令速查"
          title="24 个命令，一张表"
          lead="调用形式 /impeccable <命令> <目标>。无参数时弹出上下文感知菜单；/impeccable pin audit 可把常用命令固定为独立快捷方式。点击命令名查看详情。"
        />

        <div className="mb-4 flex flex-col gap-3">
          <div className="relative">
            <Search size={15} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input
              id={sectionSearchId}
              type="search"
              role="searchbox"
              aria-label="按关键字过滤命令"
              placeholder="过滤命令：如 评审、polish、性能…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded border border-line bg-card py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
            />
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="按类别筛选">
            <button
              type="button"
              aria-pressed={cat === 'all'}
              onClick={() => setCat('all')}
              className={`rounded-full border px-3 py-1 text-xs ${cat === 'all' ? 'border-ink bg-ink text-paper' : 'border-line bg-card text-ink-soft hover:border-accent hover:text-accent'}`}
            >
              全部 {query ? `· ${filterCommands(query, 'all').length}` : '· 24'}
            </button>
            {CATEGORY_ORDER.map((c) => (
              <button
                key={c}
                type="button"
                aria-pressed={cat === c}
                onClick={() => setCat(c)}
                className={`rounded-full border px-3 py-1 text-xs ${cat === c ? 'border-ink bg-ink text-paper' : 'border-line bg-card text-ink-soft hover:border-accent hover:text-accent'}`}
              >
                {CATEGORY_LABELS[c]} · {counts.get(c) ?? 0}
              </button>
            ))}
          </div>
        </div>

        {results.length === 0 ? (
          <p className="rounded border border-dashed border-line px-4 py-10 text-center text-sm text-ink-faint">
            没有匹配的命令 —— 试试清空关键字或切换类别。
          </p>
        ) : (
          <ul className="divide-y divide-line/70 rounded border border-line bg-card">
            {results.map((c) => (
              <li key={c.name} className="grid gap-x-4 gap-y-1 px-4 py-2.5 sm:grid-cols-[9.5rem_1fr]">
                <button
                  type="button"
                  onClick={() => onOpenCommand(c)}
                  aria-haspopup="dialog"
                  className="justify-self-start rounded px-1 font-mono text-sm font-medium text-accent-deep underline decoration-accent/30 underline-offset-2 hover:bg-accent-soft hover:decoration-accent"
                >
                  /{c.name}
                </button>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                  <span className="text-[13px] leading-6 text-ink">{c.purpose}</span>
                  <Pill tone={c.category === 'deprecated' ? 'line' : 'accent'}>{CATEGORY_LABELS[c.category]}</Pill>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-ink-faint">共 {results.length} 条 · 命令清单与上游 skill/SKILL.src.md 对齐（commit 02523ae）</p>
      </div>
    </section>
  )
}

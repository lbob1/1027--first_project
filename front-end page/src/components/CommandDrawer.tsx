import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { CATEGORY_LABELS, type Command } from '../data/commands'
import { CodeBlock, Pill } from './ui'

/** 命令详情抽屉：Esc / 遮罩关闭，打开时聚焦关闭按钮，关闭后焦点还原 */
export function CommandDrawer({ command, onClose }: { command: Command | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const restoreRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!command) return
    restoreRef.current = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      restoreRef.current?.focus()
    }
  }, [command, onClose])

  if (!command) return null

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="cmd-drawer-title">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="absolute inset-y-0 right-0 w-full max-w-md overflow-y-auto border-l border-line bg-paper shadow-2xl">
        <div className="sticky top-0 flex items-start justify-between gap-3 border-b border-line bg-paper px-5 py-4">
          <div>
            <p id="cmd-drawer-title" className="font-mono text-lg font-semibold text-accent">
              /impeccable {command.name}
            </p>
            <div className="mt-1.5">
              <Pill tone={command.category === 'deprecated' ? 'line' : 'accent'}>{CATEGORY_LABELS[command.category]}</Pill>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            aria-label="关闭详情"
            onClick={onClose}
            className="rounded border border-line bg-card p-1.5 text-ink hover:border-accent"
          >
            <X size={16} aria-hidden />
          </button>
        </div>
        <dl className="space-y-5 px-5 py-5 text-sm leading-7">
          <div>
            <dt className="mb-1 text-xs font-medium tracking-wide text-ink-faint">用途</dt>
            <dd className="text-ink">{command.purpose}</dd>
          </div>
          <div>
            <dt className="mb-1 text-xs font-medium tracking-wide text-ink-faint">适用场景</dt>
            <dd className="text-ink">{command.scene}</dd>
          </div>
          <div>
            <dt className="mb-1 text-xs font-medium tracking-wide text-ink-faint">示例调用</dt>
            <dd>
              <CodeBlock code={command.example} />
            </dd>
          </div>
          <p className="rounded border border-line bg-card px-3 py-2 text-xs leading-6 text-ink-soft">
            所有命令都会读取 PRODUCT.md（由 init 写入的产品事实层）。目标越具体，结果越好——单个组件的精查胜过整页的走马观花。
          </p>
        </dl>
      </div>
    </div>
  )
}

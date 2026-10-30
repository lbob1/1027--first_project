import { useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import type { ReactNode } from 'react'

async function writeClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // file:// 等非安全上下文回退
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
}

/** 复制按钮：点击后图标切换 ✓ 2 秒（无需 toast） */
export function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number>(0)
  return (
    <button
      type="button"
      aria-label={label ?? '复制代码'}
      onClick={() => {
        void writeClipboard(text)
        setCopied(true)
        window.clearTimeout(timer.current)
        timer.current = window.setTimeout(() => setCopied(false), 2000)
      }}
      className="inline-flex items-center gap-1 rounded border border-line bg-card px-2 py-1 text-xs text-ink-soft hover:border-accent hover:text-accent"
    >
      {copied ? <Check size={13} aria-hidden /> : <Copy size={13} aria-hidden />}
      {copied ? '已复制' : '复制'}
    </button>
  )
}

/** 终端样式代码块 + 一键复制 */
export function CodeBlock({ code, label, className = '' }: { code: string; label?: string; className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded border border-line bg-ink text-paper ${className}`}>
      {label && (
        <div className="border-b border-paper/15 px-4 py-1.5 text-xs text-paper/60">{label}</div>
      )}
      <pre className="overflow-x-auto px-4 py-3 font-mono text-[13px] leading-6">
        <code>{code}</code>
      </pre>
      <div className="absolute right-2 top-2">
        <CopyButton text={code} />
      </div>
    </div>
  )
}

/** 小标签 */
export function Pill({
  tone = 'line',
  children,
}: {
  tone?: 'line' | 'accent' | 'ink' | 'ok'
  children: ReactNode
}) {
  const tones = {
    line: 'border-line text-ink-soft bg-card',
    accent: 'border-accent/40 text-accent-deep bg-accent-soft',
    ink: 'border-ink/30 text-paper bg-ink',
    ok: 'border-ok/40 text-ok bg-[#e7efe9]',
  } as const
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}

/** 章节标题（编号 + 标题 + 导语） */
export function SectionHeader({ num, title, lead }: { num: string; title: string; lead?: string }) {
  return (
    <header className="mb-6 border-b border-line pb-4">
      <p className="font-mono text-xs tracking-widest text-accent">{num}</p>
      <h2 className="mt-1 font-display text-2xl font-semibold tracking-wide sm:text-3xl">{title}</h2>
      {lead && <p className="mt-2 max-w-[42rem] text-sm leading-7 text-ink-soft">{lead}</p>}
    </header>
  )
}

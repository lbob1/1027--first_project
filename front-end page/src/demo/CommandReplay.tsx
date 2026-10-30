import { useEffect, useRef, useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { usePrefersReducedMotion } from '../hooks'
import { Pill } from '../components/ui'
import { TrendChart } from './TrendChart'
import { HEURISTICS, ISSUES, NEXT_COMMANDS, PERSONAS, REVIEW_PANELS, TREND } from '../data/critiqueSample'

type Phase = 'idle' | 'typing' | 'sent' | 'report'

const DEMO_TARGETS = ['/impeccable critique 首页', '/impeccable critique 定价卡片', '/impeccable audit 结账流程']

const PHASE_ANNOUNCE: Record<Phase, string> = {
  idle: '等待输入，可点击示例命令开始回放',
  typing: '正在输入命令…',
  sent: '评审 A 与评审 B 并行进行中…',
  report: '评审报告已生成：健康分 32 / 40，1 个 P0、1 个 P1 问题',
}

/**
 * 命令输入回放（对应参考图二：/impeccable critique 首页）
 * 状态机：idle → typing → sent → report
 */
export function CommandReplay() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [typed, setTyped] = useState('')
  const [target, setTarget] = useState(DEMO_TARGETS[0])
  const reduced = usePrefersReducedMotion()
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (phase !== 'typing') return
    if (reduced) {
      setTyped(target)
      setPhase('sent')
      return
    }
    let i = 0
    const id = window.setInterval(() => {
      i += 1
      setTyped(target.slice(0, i))
      if (i >= target.length) {
        window.clearInterval(id)
        setPhase('sent')
      }
    }, 70)
    return () => window.clearInterval(id)
  }, [phase, target, reduced])

  useEffect(() => {
    if (phase !== 'sent') return
    const id = window.setTimeout(() => setPhase('report'), reduced ? 0 : 1400)
    return () => window.clearTimeout(id)
  }, [phase, reduced])

  const start = (cmd: string) => {
    setTarget(cmd)
    setTyped('')
    setPhase('typing')
  }

  const total = HEURISTICS.reduce((s, h) => s + h.score, 0)

  return (
    <div className="rounded border border-line bg-card">
      {/* 输入区 */}
      <div className="border-b border-line p-4">
        <div className="flex items-center gap-2 rounded border border-line bg-paper px-3 py-2">
          <span aria-hidden className="font-mono text-sm text-accent">
            ›
          </span>
          <input
            ref={inputRef}
            type="text"
            value={phase === 'typing' ? typed : phase === 'idle' ? typed : target}
            readOnly={phase !== 'idle'}
            placeholder="试着输入 /impeccable critique 首页"
            aria-label="模拟命令输入框"
            onChange={(e) => {
              setTyped(e.target.value)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                start((e.target as HTMLInputElement).value)
              }
            }}
            className="w-full bg-transparent font-mono text-sm text-ink outline-none placeholder:text-ink-faint"
          />
          {phase === 'typing' && <span aria-hidden className="review-blink font-mono text-accent">▌</span>}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-faint">示例：</span>
          {DEMO_TARGETS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => start(t)}
              className="rounded-full border border-line bg-paper px-2.5 py-1 font-mono text-xs text-ink-soft hover:border-accent hover:text-accent"
            >
              {t}
            </button>
          ))}
          {(phase === 'report' || phase === 'sent') && (
            <button
              type="button"
              onClick={() => {
                setPhase('idle')
                setTyped('')
              }}
              className="ml-auto inline-flex items-center gap-1 rounded border border-line bg-card px-2 py-1 text-xs text-ink-soft hover:border-accent hover:text-accent"
            >
              <RotateCcw size={12} aria-hidden />
              重播
            </button>
          )}
        </div>
      </div>

      {/* 状态区 */}
      <div aria-live="polite" className="sr-only">
        {PHASE_ANNOUNCE[phase]}
      </div>

      <div className="p-4">
        {phase === 'idle' && (
          <p className="py-8 text-center text-sm text-ink-faint">
            点击上方示例命令，或在输入框键入后回车 —— 查看双评审如何产出一份完整报告
          </p>
        )}

        {phase === 'sent' && (
          <div className="grid gap-3 py-6 sm:grid-cols-2">
            {REVIEW_PANELS.map((p, i) => (
              <div key={p.tag} className="flex items-start gap-3 rounded border border-line bg-paper px-3.5 py-3">
                <span aria-hidden className={`mt-1 h-2 w-2 rounded-full bg-accent ${i === 0 ? '' : 'review-blink'}`} style={{ animationDelay: `${i * 0.3}s` }} />
                <div>
                  <p className="text-sm font-medium">{p.tag}</p>
                  <p className="mt-0.5 text-xs leading-5 text-ink-faint">运行中…（模拟）</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {phase === 'report' && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">设计健康分</span>
              <span className="font-mono text-lg font-bold text-accent-deep">{total}/40</span>
              <Pill tone="ok">Good 档</Pill>
              <Pill>设计特异性：中</Pill>
              <Pill>模拟数据</Pill>
            </div>

            {/* 10 启发式评分表 */}
            <div className="overflow-hidden rounded border border-line">
              <table className="w-full text-left text-[13px]">
                <caption className="sr-only">Nielsen 十条启发式逐条评分（0~4 分）</caption>
                <thead>
                  <tr className="border-b border-line bg-paper text-xs text-ink-faint">
                    <th scope="col" className="px-3 py-2 font-medium">启发式</th>
                    <th scope="col" className="px-3 py-2 font-medium">评分</th>
                    <th scope="col" className="hidden px-3 py-2 font-medium sm:table-cell">备注</th>
                  </tr>
                </thead>
                <tbody>
                  {HEURISTICS.map((h) => (
                    <tr key={h.name} className="border-b border-line/60 last:border-0">
                      <th scope="row" className="px-3 py-1.5 font-normal">{h.name}</th>
                      <td className="px-3 py-1.5">
                        <span aria-label={`${h.score} 分（满分 4 分）`} className="tracking-widest text-accent" aria-hidden>
                          {'●'.repeat(h.score)}
                          <span className="text-line">{'●'.repeat(4 - h.score)}</span>
                        </span>
                        <span className="ml-1.5 font-mono text-xs text-ink-faint">{h.score}</span>
                      </td>
                      <td className="hidden px-3 py-1.5 text-ink-faint sm:table-cell">{h.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* P0~P3 问题 */}
            <div>
              <h4 className="mb-2 text-sm font-medium">优先问题（P0 阻断 → P3 打磨）</h4>
              <ul className="space-y-2">
                {ISSUES.map((it) => (
                  <li key={it.level} className="flex flex-wrap items-start gap-x-3 gap-y-1 rounded border border-line bg-paper px-3 py-2 text-[13px] leading-6">
                    <Pill tone={it.level === 'P0' ? 'accent' : it.level === 'P1' ? 'ink' : 'line'}>{it.level}</Pill>
                    <span className="font-medium">{it.title}</span>
                    <span className="basis-full text-ink-soft">{it.detail}</span>
                    <code className="ml-auto font-mono text-xs text-accent">{it.command}</code>
                  </li>
                ))}
              </ul>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              {/* 趋势 */}
              <div className="rounded border border-line bg-paper p-3">
                <h4 className="mb-1 text-sm font-medium">快照趋势（最近 5 次）</h4>
                <p className="mb-2 text-xs text-ink-faint">存于 .impeccable/critique/</p>
                <TrendChart data={TREND} />
              </div>
              {/* persona 红旗 */}
              <div className="rounded border border-line bg-paper p-3">
                <h4 className="mb-2 text-sm font-medium">Persona 走查红旗</h4>
                <ul className="space-y-1.5 text-[13px] leading-6">
                  {PERSONAS.map((p) => (
                    <li key={p.name} className="flex gap-2">
                      <span className="font-mono text-xs text-accent-deep">{p.name}</span>
                      <span className="text-ink-faint">{p.trait}</span>
                      <span className="text-ink-soft">— {p.flag}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* 推荐命令序列 */}
            <div>
              <h4 className="mb-2 text-sm font-medium">推荐命令序列（收尾必是 polish）</h4>
              <div className="flex flex-col gap-1.5">
                {NEXT_COMMANDS.map((c, i) => (
                  <div key={c} className="flex items-center gap-2 text-[13px]">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full border border-line bg-card font-mono text-xs text-ink-soft">{i + 1}</span>
                    <code className="font-mono text-accent-deep">{c}</code>
                    {i === NEXT_COMMANDS.length - 1 && <Pill tone="accent">终章</Pill>}
                  </div>
                ))}
              </div>
            </div>

            <p className="text-xs leading-6 text-ink-faint">
              交互模拟：以上为演示用示例数据。真实 critique 会先做双独立评审（防锚定），综合报告含设计健康分表、特异性判定、P0~P3 问题与 persona 红旗，并基于你的回答给出命令序列。
            </p>
          </div>
        )}
      </div>

      {/* 机制说明（常驻） */}
      <div className="border-t border-line bg-paper/60 px-4 py-3">
        <p className="text-xs leading-6 text-ink-soft">
          <span className="font-medium text-ink">机制</span>：评审 A（设计总监视角）与评审 B（62 条规则 + 浏览器 overlay 证据）必须隔离运行以防锚定；结果存入{' '}
          <code className="font-mono text-xs">.impeccable/critique/</code> 形成快照；报告最后会基于发现提出 2~4 个带选项的问题，按你的回答输出推荐命令。
        </p>
      </div>
    </div>
  )
}

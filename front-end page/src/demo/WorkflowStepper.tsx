import { useEffect, useState } from 'react'
import { Pause, Play } from 'lucide-react'
import { useInView, usePrefersReducedMotion } from '../hooks'
import { CodeBlock, Pill } from '../components/ui'

interface Step {
  id: number
  title: string
  badge: string
  badgeTone: 'ink' | 'accent' | 'line'
  what: string
  say: string
  out: string
  branch?: string
}

const STEPS: Step[] = [
  {
    id: 1,
    title: 'init：先写入产品事实',
    badge: '每项目一次',
    badgeTone: 'ink',
    what: '探索你的代码库，只问无法推断的问题（目标用户、产品定位、约束），写入 PRODUCT.md。不涉及任何视觉决策，后续所有命令都会读取它。',
    say: '/impeccable init',
    out: 'PRODUCT.md —— 产品事实层：用户、定位、约束、品牌承诺（绝不放视觉决策）',
  },
  {
    id: 2,
    title: 'shape（可选）：先规划再动手',
    badge: '可选',
    badgeTone: 'accent',
    what: '访谈发现（目的 / 人群 / 结果，每轮 2~3 问）→ 解决设计方向 → 产出最小可用 brief 供你确认。到确认即停止，不写一行代码。',
    say: '/impeccable shape 定价页',
    out: 'surface brief —— 单界面方向契约（THESIS / STORY / FIRST VIEWPORT 等），确认即冻结',
    branch: '想先规划 → 走 shape；不需要 → 直接跳到第 3 步',
  },
  {
    id: 3,
    title: '直接描述你想要的页面',
    badge: '日常入口',
    badgeTone: 'line',
    what: '用自然语言说出想要什么，skill 走 new-work 流程：判断既有视觉资产 →（需要时）掷概念种子、出方向决策卡 → 按你选中的方向全情构建。',
    say: '/impeccable redo this hero section',
    out: '构建出的界面 → 接入评审循环（critique / audit）与实时迭代（live）',
  },
]

/**
 * 核心工作流 Stepper（对应参考图一：init → 可选 shape → 直接描述）
 * 状态机：openStep ∈ {1,2,3}；进入视口后自动播放（reduced-motion 下不自动播放）
 */
export function WorkflowStepper() {
  const [openStep, setOpenStep] = useState(1)
  const [playing, setPlaying] = useState(false)
  const reduced = usePrefersReducedMotion()
  const { ref, inView } = useInView<HTMLDivElement>()

  useEffect(() => {
    if (inView && !reduced && openStep === 1 && !playing) {
      setPlaying(true)
    }
  }, [inView, reduced, openStep, playing])

  useEffect(() => {
    if (!playing || reduced) return
    const id = window.setInterval(() => {
      setOpenStep((s) => {
        if (s >= STEPS.length) {
          setPlaying(false)
          return s
        }
        return s + 1
      })
    }, 2800)
    return () => window.clearInterval(id)
  }, [playing, reduced])

  return (
    <div ref={ref}>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs text-ink-faint">点击节点展开详情 · 中间节点为可选分支</p>
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          aria-pressed={playing}
          className="inline-flex items-center gap-1.5 rounded border border-line bg-card px-2.5 py-1 text-xs text-ink-soft hover:border-accent hover:text-accent"
        >
          {playing ? <Pause size={13} aria-hidden /> : <Play size={13} aria-hidden />}
          {playing ? '暂停播放' : '自动播放'}
        </button>
      </div>

      <ol className="relative space-y-3" aria-label="三步核心工作流">
        <span aria-hidden className="absolute bottom-5 left-[15px] top-5 w-px bg-line" />
        {STEPS.map((step) => {
          const open = openStep === step.id
          return (
            <li key={step.id} className="relative pl-11">
              <button
                type="button"
                aria-expanded={open}
                onClick={() => {
                  setOpenStep(step.id)
                  setPlaying(false)
                }}
                className={`absolute left-0 top-0.5 flex h-8 w-8 items-center justify-center rounded-full border font-mono text-sm transition-colors ${
                  open ? 'border-accent bg-accent text-paper' : 'border-line bg-card text-ink-soft hover:border-accent hover:text-accent'
                }`}
                aria-label={`第 ${step.id} 步：${step.title}`}
              >
                {step.id}
              </button>
              <div className={`rounded border transition-colors ${open ? 'border-accent/50 bg-card' : 'border-line bg-card/60'}`}>
                <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
                  <span className="text-sm font-medium">{step.title}</span>
                  <Pill tone={step.badgeTone}>{step.badge}</Pill>
                </div>
                {open && (
                  <div className="space-y-3 border-t border-line/70 px-4 py-3.5 text-sm leading-7">
                    <p className="text-ink-soft">{step.what}</p>
                    {step.branch && (
                      <p className="rounded border border-accent/30 bg-accent-soft/60 px-3 py-1.5 text-xs text-accent-deep">⑂ {step.branch}</p>
                    )}
                    <dl className="grid gap-2 sm:grid-cols-2">
                      <div>
                        <dt className="text-xs font-medium text-ink-faint">说什么</dt>
                        <dd className="mt-1">
                          <CodeBlock code={step.say} />
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-ink-faint">产出什么</dt>
                        <dd className="mt-1 rounded border border-line bg-paper px-3 py-2.5 text-[13px] leading-6 text-ink">{step.out}</dd>
                      </div>
                    </dl>
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ol>
      <p className="mt-3 text-xs text-ink-faint">流程示意，与上游 reference/new-work.md 的机制一致；实际输出以你的项目上下文为准。</p>
    </div>
  )
}

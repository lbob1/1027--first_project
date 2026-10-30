import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { Check, ChevronLeft, ChevronRight, MousePointerClick, RotateCcw, SlidersHorizontal, X } from 'lucide-react'
import { usePrefersReducedMotion } from '../hooks'
import { Pill } from '../components/ui'

type Phase = 'off' | 'live' | 'selected' | 'generating' | 'variants' | 'accepted'

const VARIANT_LABELS = ['V1 · 层级', 'V2 · 密度', 'V3 · 色彩']
const VARIANT_AXES = ['衬线大标题 + 留白层级', '紧凑列表 + 小步间距', '朱红强调 + 品牌色彩量']

/**
 * Live 实时迭代模拟器（对应参考图三：Impeccable live 徽标）
 * 状态机：off → live → selected → generating → variants → accepted
 * 参数旋钮直接驱动示例卡片的 CSS 变量（--p-density / --p-color），零再生成本
 */
export function LiveSimulator() {
  const [phase, setPhase] = useState<Phase>('off')
  const [variant, setVariant] = useState(0)
  const [density, setDensity] = useState(50)
  const [color, setColor] = useState(50)
  const reduced = usePrefersReducedMotion()

  useEffect(() => {
    if (phase !== 'generating') return
    const id = window.setTimeout(() => setPhase('variants'), reduced ? 0 : 900)
    return () => window.clearTimeout(id)
  }, [phase, reduced])

  const live = phase !== 'off'
  const knobsEnabled = phase === 'variants' || phase === 'accepted'
  const selected = phase === 'selected' || phase === 'generating'

  const reset = () => {
    setPhase('off')
    setVariant(0)
    setDensity(50)
    setColor(50)
  }

  const cardVars = { '--p-density': density, '--p-color': color } as CSSProperties

  return (
    <div className="relative overflow-hidden rounded border border-line bg-card">
      {/* 状态播报 */}
      <div aria-live="polite" className="sr-only">
        {phase === 'off' && '模拟未开始'}
        {phase === 'live' && 'Impeccable live 已激活，请点选示例卡片'}
        {phase === 'selected' && '已选中示例卡片，可生成变体'}
        {phase === 'generating' && '正在按三条主轴生成变体…'}
        {phase === 'variants' && `变体 ${variant + 1} 已热替换，可切换变体或调节参数`}
        {phase === 'accepted' && '已接受：模拟写回源码完成'}
      </div>

      <div className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium">演示目标：会员定价卡</p>
          <Pill>交互模拟 · 非真实注入</Pill>
        </div>
        <p className="mt-1 text-xs leading-5 text-ink-faint">
          真实流程要求本地 dev server + HMR（Vite / Next / SvelteKit / Astro / Nuxt / 纯 HTML），仅限本地 checkout。
        </p>
      </div>

      <div className="grid gap-5 p-4 lg:grid-cols-[1fr_240px]">
        {/* 示例卡片（live 阶段可点选） */}
        <div className="relative">
          {live && (
            <p className="mb-2 flex items-center gap-1.5 text-xs text-[#2563eb]">
              <MousePointerClick size={13} aria-hidden />
              {phase === 'live' ? '点选下方卡片（或聚焦后按 Enter）' : '已选中，生成变体试试'}
            </p>
          )}
          <button
            type="button"
            disabled={!live || selected}
            aria-label="选中演示卡片"
            onClick={() => setPhase('selected')}
            className={`demo-card v${variant} block w-full text-left ${live && !selected ? 'selectable' : ''} ${selected ? 'selected' : ''} disabled:cursor-default`}
            style={cardVars}
          >
            {variant === 2 && <span aria-hidden className="demo-v2band -mx-1 mb-3 block w-[calc(100%+8px)]" />}
            <span aria-hidden className="demo-accentbar mb-3 block" />
            <span className="demo-title block">年度会员</span>
            <span className="mt-1 block text-2xl font-bold tracking-tight">
              ¥1,299
              <span className="text-sm font-normal text-ink-faint">/年</span>
            </span>
            <ul className="demo-list mt-3 grid gap-1.5 text-[13px] leading-6 text-ink-soft">
              <li>· 全部进阶模板</li>
              <li>· 每月 500 次生成额度</li>
              <li>· 优先客服响应</li>
            </ul>
            <span className="demo-cta mt-4 inline-block rounded">立即开通</span>
          </button>

          {/* live 徽标（复刻图三样式，仅出现在演示容器内） */}
          {live && (
            <span
              className={`absolute -top-1 right-0 inline-flex translate-y-[-40%] items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shadow-sm ${
                phase === 'accepted' ? 'bg-ok text-white' : 'bg-ink text-paper'
              }`}
            >
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${phase === 'accepted' ? 'bg-[#bde3c6]' : 'live-dot bg-[#7ddc8f]'}`} />
              Impeccable live
            </span>
          )}
        </div>

        {/* 控制台 */}
        <div className="space-y-3">
          {phase === 'off' && (
            <button
              type="button"
              onClick={() => setPhase('live')}
              className="w-full rounded bg-ink px-3 py-2.5 font-mono text-sm text-paper hover:bg-black"
            >
              $ /impeccable live
            </button>
          )}

          {phase === 'live' && (
            <p className="rounded border border-line bg-paper px-3 py-2 text-xs leading-5 text-ink-soft">
              徽标已亮起。在真实环境中，此刻你可以在页面上直接点选任意元素 → 选设计动作 → 加批注。
            </p>
          )}

          {phase === 'selected' && (
            <div className="space-y-2">
              <p className="text-xs leading-5 text-ink-soft">已锁定品牌身份，agent 将沿三条不同主轴各出一个变体。</p>
              <button type="button" onClick={() => setPhase('generating')} className="w-full rounded bg-accent px-3 py-2 text-sm text-white hover:bg-accent-deep">
                生成 3 个变体
              </button>
              <button type="button" onClick={() => setPhase('live')} className="w-full rounded border border-line bg-card px-3 py-1.5 text-xs text-ink-soft hover:border-accent">
                取消选择
              </button>
            </div>
          )}

          {phase === 'generating' && (
            <p className="rounded border border-line bg-paper px-3 py-2 text-xs leading-5 text-ink-soft">
              <span aria-hidden className="review-blink">●</span> 热替换中…（HMR 原地切换，不刷新页面）
            </p>
          )}

          {(phase === 'variants' || phase === 'accepted') && (
            <div className="space-y-3">
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  aria-label="上一个变体"
                  onClick={() => setVariant((v) => (v + 2) % 3)}
                  className="rounded border border-line bg-card p-1.5 text-ink-soft hover:border-accent hover:text-accent"
                >
                  <ChevronLeft size={14} aria-hidden />
                </button>
                {VARIANT_LABELS.map((label, i) => (
                  <button
                    key={label}
                    type="button"
                    aria-pressed={variant === i}
                    onClick={() => setVariant(i)}
                    title={VARIANT_AXES[i]}
                    className={`flex-1 rounded border px-1 py-1.5 text-xs ${
                      variant === i ? 'border-accent bg-accent-soft font-medium text-accent-deep' : 'border-line bg-card text-ink-soft hover:border-accent'
                    }`}
                  >
                    {label}
                  </button>
                ))}
                <button
                  type="button"
                  aria-label="下一个变体"
                  onClick={() => setVariant((v) => (v + 1) % 3)}
                  className="rounded border border-line bg-card p-1.5 text-ink-soft hover:border-accent hover:text-accent"
                >
                  <ChevronRight size={14} aria-hidden />
                </button>
              </div>
              <p className="text-[11px] leading-4 text-ink-faint">当前主轴：{VARIANT_AXES[variant]}</p>

              {/* 参数旋钮：直改 CSS 变量，零延迟 */}
              <fieldset className="rounded border border-line bg-paper p-3" disabled={!knobsEnabled}>
                <legend className="flex items-center gap-1 px-1 text-xs font-medium text-ink-soft">
                  <SlidersHorizontal size={12} aria-hidden />
                  实时参数（0~4 个/变体）
                </legend>
                <label className="mt-1 block text-xs text-ink-soft" htmlFor="knob-density">
                  密度 <span className="font-mono text-ink-faint">{density}</span>
                </label>
                <input
                  id="knob-density"
                  type="range"
                  min={0}
                  max={100}
                  value={density}
                  disabled={!knobsEnabled}
                  onChange={(e) => setDensity(Number(e.target.value))}
                  className="w-full accent-[#b23a24]"
                />
                <label className="mt-2 block text-xs text-ink-soft" htmlFor="knob-color">
                  色彩量 <span className="font-mono text-ink-faint">{color}</span>
                </label>
                <input
                  id="knob-color"
                  type="range"
                  min={0}
                  max={100}
                  value={color}
                  disabled={!knobsEnabled}
                  onChange={(e) => setColor(Number(e.target.value))}
                  className="w-full accent-[#b23a24]"
                />
              </fieldset>

              {phase === 'variants' ? (
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => setPhase('accepted')} className="inline-flex items-center justify-center gap-1 rounded bg-ok px-3 py-2 text-sm text-white hover:opacity-90">
                    <Check size={14} aria-hidden />
                    Accept
                  </button>
                  <button type="button" onClick={() => setPhase('live')} className="inline-flex items-center justify-center gap-1 rounded border border-line bg-card px-3 py-2 text-sm text-ink-soft hover:border-accent">
                    <X size={14} aria-hidden />
                    Discard
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="rounded border border-ok/40 bg-[#e7efe9] px-3 py-2 text-xs leading-5 text-ok">
                    已写回源码（模拟）—— 真实流程会把选中变体写入你的组件并清理脚手架。
                  </p>
                  <button type="button" onClick={reset} className="inline-flex items-center gap-1 text-xs text-ink-soft underline decoration-line underline-offset-2 hover:text-accent">
                    <RotateCcw size={12} aria-hidden />
                    重置演示
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <p className="border-t border-line bg-paper/60 px-4 py-3 text-xs leading-6 text-ink-soft">
        <span className="font-medium text-ink">机制</span>：变体生成时品牌身份锁定、三条主轴各出一版；每个变体可带 0~4 个 CSS 变量驱动的实时参数旋钮，拖动零再生成本；Accept 写回源码并清理脚手架，Discard 原样还原。
      </p>
    </div>
  )
}

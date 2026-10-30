import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Pill, SectionHeader } from '../components/ui'

interface Layer {
  id: string
  name: string
  role: string
  writes: string
  reads: string
  detail: string
}

const LAYERS: Layer[] = [
  {
    id: 'brief',
    name: 'surface brief',
    role: '单界面策略层',
    writes: 'shape 产出，用户确认后冻结',
    reads: '该界面的构建 / 评审命令',
    detail: '某一路由或页面的方向契约，含 THESIS / STORY / FIRST VIEWPORT 等六块。一个界面一份，确保该页的一切改动服务于同一策略。',
  },
  {
    id: 'design',
    name: 'DESIGN.md',
    role: '视觉系统层',
    writes: 'document 从既有代码生成；redesign 时替换',
    reads: '所有涉及视觉的命令',
    detail: '字体、色板、组件语言。有它在，后续改动保持在品牌之内；没有它不等于 greenfield——new-work 会决定保留、扩展还是替换现有世界。',
  },
  {
    id: 'product',
    name: 'PRODUCT.md',
    role: '产品事实层',
    writes: 'init 写入（每项目一次）',
    reads: '每一条命令',
    detail: '用户、定位、约束、品牌承诺。绝不放视觉决策——它是所有命令共同的地面事实。',
  },
]

const MODES = [
  { name: 'Persuade', desc: '说服转化：设计即产品，全力以赴' },
  { name: 'Operate', desc: '完成任务：可扫描性优先，品牌藏在细节' },
  { name: 'Read', desc: '阅读理解：结构服务理解（本页即此模式）' },
  { name: 'Experience', desc: '沉浸体验：作品主导，界面后退' },
]

/** 上下文文件机制：三层金字塔 + 四种访客模式 */
export function ContextFilesSection() {
  const [open, setOpen] = useState<string>('product')
  return (
    <section id="context" aria-label="上下文文件机制" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="06 / 上下文文件"
          title="三层金字塔：命令为什么懂你"
          lead="init 写产品事实，document 提视觉系统，shape 冻结单界面策略。三层各管一段，谁写入、何时读，见下。"
        />

        {/* 金字塔（自上而下：brief → design → product） */}
        <div className="flex flex-col items-center gap-2">
          {LAYERS.map((layer, i) => {
            const widths = ['w-full sm:w-3/4', 'w-full sm:w-7/8', 'w-full']
            const isOpen = open === layer.id
            return (
              <div key={layer.id} className={`${widths[i]} flex flex-col items-center`}>
                <button
                  type="button"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? '' : layer.id)}
                  className={`flex w-full items-center justify-between gap-2 rounded border px-4 py-2.5 text-left transition-colors ${
                    isOpen ? 'border-accent bg-accent-soft' : 'border-line bg-card hover:border-accent'
                  }`}
                >
                  <span className="flex flex-wrap items-baseline gap-x-3">
                    <code className={`font-mono text-sm font-semibold ${isOpen ? 'text-accent-deep' : 'text-ink'}`}>{layer.name}</code>
                    <span className="text-xs text-ink-soft">{layer.role}</span>
                  </span>
                  <ChevronDown size={15} aria-hidden className={`shrink-0 text-ink-faint transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </button>
                {isOpen && (
                  <div className="w-full rounded-b border border-t-0 border-accent bg-card px-4 py-3 text-[13px] leading-6">
                    <p className="text-ink-soft">{layer.detail}</p>
                    <dl className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
                      <div className="flex gap-2">
                        <dt className="shrink-0 text-ink-faint">谁写入</dt>
                        <dd className="text-ink">{layer.writes}</dd>
                      </div>
                      <div className="flex gap-2">
                        <dt className="shrink-0 text-ink-faint">何时读</dt>
                        <dd className="text-ink">{layer.reads}</dd>
                      </div>
                    </dl>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* 四种访客模式 */}
        <h3 className="mb-3 mt-8 text-sm font-medium">四种访客模式（野心的刻度尺）</h3>
        <ul className="grid gap-2 sm:grid-cols-2">
          {MODES.map((m) => (
            <li key={m.name} className="rounded border border-line bg-card px-3.5 py-2.5">
              <Pill tone="ink">{m.name}</Pill>
              <p className="mt-1.5 text-xs leading-5 text-ink-soft">{m.desc}</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs leading-6 text-ink-soft">
          另有两个构建取向：<span className="font-medium text-ink">comp-first</span>（先生成高保真效果图再照建，更大胆更慢）与{' '}
          <span className="font-medium text-ink">code-first</span>（直接代码构建，更精简更快）。
        </p>
      </div>
    </section>
  )
}

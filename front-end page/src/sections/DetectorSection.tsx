import { Bot, Chrome, Terminal } from 'lucide-react'
import { CodeBlock, Pill, SectionHeader } from '../components/ui'

const WAYS = [
  { icon: Bot, title: 'Agent hook', desc: '在 agent 内以 hook 方式运行：每次编辑 UI 文件后自动检测，无需手动触发。' },
  { icon: Terminal, title: 'CLI', desc: 'npx impeccable detect 可扫目录或 URL，能接入 CI；退出码 2 表示有发现，0 表示干净。' },
  { icon: Chrome, title: 'Chrome 扩展', desc: '浏览器 overlay 直接在页面上可视化标注 AI 套路特征与质量问题。' },
]

/** 检测器：62 条确定性规则、三种运行方式 */
export function DetectorSection() {
  return (
    <section id="detector" aria-label="检测器" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="07 / 检测器"
          title="Slopp Detector：62 条规则抓套路"
          lead="确定性规则、无 LLM、无 API key：Inter 全家桶、紫蓝渐变、卡片套卡片、灰字压彩底、圆角方块图标……顺带抓拥挤留白、跳级标题等质量问题。"
        />

        <div className="grid gap-3 sm:grid-cols-3">
          {WAYS.map((w) => (
            <div key={w.title} className="rounded border border-line bg-card px-4 py-3.5">
              <w.icon size={18} aria-hidden className="text-accent" />
              <h3 className="mt-2 text-sm font-medium">{w.title}</h3>
              <p className="mt-1 text-xs leading-6 text-ink-soft">{w.desc}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <p className="mb-2 flex items-center gap-2 text-sm font-medium">
              终端输出示意 <Pill>模拟</Pill>
            </p>
            <CodeBlock
              label="CLI"
              code={`$ npx impeccable detect src/
✔ Scanned 14 files · 62 rules
⚠ 3 findings
  warn  default-font-stack     src/theme.css:12
  warn  gradient-banner        src/Hero.tsx:31
  info  rounded-square-icon    src/Features.tsx:8
✖ exit code 2 — findings found`}
            />
          </div>
          <div className="rounded border border-line bg-card px-4 py-3.5 text-[13px] leading-7">
            <h3 className="text-sm font-medium">误报与忽略</h3>
            <p className="mt-1 text-ink-soft">
              规则宁可错报也不放过。可在 .impeccable/ 配置中按规则或路径忽略（语法以上游文档为准）；brief 明确要求的美学受「brief 优先」原则保护，不会被当作套路。
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

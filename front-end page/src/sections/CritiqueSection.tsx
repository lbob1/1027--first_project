import { SectionHeader } from '../components/ui'
import { CommandReplay } from '../demo/CommandReplay'
import { REVIEW_PANELS } from '../data/critiqueSample'

/** 评审循环：以 /impeccable critique 首页 为入口（对应参考图二） */
export function CritiqueSection() {
  return (
    <section id="critique" aria-label="评审循环" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="04 / 评审循环"
          title="agent 改完自己说好？派个评审"
          lead="critique 是带启发式打分的 UX 评审，audit 是技术质量报告（无障碍 / 性能 / 响应式，P0~P3 分级）。下面回放一次完整评审："
        />

        {/* 双评审示意 */}
        <div className="mb-5 grid gap-3 sm:grid-cols-2">
          {REVIEW_PANELS.map((p) => (
            <div key={p.tag} className="rounded border border-line bg-card px-4 py-3">
              <p className="text-sm font-medium">{p.tag}</p>
              <p className="mt-1 text-xs leading-6 text-ink-soft">{p.desc}</p>
            </div>
          ))}
        </div>

        <CommandReplay />
      </div>
    </section>
  )
}

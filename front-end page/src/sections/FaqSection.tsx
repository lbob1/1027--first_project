import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { FAQS } from '../data/faq'
import { SectionHeader } from '../components/ui'

/** FAQ 与排障：手风琴（aria-expanded 正确标注） */
export function FaqSection() {
  const [open, setOpen] = useState<number>(0)
  return (
    <section id="faq" aria-label="常见问题与排障" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader num="08 / FAQ 与排障" title="卡住了先看这里" lead="环境自检的第一入口是 /impeccable doctor。" />
        <ul className="divide-y divide-line rounded border border-line bg-card">
          {FAQS.map((f, i) => {
            const isOpen = open === i
            return (
              <li key={f.q}>
                <button
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={`faq-panel-${i}`}
                  id={`faq-btn-${i}`}
                  onClick={() => setOpen(isOpen ? -1 : i)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium hover:bg-paper"
                >
                  {f.q}
                  <ChevronDown size={15} aria-hidden className={`shrink-0 text-ink-faint transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </button>
                {isOpen && (
                  <div id={`faq-panel-${i}`} role="region" aria-labelledby={`faq-btn-${i}`} className="px-4 pb-4 text-[13px] leading-7 text-ink-soft">
                    {f.a}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}

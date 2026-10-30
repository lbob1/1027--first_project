import { ArrowRight, Command } from 'lucide-react'

/** Hero：一句话定位 + Before/After 对比（复刻 README Villa Castagneto 案例布局，示意） */
export function HeroSection() {
  return (
    <section id="hero" aria-label="是什么" className="scroll-mt-16 px-4 pb-14 pt-10 sm:px-8 sm:pt-14">
      <p className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1 text-xs text-ink-soft">
        <Command size={12} aria-hidden className="text-accent" />
        Impeccable · Apache-2.0 · 基于上游 commit 02523ae
      </p>
      <h1 className="mt-5 max-w-[38rem] font-display text-4xl font-semibold leading-[1.15] tracking-wide sm:text-5xl">
        给你的编码智能体的
        <span className="text-accent">设计词汇表</span>
      </h1>
      <p className="mt-4 max-w-[40rem] text-[15px] leading-8 text-ink-soft">
        用 <code className="font-mono text-sm text-accent-deep">polish</code> 和{' '}
        <code className="font-mono text-sm text-accent-deep">bolder</code> 操控，用{' '}
        <code className="font-mono text-sm text-accent-deep">critique</code> 和{' '}
        <code className="font-mono text-sm text-accent-deep">audit</code> 评审，在 AI 套路上线前抓住它。
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <a
          href="#install"
          className="inline-flex items-center gap-1.5 rounded bg-ink px-4 py-2.5 text-sm font-medium text-paper hover:bg-black"
        >
          开始安装
          <ArrowRight size={15} aria-hidden />
        </a>
        <a
          href="#commands"
          className="inline-flex items-center rounded border border-line bg-card px-4 py-2.5 text-sm text-ink hover:border-accent hover:text-accent"
        >
          先看 24 个命令
        </a>
      </div>

      {/* 数据条 */}
      <dl className="mt-8 grid max-w-[34rem] grid-cols-2 gap-px overflow-hidden rounded border border-line bg-line sm:grid-cols-4">
        {[
          ['24', '条命令'],
          ['62', '条检测规则'],
          ['20+', '支持的工具'],
          ['0', 'API key'],
        ].map(([n, label]) => (
          <div key={label} className="bg-card px-3 py-2.5">
            <dt className="sr-only">{label}</dt>
            <dd>
              <span className="font-mono text-lg font-bold text-accent-deep">{n}</span>
              <span className="ml-1.5 text-xs text-ink-soft">{label}</span>
            </dd>
          </div>
        ))}
      </dl>

      {/* Before / After */}
      <div className="mt-10">
        <h2 className="text-sm font-medium text-ink">同一模型、同一 brief 的两种结局（示意复刻 README 案例）</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {/* Without：套路脸 */}
          <figure className="overflow-hidden rounded border border-line">
            <div className="bg-[#f7f1e3] px-5 py-6">
              <p className="text-center font-serif text-xl font-light tracking-wide text-[#6b6355]">
                Villa <em>Castagneto</em>
              </p>
              <p className="mt-2 text-center text-[11px] leading-5 text-[#8d8574]">利古里亚海岸的十四间房家庭旅馆</p>
              <div className="mt-3 flex justify-center gap-2">
                <span className="rounded-full border border-[#b7ae9c] px-3 py-1 text-[10px] text-[#6b6355]">预订客房</span>
                <span className="rounded-full border border-[#b7ae9c] px-3 py-1 text-[10px] text-[#6b6355]">了解我们</span>
              </div>
              <div className="mx-auto mt-4 flex h-24 w-full max-w-[210px] flex-col items-center justify-center rounded-xl border border-[#ddd3bd] bg-[#efe7d2]">
                <span aria-hidden className="h-8 w-8 rounded-full bg-[#d9cba6]" />
                <span aria-hidden className="mt-1 h-2 w-24 rounded-full bg-[#d9cba6]" />
              </div>
            </div>
            <figcaption className="border-t border-line bg-card px-4 py-2.5 text-xs leading-5 text-ink-soft">
              <span className="font-medium text-ink">没有 Impeccable：</span>
              米色底、细衬线加斜体点缀、药丸按钮、圆角卡片插画 —— 得体的默认，也是千篇一律。
            </figcaption>
          </figure>

          {/* With：一幅画面 */}
          <figure className="overflow-hidden rounded border border-line">
            <div className="bg-[#14161c] px-5 py-6">
              <svg viewBox="0 0 260 120" className="w-full" role="img" aria-label="夜景版画示意：海上望向悬崖上的别墅">
                <circle cx="216" cy="26" r="13" fill="none" stroke="#b23a24" strokeWidth="1.5" />
                <path d="M8 96 L60 60 L84 74 L128 44 L172 66 L214 54 L252 88" fill="none" stroke="#e8e0cf" strokeWidth="1" />
                <path d="M118 44 L142 44 L140 30 L128 22 L118 30 Z" fill="none" stroke="#e8e0cf" strokeWidth="1.2" />
                <path d="M124 36 h4 M132 36 h4" stroke="#b23a24" strokeWidth="1.5" />
                <path d="M14 106 q8 -5 16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0" fill="none" stroke="#3d4450" strokeWidth="1.2" />
              </svg>
              <p className="mt-3 text-center font-display text-xl font-semibold uppercase tracking-[0.08em] text-[#f2ead6]">
                The House <span className="text-accent">at Night</span>
              </p>
              <div className="mt-4 grid grid-cols-12 gap-px bg-[#2a2e38]" aria-hidden>
                {Array.from({ length: 12 }).map((_, i) => (
                  <span key={i} className={`py-1 text-center font-mono text-[8px] ${i === 6 ? 'bg-accent text-white' : 'bg-[#14161c] text-[#7c8494]'}`}>
                    {'JFMAMJJASOND'[i]}
                  </span>
                ))}
              </div>
            </div>
            <figcaption className="border-t border-line bg-card px-4 py-2.5 text-xs leading-5 text-ink-soft">
              <span className="font-medium text-ink">使用 Impeccable：</span>
              围绕一幅画面构建 —— 「夜里从海上看到的房子」，全幅版画夜景 + 压缩标题 + 月份条。
            </figcaption>
          </figure>
        </div>
      </div>
    </section>
  )
}

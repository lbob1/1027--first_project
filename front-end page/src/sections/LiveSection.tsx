import { SectionHeader } from '../components/ui'
import { LiveSimulator } from '../demo/LiveSimulator'

/** Live 实时迭代：Impeccable live 徽标开场（对应参考图三） */
export function LiveSection() {
  return (
    <section id="live" aria-label="实时迭代" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="05 / 实时迭代"
          title="页角亮起 Impeccable live"
          lead="运行 /impeccable live 后，浏览器出现工具栏与状态徽标：在页面上直接点选元素 → 选设计动作（可加批注/涂鸦）→ agent 热替换生成 3 个变体 → 满意就 Accept 写回源码。"
        />
        <LiveSimulator />
        <p className="mt-3 text-xs leading-6 text-ink-faint">
          兄弟命令：<code className="font-mono">/impeccable generate 3 bolder hero</code> 为指定元素批量生成变体，无需手动点选。
        </p>
      </div>
    </section>
  )
}

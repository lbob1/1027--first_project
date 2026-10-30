import { SectionHeader } from '../components/ui'
import { WorkflowStepper } from '../demo/WorkflowStepper'

/** 核心工作流：三步主线（对应参考图一） */
export function WorkflowSection() {
  return (
    <section id="workflow" aria-label="核心工作流" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="02 / 核心工作流"
          title="三步主线"
          lead="先运行 init 写入产品事实 →（可选）若想先规划，中间加一次 shape → 直接描述你想做的页面。之后进入评审与迭代的循环。"
        />
        <WorkflowStepper />
      </div>
    </section>
  )
}

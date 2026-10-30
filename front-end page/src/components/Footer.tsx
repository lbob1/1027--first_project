export function Footer() {
  return (
    <footer className="mt-16 border-t border-line px-4 py-8 pb-12 text-xs leading-6 text-ink-faint sm:px-8">
      <div className="mx-auto max-w-content space-y-1">
        <p>
          Impeccable 使用指南 · 社区交互文档（演示区均为
          <span className="text-ink-soft">交互模拟</span>）· 基于上游
          <a
            className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
            href="https://github.com/pbakaus/impeccable"
            target="_blank"
            rel="noreferrer"
          >
            pbakaus/impeccable
          </a>
          commit 02523ae
        </p>
        <p>
          许可 Apache-2.0 · 官方文档
          <a
            className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
            href="https://impeccable.style/docs"
            target="_blank"
            rel="noreferrer"
          >
            impeccable.style/docs
          </a>
          · 本页按 impeccable 流程规划与自审（shape → build → critique）
        </p>
      </div>
    </footer>
  )
}

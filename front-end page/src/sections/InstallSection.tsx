import { useState } from 'react'
import { CodeBlock, Pill, SectionHeader } from '../components/ui'

const TABS = [
  {
    label: 'npx 安装（推荐）',
    desc: '在项目根目录执行，安装器会自动放置 skill 并提示后续步骤。',
    code: 'npx impeccable install',
  },
  {
    label: '手动复制',
    desc: '已克隆上游仓库时，把 skill 目录复制进项目的 .trae/skills/impeccable（其他工具对应其 skills 目录）。',
    code: '# PowerShell 示例（路径按你的实际位置调整）\nCopy-Item -Recurse path\\to\\impeccable\\skill .trae\\skills\\impeccable',
  },
  {
    label: 'git submodule',
    desc: '希望跟随上游更新时，以子模块方式引入，再把 skill 目录链接/复制为 .trae/skills/impeccable。',
    code: 'git submodule add https://github.com/pbakaus/impeccable third_party/impeccable\n# 再将 third_party/impeccable/skill 复制或链接为 .trae/skills/impeccable',
  },
]

/** 安装：三种方式 Tab 切换 + 装后重启提示 */
export function InstallSection() {
  const [tab, setTab] = useState(0)
  return (
    <section id="install" aria-label="安装" className="scroll-mt-16 border-t border-line px-4 py-14 sm:px-8">
      <div className="mx-auto max-w-content">
        <SectionHeader
          num="01 / 安装"
          title="怎么装"
          lead="支持 Claude Code、Cursor、Codex CLI、GitHub Copilot、Devin、Trae 等 20+ 工具。任选其一："
        />
        <div role="tablist" aria-label="安装方式" className="flex flex-wrap gap-2">
          {TABS.map((t, i) => (
            <button
              key={t.label}
              role="tab"
              id={`install-tab-${i}`}
              aria-selected={tab === i}
              aria-controls="install-panel"
              onClick={() => setTab(i)}
              onKeyDown={(e) => {
                if (e.key === 'ArrowRight') setTab((i + 1) % TABS.length)
                if (e.key === 'ArrowLeft') setTab((i + TABS.length - 1) % TABS.length)
              }}
              className={`rounded-full border px-3 py-1.5 text-sm ${
                tab === i ? 'border-accent bg-accent-soft font-medium text-accent-deep' : 'border-line bg-card text-ink-soft hover:border-accent hover:text-accent'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div id="install-panel" role="tabpanel" aria-labelledby={`install-tab-${tab}`} className="mt-4 space-y-3">
          <p className="text-sm leading-7 text-ink-soft">{TABS[tab].desc}</p>
          <CodeBlock code={TABS[tab].code} label="终端" />
        </div>
        <div className="mt-5 rounded border border-accent/40 bg-accent-soft/60 px-4 py-3 text-sm leading-7">
          <Pill tone="accent">装好后</Pill>
          <span className="ml-2 text-ink">
            重启 Trae（或所用的编码工具），然后运行第一条命令{' '}
            <code className="font-mono text-accent-deep">/impeccable init</code>
          </span>
        </div>
      </div>
    </section>
  )
}

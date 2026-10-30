import { useCallback, useEffect, useState } from 'react'
import type { Command } from './data/commands'
import { SECTIONS } from './data/sections'
import { usePrefersReducedMotion, useScrollSpy } from './hooks'
import { CommandDrawer } from './components/CommandDrawer'
import { Footer } from './components/Footer'
import { MobileBar, MobileDrawer, SideNav } from './components/SideNav'
import { HeroSection } from './sections/HeroSection'
import { InstallSection } from './sections/InstallSection'
import { WorkflowSection } from './sections/WorkflowSection'
import { CommandReferenceSection } from './sections/CommandReferenceSection'
import { CritiqueSection } from './sections/CritiqueSection'
import { LiveSection } from './sections/LiveSection'
import { ContextFilesSection } from './sections/ContextFilesSection'
import { DetectorSection } from './sections/DetectorSection'
import { FaqSection } from './sections/FaqSection'

const SECTION_IDS = SECTIONS.map((s) => s.id)

export default function App() {
  const active = useScrollSpy(SECTION_IDS)
  const reduced = usePrefersReducedMotion()
  const [detail, setDetail] = useState<Command | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const navigateTo = useCallback(
    (id: string) => {
      document.getElementById(id)?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' })
    },
    [reduced],
  )

  // scrollspy → URL hash 同步（可分享锚点，不产生历史记录）
  useEffect(() => {
    if (SECTION_IDS.includes(active) && window.location.hash !== `#${active}`) {
      history.replaceState(null, '', `#${active}`)
    }
  }, [active])

  // 初始加载时若带锚点则定位（React 挂载晚于浏览器原生锚点处理）
  useEffect(() => {
    const h = window.location.hash.slice(1)
    if (h && SECTION_IDS.includes(h)) {
      requestAnimationFrame(() => document.getElementById(h)?.scrollIntoView())
    }
  }, [])

  // 抽屉打开时锁定页面滚动
  useEffect(() => {
    const locked = detail !== null || mobileNavOpen
    document.body.style.overflow = locked ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [detail, mobileNavOpen])

  // `/` 快捷键聚焦搜索（向 agent 命令习惯致敬）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '/') return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      e.preventDefault()
      const desktop = window.matchMedia('(min-width: 1024px)').matches
      if (!desktop) setMobileNavOpen(true)
      requestAnimationFrame(() => {
        document.getElementById(desktop ? 'search-desktop' : 'search-mobile')?.focus()
      })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="min-h-screen">
      <a
        href="#hero"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[60] focus:rounded focus:bg-ink focus:px-3 focus:py-2 focus:text-sm focus:text-paper"
      >
        跳到内容
      </a>

      {/* 桌面侧导航 */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-line bg-card lg:block">
        <SideNav
          active={active}
          searchId="search-desktop"
          onNavigate={navigateTo}
          onOpenCommand={(c) => setDetail(c)}
        />
      </aside>

      {/* 移动端顶栏与抽屉 */}
      <MobileBar onOpen={() => setMobileNavOpen(true)} />
      <MobileDrawer
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        active={active}
        searchId="search-mobile"
        onNavigate={navigateTo}
        onOpenCommand={(c) => setDetail(c)}
      />

      {/* 内容区 */}
      <main className="lg:ml-60">
        <div className="mx-auto max-w-content">
          <HeroSection />
          <InstallSection />
          <WorkflowSection />
          <CommandReferenceSection onOpenCommand={(c) => setDetail(c)} sectionSearchId="command-search" />
          <CritiqueSection />
          <LiveSection />
          <ContextFilesSection />
          <DetectorSection />
          <FaqSection />
        </div>
        <Footer />
      </main>

      <CommandDrawer command={detail} onClose={() => setDetail(null)} />
    </div>
  )
}

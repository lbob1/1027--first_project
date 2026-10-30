import { useEffect, useState } from 'react'
import { checkHealth } from '../api'
import type { View } from '../App'

const NAV: { id: View; label: string }[] = [
  { id: 'chat', label: '对话问答' },
  { id: 'docs', label: '文档管理' },
]

export default function Sidebar({
  open,
  view,
  onNavigate,
  onNewChat,
}: {
  open: boolean
  view: View
  onNavigate: (v: View) => void
  onNewChat: () => void
}) {
  const [ok, setOk] = useState<boolean | null>(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const r = await checkHealth()
      if (alive) setOk(r)
    }
    tick()
    const t = setInterval(tick, 30000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  return (
    <aside className={`sidebar${open ? ' open' : ''}`}>
      <div className="brand">
        Pyknora
        <div className="brand-bar" aria-hidden="true" />
      </div>
      <button className="newbtn" onClick={onNewChat}>
        ＋ 新对话
      </button>
      <nav className="nav" aria-label="主导航">
        {NAV.map((n) => (
          <button
            key={n.id}
            className={view === n.id ? 'navi on' : 'navi'}
            aria-current={view === n.id ? 'page' : undefined}
            onClick={() => onNavigate(n.id)}
          >
            {n.label}
          </button>
        ))}
      </nav>
      <div className="sidefoot">
        {ok === false ? (
          <>
            <span className="dotbad" aria-hidden="true" />
            服务未连接（请启动后端）
          </>
        ) : (
          <>
            <span className="dotok" aria-hidden="true" />
            服务正常
          </>
        )}
      </div>
    </aside>
  )
}

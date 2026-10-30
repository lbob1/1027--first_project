import { useEffect, useState } from 'react'
import { getToken, logout } from './api'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import ChatView from './components/ChatView'
import DocsView from './components/DocsView'
import LoginView from './components/LoginView'

export type View = 'chat' | 'docs'
export type Theme = 'paper' | 'light' | 'dark' | 'aurora'

const THEMES: Theme[] = ['paper', 'light', 'dark', 'aurora']

export default function App() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('pyknora-theme')
    return THEMES.includes(saved as Theme) ? (saved as Theme) : 'paper'
  })
  const [authed, setAuthed] = useState(() => !!getToken())
  const [view, setView] = useState<View>('chat')
  const [navOpen, setNavOpen] = useState(false)
  const [chatKey, setChatKey] = useState(0)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('pyknora-theme', theme)
  }, [theme])

  if (!authed) {
    return <LoginView onLogin={() => setAuthed(true)} />
  }

  return (
    <div className="app">
      {navOpen && (
        <button className="scrim" aria-label="关闭菜单" onClick={() => setNavOpen(false)} />
      )}
      <Sidebar
        open={navOpen}
        view={view}
        onNavigate={(v) => {
          setView(v)
          setNavOpen(false)
        }}
        onNewChat={() => {
          setChatKey((k) => k + 1)
          setView('chat')
          setNavOpen(false)
        }}
      />
      <div className="main">
        <TopBar
          view={view}
          theme={theme}
          onTheme={setTheme}
          onMenu={() => setNavOpen((o) => !o)}
        />
        {view === 'chat' ? (
          <ChatView
            key={chatKey}
            onAuthError={() => {
              logout()
              setAuthed(false)
            }}
          />
        ) : (
          <DocsView
            onAuthError={() => {
              logout()
              setAuthed(false)
            }}
          />
        )}
      </div>
    </div>
  )
}

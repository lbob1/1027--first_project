import type { Theme, View } from '../App'

const TITLES: Record<View, string> = { chat: '知识库问答', docs: '文档管理' }
const NAMES: Record<Theme, string> = {
  paper: '暖纸',
  light: '纯白',
  dark: '深黑',
  aurora: '彩虹·晨光',
}
const SWATCH: Record<Theme, string> = {
  paper: '#f0e6d2',
  light: '#ffffff',
  dark: '#141414',
  aurora: 'linear-gradient(135deg,#f6d8a8,#f3c6d8,#c9d4f2,#bfe8d9)',
}
const ORDER: Theme[] = ['paper', 'light', 'dark', 'aurora']

export default function TopBar({
  view,
  theme,
  onTheme,
  onMenu,
}: {
  view: View
  theme: Theme
  onTheme: (t: Theme) => void
  onMenu: () => void
}) {
  return (
    <header className="topbar">
      <button className="hamburger" aria-label="打开菜单" onClick={onMenu}>
        ☰
      </button>
      <strong className="top-title">{TITLES[view]}</strong>
      <div className="top-right">
        <div className="themeswitch" role="group" aria-label="主题切换">
          {ORDER.map((t) => (
            <button
              key={t}
              className={`tdot t-${t}${theme === t ? ' on' : ''}`}
              style={{ background: SWATCH[t] }}
              aria-label={`切换到${NAMES[t]}主题`}
              aria-pressed={theme === t}
              title={NAMES[t]}
              onClick={() => onTheme(t)}
            />
          ))}
        </div>
        <span className="pill">本地演示</span>
      </div>
    </header>
  )
}

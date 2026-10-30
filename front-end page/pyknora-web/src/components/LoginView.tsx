import { useState, type FormEvent } from 'react'
import { getWsId, login, setWsId } from '../api'

export default function LoginView({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [wsid, setWsid] = useState(getWsId())
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    setErr('')
    setBusy(true)
    try {
      await login(username.trim(), password)
      if (wsid.trim()) setWsId(wsid.trim())
      onLogin()
    } catch (ex) {
      setErr((ex as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="loginwrap">
      <form className="login" onSubmit={submit}>
        <div className="brand" style={{ fontSize: 22 }}>
          Pyknora
          <div className="brand-bar" aria-hidden="true" />
        </div>
        <p className="sub">登录知识库问答（演示账号由脚本预置）</p>
        <input
          className="field"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />
        <input
          className="field"
          type="password"
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        <input
          className="field"
          placeholder="工作区 ID（uuid，演示环境已预填）"
          value={wsid}
          onChange={(e) => setWsid(e.target.value)}
        />
        {err && <div className="errmsg">{err}</div>}
        <button className="sendbtn" disabled={busy}>
          {busy ? '登录中…' : '登录'}
        </button>
      </form>
    </div>
  )
}

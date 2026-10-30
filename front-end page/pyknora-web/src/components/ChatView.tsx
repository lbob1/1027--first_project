import { useRef, useState } from 'react'
import { AuthError, streamChat, type SourceHit } from '../api'
import { colorFor } from '../spectrum' // 光谱六色：同一文档恒定一色（与文档管理一致）

type Msg = {
  role: 'user' | 'ai'
  text: string
  sources?: SourceHit[]
  error?: string
  stopped?: boolean
}

const EXAMPLES = ['知识库里关于检索评估的结论是什么？', '弹性伸缩是怎么计费的？']

export default function ChatView({ onAuthError }: { onAuthError: () => void }) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [openSrc, setOpenSrc] = useState<{ msg: number; file: string } | null>(null)
  const threadRef = useRef(crypto.randomUUID())
  const abortRef = useRef<AbortController | null>(null)
  const areaRef = useRef<HTMLTextAreaElement>(null)

  async function send(raw: string) {
    const q = raw.trim()
    if (!q || busy) return
    setBusy(true)
    setInput('')
    setOpenSrc(null)
    setMessages((m) => [...m, { role: 'user', text: q }, { role: 'ai', text: '' }])
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const patch = (fn: (m: Msg) => Msg) =>
      setMessages((all) => all.map((m, i) => (i === all.length - 1 ? fn(m) : m)))
    try {
      await streamChat({
        question: q,
        threadId: threadRef.current,
        signal: ctrl.signal,
        onSources: (hits) => patch((m) => ({ ...m, sources: hits })),
        onToken: (t) => patch((m) => ({ ...m, text: m.text + t })),
        onError: (code, message) => patch((m) => ({ ...m, error: `(${code}) ${message}` })),
      })
    } catch (e) {
      if ((e as Error).name === 'AbortError') patch((m) => ({ ...m, stopped: true }))
      else if (e instanceof AuthError) onAuthError()
      else patch((m) => ({ ...m, error: (e as Error).message }))
    } finally {
      setBusy(false)
      abortRef.current = null
    }
  }

  function stop() {
    abortRef.current?.abort()
  }

  return (
    <>
      <div className="chatwrap">
        <div className="chat">
          {messages.length === 0 ? (
            <div className="welcome">
              <h1>问点什么吧</h1>
              <p className="sub">知识库已就绪，点击示例或直接输入问题</p>
              <div className="chips">
                {EXAMPLES.map((e) => (
                  <button key={e} className="chip" onClick={() => send(e)}>
                    {e}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => {
              if (m.role === 'user') {
                return (
                  <div key={i} className="msg user">
                    {m.text}
                  </div>
                )
              }
              const groups = new Map<string, SourceHit[]>()
              for (const h of m.sources ?? []) {
                const arr = groups.get(h.filename) ?? []
                arr.push(h)
                groups.set(h.filename, arr)
              }
              const files = [...groups.entries()]
              const total = m.sources?.length ?? 0
              const waiting = busy && i === messages.length - 1 && !m.text
              return (
                <div key={i} className="msg ai">
                  {m.text || (waiting ? '…' : '')}
                  {m.stopped && <span className="stopnote">（已停止）</span>}
                  {m.error && <div className="errmsg">{m.error}</div>}
                  {files.length > 0 && (
                    <div className="srcwrap">
                      <div className="srcbar" role="img" aria-label="来源占比条">
                        {files.map(([f, hits]) => (
                          <i
                            key={f}
                            style={{ width: `${(hits.length / total) * 100}%`, background: colorFor(f) }}
                          />
                        ))}
                      </div>
                      <div className="srcchips">
                        {files.map(([f, hits]) => {
                          const on = openSrc?.msg === i && openSrc.file === f
                          return (
                            <button
                              key={f}
                              className="srcchip"
                              style={{
                                borderColor: colorFor(f),
                                color: colorFor(f),
                                background: on ? 'var(--accent-soft)' : 'transparent',
                              }}
                              aria-expanded={on}
                              onClick={() =>
                                setOpenSrc(on ? null : { msg: i, file: f })
                              }
                            >
                              <i className="kd" style={{ background: colorFor(f) }} />
                              {f} ×{hits.length}
                            </button>
                          )
                        })}
                      </div>
                      {openSrc?.msg === i && groups.has(openSrc.file) && (
                        <div className="srcpanel">
                          {groups.get(openSrc.file)!.slice(0, 3).map((h) => (
                            <div key={h.chunk_id} className="snippet">
                              <span className="snipmeta">
                                第 {h.seq_no} 段 · v{h.version_no}
                              </span>
                              <p>
                                {h.content.length > 140
                                  ? `${h.content.slice(0, 140)}…`
                                  : h.content}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
      <div className="inputbar">
        <div className="inputinner">
          <textarea
            ref={areaRef}
            className="input"
            rows={1}
            placeholder="输入问题，Enter 发送"
            title="Enter 发送 · Shift+Enter 换行"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
          />
          {busy ? (
            <button className="sendbtn stop" onClick={stop}>
              停止
            </button>
          ) : (
            <button className="sendbtn" onClick={() => send(input)}>
              发送
            </button>
          )}
        </div>
      </div>
    </>
  )
}

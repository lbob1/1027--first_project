import { useCallback, useEffect, useRef, useState } from 'react'
import { AuthError, listDocuments, uploadDocument, type DocInfo } from '../api'
import { colorFor } from '../spectrum' // 光谱六色：同一文档恒定一色（与对话来源一致）

const ACCEPT = '.pdf,.docx,.md,.txt'

function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export default function DocsView({ onAuthError }: { onAuthError: () => void }) {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    try {
      setDocs(await listDocuments())
      setError('')
    } catch (e) {
      if (e instanceof AuthError) onAuthError()
      else setError((e as Error).message)
    }
  }, [onAuthError])

  useEffect(() => {
    refresh()
  }, [refresh])

  // 有「处理中」文档时每 4 秒轮询，全部稳定后自动停止
  useEffect(() => {
    if (!docs.some((d) => d.status === 'staging')) return
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [docs, refresh])

  async function upload(files: FileList | null) {
    if (!files || files.length === 0 || busy) return
    setBusy(true)
    setError('')
    try {
      for (const f of Array.from(files)) await uploadDocument(f)
      await refresh()
    } catch (e) {
      if (e instanceof AuthError) onAuthError()
      else setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="docswrap">
      <div className="docs">
        <div
          className={`drop${dragOver ? ' over' : ''}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            upload(e.dataTransfer.files)
          }}
          role="button"
          tabIndex={0}
          aria-disabled={busy}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              fileRef.current?.click()
            }
          }}
        >
          {busy ? '正在上传…' : '拖拽文件到这里，或点击上传'}
          <span className="drophint">支持 PDF / Word / Markdown / 文本，单文件最大 20MB</span>
        </div>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="srfile"
          onChange={(e) => {
            upload(e.target.files)
            e.target.value = ''
          }}
        />
        {error && (
          <p className="docerr" role="alert">
            {error}
          </p>
        )}
        {docs.length === 0 && !error && <p className="notice">还没有文档，上传第一份试试。</p>}
        {docs.map((d) => (
          <div key={d.document_id} className="docrow">
            <i className="dbar" style={{ background: colorFor(d.filename) }} aria-hidden="true" />
            <div className="docmain">
              <span className="docname">{d.filename}</span>
              <span className="docsub">
                v{d.version_no}
                {d.created_at ? ` · ${fmtTime(d.created_at)}` : ''}
              </span>
            </div>
            <span className="meta">
              {d.status === 'staging' && (
                <>
                  <span
                    className="dring"
                    style={{ '--c': colorFor(d.filename) } as React.CSSProperties}
                    aria-hidden="true"
                  />
                  处理中
                </>
              )}
              {d.status === 'active' && (
                <>
                  <span className="dotok" aria-hidden="true" />
                  就绪
                </>
              )}
              {d.status === 'failed' && (
                <>
                  <span className="dotbad" aria-hidden="true" />
                  处理失败
                </>
              )}
              {d.status === 'retired' && (
                <>
                  <span className="dotmut" aria-hidden="true" />
                  已被新版取代
                </>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

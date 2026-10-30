/* Pyknora Web API 层：登录 / 健康检查 / SSE 流式问答 */

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) || 'http://localhost:8000'

export class AuthError extends Error {}

export function getToken(): string | null {
  return localStorage.getItem('pyknora-token')
}
export function logout(): void {
  localStorage.removeItem('pyknora-token')
}
export function getWsId(): string {
  return localStorage.getItem('pyknora-wsid') || (import.meta.env.VITE_WS_ID as string | undefined) || ''
}
export function setWsId(v: string): void {
  localStorage.setItem('pyknora-wsid', v)
}

export async function login(username: string, password: string): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      signal: AbortSignal.timeout(15000),
    })
  } catch (e) {
    const name = (e as Error).name
    if (name === 'TimeoutError' || name === 'AbortError') {
      throw new Error('登录请求超时（后端未响应），请确认后端已启动后重试')
    }
    throw e
  }
  const j = await res.json().catch(() => null)
  if (!res.ok) throw new Error(j?.message || `登录失败（HTTP ${res.status}）`)
  const token: string | undefined = j?.data?.token ?? j?.token
  if (!token) throw new Error('登录响应缺少 token')
  localStorage.setItem('pyknora-token', token)
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/healthz`, { signal: AbortSignal.timeout(5000) })
    return res.ok
  } catch {
    return false
  }
}

export type SourceHit = {
  chunk_id: string
  seq_no: number
  content: string
  filename: string
  version_no: number
  rrf_score?: number
  relevance_score?: number
  sources?: string[]
}

export type StreamHandlers = {
  onSources?: (hits: SourceHit[]) => void
  onToken: (t: string) => void
  onError?: (code: string, message: string) => void
  onDone?: () => void
}

/** POST /api/v1/workspaces/{id}/chat 的 SSE 客户端（sources/token/error/done）。 */
export async function streamChat(
  opts: { question: string; topK?: number; threadId: string; signal: AbortSignal } & StreamHandlers,
): Promise<void> {
  const token = getToken()
  if (!token) throw new AuthError('未登录')
  const ws = getWsId()
  if (!ws) throw new Error('缺少工作区 ID，请在登录页填写')

  const res = await fetch(`${API_BASE}/api/v1/workspaces/${ws}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question: opts.question, top_k: opts.topK ?? 5, thread_id: opts.threadId }),
    signal: opts.signal,
  })
  if (res.status === 401) throw new AuthError('登录已过期，请重新登录')
  if (!res.ok) {
    const j = await res.json().catch(() => null)
    throw new Error(j?.message || `请求失败（HTTP ${res.status}）`)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let event = 'message'
      const dataLines: string[] = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) continue
      let payload: Record<string, unknown>
      try {
        payload = JSON.parse(dataLines.join('\n'))
      } catch {
        continue
      }
      if (event === 'sources') {
        opts.onSources?.((payload.sources as SourceHit[]) ?? [])
      } else if (event === 'token') {
        opts.onToken((payload.token as string) ?? '')
      } else if (event === 'error') {
        opts.onError?.((payload.code as string) ?? 'KN-500', (payload.message as string) ?? '生成中断')
      } else if (event === 'approval_required') {
        opts.onError?.('approval_required', '该请求需要删除审批确认，网页端暂不支持，请通过 API 处理')
      } else if (event === 'done') {
        opts.onDone?.()
        return
      }
      // budget / trace 事件暂不展示
    }
  }
}

/* ---------- 文档管理（P4） ---------- */

export type DocInfo = {
  document_id: string
  filename: string
  created_at: string
  active_version: string | null
  version_no: number
  status: 'staging' | 'active' | 'retired' | 'failed'
}

/** GET /api/v1/workspaces/{id}/documents：工作区文档列表。 */
export async function listDocuments(): Promise<DocInfo[]> {
  const token = getToken()
  if (!token) throw new AuthError('未登录')
  const ws = getWsId()
  if (!ws) throw new Error('缺少工作区 ID，请在登录页填写')
  const res = await fetch(`${API_BASE}/api/v1/workspaces/${ws}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10000),
  })
  if (res.status === 401) throw new AuthError('登录已过期，请重新登录')
  const j = await res.json().catch(() => null)
  if (!res.ok) throw new Error(j?.message || `获取文档列表失败（HTTP ${res.status}）`)
  return (j?.data as DocInfo[]) ?? []
}

/** POST /api/v1/workspaces/{id}/documents：multipart 上传（新文档或追加版本）。 */
export async function uploadDocument(
  file: File,
  documentId?: string,
): Promise<{ status: 'accepted' | 'unchanged'; document_id: string; version_no?: number }> {
  const token = getToken()
  if (!token) throw new AuthError('未登录')
  const ws = getWsId()
  if (!ws) throw new Error('缺少工作区 ID，请在登录页填写')
  const form = new FormData()
  form.append('file', file)
  if (documentId) form.append('document_id', documentId)
  const res = await fetch(`${API_BASE}/api/v1/workspaces/${ws}/documents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    signal: AbortSignal.timeout(60000),
  })
  if (res.status === 401) throw new AuthError('登录已过期，请重新登录')
  const j = await res.json().catch(() => null)
  if (!res.ok) throw new Error(j?.message || `上传失败（HTTP ${res.status}）`)
  return j?.data
}

export type DocStatus = {
  document_id: string
  active_version: string | null
  versions: { version_id: string; version_no: number; status: string; failure_reason: string | null }[]
}

/** GET /api/v1/workspaces/{id}/documents/{doc}/status：单文档各版本状态。 */
export async function getDocumentStatus(documentId: string): Promise<DocStatus> {
  const token = getToken()
  if (!token) throw new AuthError('未登录')
  const ws = getWsId()
  if (!ws) throw new Error('缺少工作区 ID，请在登录页填写')
  const res = await fetch(
    `${API_BASE}/api/v1/workspaces/${ws}/documents/${documentId}/status`,
    {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
    },
  )
  if (res.status === 401) throw new AuthError('登录已过期，请重新登录')
  const j = await res.json().catch(() => null)
  if (!res.ok) throw new Error(j?.message || `查询状态失败（HTTP ${res.status}）`)
  return j?.data
}

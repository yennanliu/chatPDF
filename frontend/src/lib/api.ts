// Central API client (§2.4).
//
// One place for the base URL, request timeout, JSON handling, and error message
// extraction — stores no longer call fetch() directly or hardcode paths.

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''

const DEFAULT_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function _extractError(res: Response): Promise<string> {
  // FastAPI errors are usually {detail: "..."}; fall back to text/status.
  try {
    const data = await res.clone().json()
    if (data && typeof data.detail === 'string') return data.detail
  } catch { /* not JSON */ }
  return (await res.text().catch(() => '')) || res.statusText || `HTTP ${res.status}`
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number
}

async function request(path: string, opts: RequestOptions = {}): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = opts
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal })
    if (!res.ok) throw new ApiError(await _extractError(res), res.status)
    return res
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(`Request timed out after ${timeoutMs / 1000}s`, 0)
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  /** Status that should not throw (e.g. DELETE returning 404). */
  async raw(path: string, opts: RequestOptions = {}, allowStatuses: number[] = []): Promise<Response> {
    try {
      return await request(path, opts)
    } catch (e) {
      if (e instanceof ApiError && allowStatuses.includes(e.status)) {
        return new Response(null, { status: e.status })
      }
      throw e
    }
  },

  async get<T>(path: string): Promise<T> {
    return (await request(path)).json() as Promise<T>
  },

  async postJson<T>(path: string, body: unknown): Promise<T> {
    const res = await request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return res.json() as Promise<T>
  },

  async postForm<T>(path: string, form: FormData): Promise<T> {
    const res = await request(path, { method: 'POST', body: form, timeoutMs: 120_000 })
    return res.json() as Promise<T>
  },

  async patchJson<T>(path: string, body: unknown): Promise<T> {
    const res = await request(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return res.json() as Promise<T>
  },

  async del(path: string, allowStatuses: number[] = [404]): Promise<void> {
    await this.raw(path, { method: 'DELETE' }, allowStatuses)
  },
}

/** WebSocket URL for the chat endpoint, honoring API_BASE when it's absolute. */
export function wsUrl(path: string): string {
  if (/^https?:\/\//.test(API_BASE)) {
    return API_BASE.replace(/^http/, 'ws') + path
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, ApiError, wsUrl } from './api'

function mockResponse(body: unknown, init: { status?: number } = {}): Response {
  const status = init.status ?? 200
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': typeof body === 'string' ? 'text/plain' : 'application/json' },
  })
}

describe('api client', () => {
  beforeEach(() => { vi.restoreAllMocks() })
  afterEach(() => { vi.restoreAllMocks() })

  it('get() returns parsed JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse({ hello: 'world' })))
    const data = await api.get<{ hello: string }>('/api/x')
    expect(data.hello).toBe('world')
  })

  it('throws ApiError with FastAPI detail on error status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse({ detail: 'boom' }, { status: 422 })))
    await expect(api.get('/api/x')).rejects.toMatchObject({ message: 'boom', status: 422 })
    await expect(api.get('/api/x')).rejects.toBeInstanceOf(ApiError)
  })

  it('del() swallows allowed statuses (404)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse('', { status: 404 })))
    await expect(api.del('/api/x')).resolves.toBeUndefined()
  })

  it('del() rethrows disallowed statuses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse({ detail: 'nope' }, { status: 500 })))
    await expect(api.del('/api/x')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('wsUrl', () => {
  it('builds a ws/wss url from window.location by default', () => {
    const url = wsUrl('/ws/chat/abc')
    expect(url).toMatch(/^wss?:\/\/.+\/ws\/chat\/abc$/)
  })
})

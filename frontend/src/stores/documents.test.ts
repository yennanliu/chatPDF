import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDocumentsStore } from './documents'
import { api } from '@/lib/api'

describe('documents store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('fetchDocuments populates state', async () => {
    vi.spyOn(api, 'get').mockResolvedValue([
      { doc_id: '1', name: 'a.pdf', page_count: 2, status: 'indexed', created_at: 'x' },
    ])
    const store = useDocumentsStore()
    await store.fetchDocuments()
    expect(store.documents).toHaveLength(1)
    expect(store.documents[0].name).toBe('a.pdf')
  })

  it('fetchDocuments records an error message on failure', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new Error('network down'))
    const store = useDocumentsStore()
    await store.fetchDocuments()
    expect(store.error).toBe('network down')
    expect(store.documents).toHaveLength(0)
  })

  it('deleteDocument removes the doc from state', async () => {
    vi.spyOn(api, 'get').mockResolvedValue([
      { doc_id: '1', name: 'a.pdf', page_count: 1, status: 'indexed', created_at: 'x' },
    ])
    vi.spyOn(api, 'del').mockResolvedValue(undefined)
    const store = useDocumentsStore()
    await store.fetchDocuments()
    await store.deleteDocument('1')
    expect(store.documents).toHaveLength(0)
  })
})

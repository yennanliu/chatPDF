import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Document {
  doc_id: string
  name: string
  page_count: number | null
  status: 'pending' | 'indexed' | 'error'
  created_at: string
}

export interface ChunkOptions {
  chunker: 'recursive' | 'sentence' | 'semantic'
  chunk_size: number
  chunk_overlap: number
}

export const useDocumentsStore = defineStore('documents', () => {
  const documents = ref<Document[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchDocuments(): Promise<void> {
    loading.value = true
    error.value = null
    console.info('[documents] fetch start')
    try {
      const res = await fetch('/api/documents')
      if (!res.ok) throw new Error(res.statusText)
      documents.value = await res.json()
      console.info('[documents] fetch ok:', documents.value.length, 'docs')
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      console.error('[documents] fetch failed:', error.value)
    } finally {
      loading.value = false
    }
  }

  const _cancelledPolls = new Set<string>()

  async function uploadDocument(file: File, opts?: ChunkOptions): Promise<Document | null> {
    error.value = null
    console.info('[documents] upload start:', file.name, `${file.size}B`, opts)
    try {
      const form = new FormData()
      form.append('file', file)
      if (opts) {
        form.append('chunker', opts.chunker)
        form.append('chunk_size', String(opts.chunk_size))
        form.append('chunk_overlap', String(opts.chunk_overlap))
      }
      const res = await fetch('/api/documents/upload', { method: 'POST', body: form })
      console.info('[documents] upload response:', res.status, res.statusText)
      if (!res.ok) throw new Error(await res.text())
      const doc: Document = await res.json()
      console.info('[documents] upload ok, doc_id=', doc.doc_id, '— polling status')
      documents.value.unshift(doc)
      _pollStatus(doc.doc_id)
      return doc
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      console.error('[documents] upload failed:', error.value)
      return null
    }
  }

  async function _pollStatus(doc_id: string): Promise<void> {
    _cancelledPolls.delete(doc_id)
    for (let i = 0; i < 60; i++) {
      if (_cancelledPolls.has(doc_id)) return
      const idx = documents.value.findIndex(d => d.doc_id === doc_id)
      if (idx === -1 || documents.value[idx].status !== 'pending') return
      await _sleep(1500)
      if (_cancelledPolls.has(doc_id)) return
      try {
        const res = await fetch(`/api/documents/${doc_id}/status`)
        if (!res.ok) return
        const { status, page_count } = await res.json()
        const i2 = documents.value.findIndex(d => d.doc_id === doc_id)
        if (i2 !== -1) {
          documents.value[i2].status = status
          documents.value[i2].page_count = page_count
        }
        if (status !== 'pending') {
          console.info('[documents] poll done:', doc_id, '→', status)
          return
        }
      } catch (e) {
        console.error('[documents] poll error:', doc_id, e)
        return
      }
    }
  }

  async function deleteDocument(doc_id: string): Promise<void> {
    error.value = null
    _cancelledPolls.add(doc_id)
    console.info('[documents] delete start:', doc_id)
    try {
      const res = await fetch(`/api/documents/${doc_id}`, { method: 'DELETE' })
      if (!res.ok && res.status !== 404) throw new Error(await res.text() || res.statusText)
      documents.value = documents.value.filter(d => d.doc_id !== doc_id)
      console.info('[documents] delete ok:', doc_id, res.status)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      console.error('[documents] delete failed:', error.value)
    }
  }

  async function deleteAllDocuments(): Promise<void> {
    error.value = null
    documents.value.forEach(d => _cancelledPolls.add(d.doc_id))  // stop in-flight polls
    console.info('[documents] delete-all start')
    try {
      const res = await fetch('/api/documents', { method: 'DELETE' })
      if (!res.ok && res.status !== 404) throw new Error(await res.text() || res.statusText)
      documents.value = []
      console.info('[documents] delete-all ok')
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      console.error('[documents] delete-all failed:', error.value)
    }
  }

  return { documents, loading, error, fetchDocuments, uploadDocument, deleteDocument, deleteAllDocuments }
})

function _sleep(ms: number) {
  return new Promise<void>(resolve => setTimeout(resolve, ms))
}

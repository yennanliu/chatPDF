import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Document {
  doc_id: string
  name: string
  page_count: number | null
  status: 'pending' | 'indexed' | 'error'
  created_at: string
}

export const useDocumentsStore = defineStore('documents', () => {
  const documents = ref<Document[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchDocuments(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/documents')
      if (!res.ok) throw new Error(res.statusText)
      documents.value = await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function uploadDocument(file: File): Promise<Document | null> {
    error.value = null
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/documents/upload', { method: 'POST', body: form })
      if (!res.ok) throw new Error(await res.text())
      const doc: Document = await res.json()
      // Insert at front; status starts as "pending"
      documents.value.unshift(doc)
      // Poll until indexing completes
      _pollStatus(doc.doc_id)
      return doc
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return null
    }
  }

  async function _pollStatus(doc_id: string): Promise<void> {
    for (let i = 0; i < 60; i++) {
      // Find the current status each iteration (array may shift)
      const doc = documents.value.find(d => d.doc_id === doc_id)
      if (!doc || doc.status !== 'pending') return
      await _sleep(1500)
      try {
        const res = await fetch(`/api/documents/${doc_id}/status`)
        if (!res.ok) return
        const { status, page_count } = await res.json()
        const idx = documents.value.findIndex(d => d.doc_id === doc_id)
        if (idx !== -1) {
          documents.value[idx].status = status
          documents.value[idx].page_count = page_count
        }
        if (status !== 'pending') return
      } catch {
        return
      }
    }
  }

  async function deleteDocument(doc_id: string): Promise<void> {
    error.value = null
    try {
      const res = await fetch(`/api/documents/${doc_id}`, { method: 'DELETE' })
      if (!res.ok && res.status !== 404) throw new Error(res.statusText)
      documents.value = documents.value.filter(d => d.doc_id !== doc_id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  return { documents, loading, error, fetchDocuments, uploadDocument, deleteDocument }
})

function _sleep(ms: number) {
  return new Promise<void>(resolve => setTimeout(resolve, ms))
}

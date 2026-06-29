import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import { useToast } from '@/composables/useToast'

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
  const toast = useToast()

  function _fail(e: unknown): void {
    error.value = e instanceof Error ? e.message : String(e)
    toast.error(error.value)
  }

  async function fetchDocuments(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      documents.value = await api.get<Document[]>('/api/documents')
    } catch (e) {
      _fail(e)
    } finally {
      loading.value = false
    }
  }

  const _cancelledPolls = new Set<string>()

  async function uploadDocument(file: File, opts?: ChunkOptions): Promise<Document | null> {
    error.value = null
    try {
      const form = new FormData()
      form.append('file', file)
      if (opts) {
        form.append('chunker', opts.chunker)
        form.append('chunk_size', String(opts.chunk_size))
        form.append('chunk_overlap', String(opts.chunk_overlap))
      }
      const doc = await api.postForm<Document>('/api/documents/upload', form)
      documents.value.unshift(doc)
      _pollStatus(doc.doc_id)
      return doc
    } catch (e) {
      _fail(e)
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
        const { status, page_count } =
          await api.get<{ status: Document['status']; page_count: number | null }>(
            `/api/documents/${doc_id}/status`,
          )
        const i2 = documents.value.findIndex(d => d.doc_id === doc_id)
        if (i2 !== -1) {
          documents.value[i2].status = status
          documents.value[i2].page_count = page_count
        }
        if (status !== 'pending') {
          if (status === 'indexed') toast.success(`Indexed ${documents.value[i2]?.name ?? doc_id}`)
          else if (status === 'error') toast.error(`Indexing failed for ${documents.value[i2]?.name ?? doc_id}`)
          return
        }
      } catch {
        return
      }
    }
  }

  async function deleteDocument(doc_id: string): Promise<void> {
    error.value = null
    _cancelledPolls.add(doc_id)
    try {
      await api.del(`/api/documents/${doc_id}`)
      documents.value = documents.value.filter(d => d.doc_id !== doc_id)
      toast.success('Document deleted')
    } catch (e) {
      _fail(e)
    }
  }

  async function deleteAllDocuments(): Promise<void> {
    error.value = null
    documents.value.forEach(d => _cancelledPolls.add(d.doc_id))  // stop in-flight polls
    try {
      await api.del('/api/documents')
      documents.value = []
    } catch (e) {
      _fail(e)
    }
  }

  return { documents, loading, error, fetchDocuments, uploadDocument, deleteDocument, deleteAllDocuments }
})

function _sleep(ms: number) {
  return new Promise<void>(resolve => setTimeout(resolve, ms))
}

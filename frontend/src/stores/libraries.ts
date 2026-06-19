import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface DocumentSnippet {
  doc_id: string
  name: string
  status: string
}

export interface Library {
  library_id: string
  name: string
  description: string | null
  rag_config: Record<string, unknown>
  documents: DocumentSnippet[]
  created_at: string
}

export const useLibrariesStore = defineStore('libraries', () => {
  const libraries = ref<Library[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchLibraries(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/libraries')
      if (!res.ok) throw new Error(res.statusText)
      libraries.value = await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function fetchLibrary(id: string): Promise<Library> {
    const res = await fetch(`/api/libraries/${id}`)
    if (!res.ok) throw new Error(res.statusText)
    const lib: Library = await res.json()
    const idx = libraries.value.findIndex(l => l.library_id === id)
    if (idx !== -1) libraries.value[idx] = lib
    else libraries.value.unshift(lib)
    return lib
  }

  async function createLibrary(name: string, description?: string): Promise<Library> {
    const res = await fetch('/api/libraries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description: description || null }),
    })
    if (!res.ok) throw new Error(res.statusText)
    const lib: Library = await res.json()
    libraries.value.unshift(lib)
    return lib
  }

  async function renameLibrary(id: string, name: string): Promise<void> {
    const res = await fetch(`/api/libraries/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) throw new Error(res.statusText)
    const updated: Library = await res.json()
    const idx = libraries.value.findIndex(l => l.library_id === id)
    if (idx !== -1) libraries.value[idx] = updated
  }

  async function updateRagConfig(id: string, rag_config: Record<string, unknown>): Promise<void> {
    const res = await fetch(`/api/libraries/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rag_config }),
    })
    if (!res.ok) throw new Error(res.statusText)
    const updated: Library = await res.json()
    const idx = libraries.value.findIndex(l => l.library_id === id)
    if (idx !== -1) libraries.value[idx] = updated
  }

  async function deleteLibrary(id: string): Promise<void> {
    const res = await fetch(`/api/libraries/${id}`, { method: 'DELETE' })
    if (!res.ok && res.status !== 404) throw new Error(res.statusText)
    libraries.value = libraries.value.filter(l => l.library_id !== id)
  }

  async function addDocument(library_id: string, doc_id: string): Promise<void> {
    const res = await fetch(`/api/libraries/${library_id}/documents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id }),
    })
    if (!res.ok) throw new Error(res.statusText)
    const updated: Library = await res.json()
    const idx = libraries.value.findIndex(l => l.library_id === library_id)
    if (idx !== -1) libraries.value[idx] = updated
  }

  async function removeDocument(library_id: string, doc_id: string): Promise<void> {
    const res = await fetch(`/api/libraries/${library_id}/documents/${doc_id}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error(res.statusText)
    const updated: Library = await res.json()
    const idx = libraries.value.findIndex(l => l.library_id === library_id)
    if (idx !== -1) libraries.value[idx] = updated
  }

  return {
    libraries, loading, error,
    fetchLibraries, fetchLibrary, createLibrary, renameLibrary, deleteLibrary,
    updateRagConfig, addDocument, removeDocument,
  }
})

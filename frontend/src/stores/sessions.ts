import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'

export interface MessageOut {
  role: 'user' | 'assistant'
  content: string
  sources: Array<{ doc_name: string; page?: number | null; chunk_preview: string; score: number }> | null
  created_at: string
}

export interface DocumentSnippet {
  doc_id: string
  name: string
  status: string
}

export interface Session {
  session_id: string
  title: string
  documents: DocumentSnippet[]
  rag_config: Record<string, unknown>
  provider: string
  model: string
  created_at: string
}

export interface SessionDetail extends Session {
  messages: MessageOut[]
}

export const useSessionsStore = defineStore('sessions', () => {
  const sessions = ref<Session[]>([])
  const activeSession = ref<SessionDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const models = ref<Record<string, string[]>>({})

  async function fetchModels(): Promise<void> {
    try {
      models.value = await api.get<Record<string, string[]>>('/api/models')
    } catch {
      // Non-fatal: the UI falls back to its built-in defaults.
    }
  }

  async function fetchSessions(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      sessions.value = await api.get<Session[]>('/api/sessions')
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function fetchSession(id: string): Promise<SessionDetail> {
    const detail = await api.get<SessionDetail>(`/api/sessions/${id}`)
    activeSession.value = detail
    return detail
  }

  async function createSession(payload: {
    doc_ids: string[]
    provider: string
    model: string
    title?: string
    rag_config?: Record<string, unknown>
  }): Promise<Session> {
    const sess = await api.postJson<Session>('/api/sessions', payload)
    sessions.value.unshift(sess)
    return sess
  }

  async function renameSession(id: string, title: string): Promise<void> {
    const updated = await api.patchJson<Session>(`/api/sessions/${id}`, { title })
    const idx = sessions.value.findIndex(s => s.session_id === id)
    if (idx !== -1) sessions.value[idx] = updated
    if (activeSession.value?.session_id === id) {
      activeSession.value.title = updated.title
    }
  }

  async function deleteSession(id: string): Promise<void> {
    await api.del(`/api/sessions/${id}`)
    sessions.value = sessions.value.filter(s => s.session_id !== id)
    if (activeSession.value?.session_id === id) activeSession.value = null
  }

  async function deleteAllSessions(): Promise<void> {
    await api.del('/api/sessions')
    sessions.value = []
    activeSession.value = null
  }

  return {
    sessions, activeSession, loading, error, models,
    fetchModels, fetchSessions, fetchSession, createSession, renameSession, deleteSession, deleteAllSessions,
  }
})

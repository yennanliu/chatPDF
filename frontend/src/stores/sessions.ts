import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface MessageOut {
  role: 'user' | 'assistant'
  content: string
  sources: Array<{ doc_name: string; chunk_preview: string; score: number }> | null
  created_at: string
}

export interface Session {
  session_id: string
  title: string
  library_id: string
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

  async function fetchSessions(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/sessions')
      if (!res.ok) throw new Error(res.statusText)
      sessions.value = await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function fetchSession(id: string): Promise<SessionDetail> {
    const res = await fetch(`/api/sessions/${id}`)
    if (!res.ok) throw new Error(res.statusText)
    const detail: SessionDetail = await res.json()
    activeSession.value = detail
    return detail
  }

  async function createSession(payload: {
    library_id: string
    provider: string
    model: string
    title?: string
  }): Promise<Session> {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(res.statusText)
    const sess: Session = await res.json()
    sessions.value.unshift(sess)
    return sess
  }

  async function renameSession(id: string, title: string): Promise<void> {
    const res = await fetch(`/api/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
    if (!res.ok) throw new Error(res.statusText)
    const updated: Session = await res.json()
    const idx = sessions.value.findIndex(s => s.session_id === id)
    if (idx !== -1) sessions.value[idx] = updated
    if (activeSession.value?.session_id === id) {
      activeSession.value.title = updated.title
    }
  }

  async function deleteSession(id: string): Promise<void> {
    const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
    if (!res.ok && res.status !== 404) throw new Error(res.statusText)
    sessions.value = sessions.value.filter(s => s.session_id !== id)
    if (activeSession.value?.session_id === id) activeSession.value = null
  }

  return {
    sessions, activeSession, loading, error,
    fetchSessions, fetchSession, createSession, renameSession, deleteSession,
  }
})

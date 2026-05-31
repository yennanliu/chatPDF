import { ref, watch, onUnmounted, type Ref } from 'vue'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Source {
  doc_name: string
  chunk_preview: string
  score: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Source[] | null
  isStreaming: boolean
}

export type WsState = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

// ── Composable ────────────────────────────────────────────────────────────────

export function useChatSocket(sessionId: Ref<string | null>) {
  const messages  = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const wsState   = ref<WsState>('idle')
  const wsError   = ref<string | null>(null)

  let ws: WebSocket | null = null
  let pendingQuery: string | null = null

  // ── Connection helpers ────────────────────────────────────────────────────

  function _wsUrl(sid: string): string {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/ws/chat/${sid}`
  }

  function _connect(sid: string) {
    _teardown()
    wsState.value = 'connecting'
    wsError.value = null

    ws = new WebSocket(_wsUrl(sid))

    ws.onopen = () => {
      wsState.value = 'open'
      if (pendingQuery !== null) {
        _dispatch(pendingQuery)
        pendingQuery = null
      }
    }

    ws.onmessage = (evt: MessageEvent<string>) => {
      const frame = JSON.parse(evt.data) as {
        type: 'token' | 'done' | 'error'
        data?: string
        sources?: Source[]
        detail?: string
      }

      if (frame.type === 'token') {
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant' && last.isStreaming) {
          last.content += frame.data ?? ''
        }
      } else if (frame.type === 'done') {
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant') {
          last.isStreaming = false
          last.sources = frame.sources ?? null
        }
        isStreaming.value = false
      } else if (frame.type === 'error') {
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant' && last.isStreaming) {
          last.isStreaming = false
          last.content = last.content || `⚠ ${frame.detail ?? 'Unknown error'}`
        }
        wsError.value = frame.detail ?? 'Unknown error'
        isStreaming.value = false
      }
    }

    ws.onerror = () => {
      wsState.value = 'error'
      wsError.value = 'WebSocket connection failed'
      isStreaming.value = false
    }

    ws.onclose = (evt: CloseEvent) => {
      wsState.value = evt.wasClean ? 'closed' : 'error'
      isStreaming.value = false
    }
  }

  function _teardown() {
    if (ws) {
      ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
      ws = null
    }
    wsState.value = 'idle'
    isStreaming.value = false
  }

  // ── Dispatch a query frame ────────────────────────────────────────────────

  function _dispatch(query: string) {
    const uid = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`
    messages.value.push({ id: `${uid}_u`, role: 'user',      content: query, sources: null, isStreaming: false })
    messages.value.push({ id: `${uid}_a`, role: 'assistant', content: '',    sources: null, isStreaming: true  })
    isStreaming.value = true
    wsError.value = null
    ws!.send(JSON.stringify({ query }))
  }

  // ── Public API ────────────────────────────────────────────────────────────

  function send(query: string) {
    const sid = sessionId.value
    if (!sid || isStreaming.value) return

    if (ws?.readyState === WebSocket.OPEN) {
      _dispatch(query)
    } else {
      // Queue and connect; _dispatch fires in onopen
      pendingQuery = query
      _connect(sid)
    }
  }

  function loadHistory(history: Array<{ role: string; content: string; sources: Source[] | null }>) {
    messages.value = history.map((m, i) => ({
      id: `hist_${i}`,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      sources: m.sources ?? null,
      isStreaming: false,
    }))
  }

  function clearMessages() {
    messages.value = []
  }

  // Reconnect whenever the sessionId changes
  watch(sessionId, (sid) => {
    messages.value = []
    pendingQuery = null
    if (sid) _connect(sid)
    else _teardown()
  })

  onUnmounted(_teardown)

  function reconnect() {
    const sid = sessionId.value
    if (sid) _connect(sid)
  }

  return { messages, isStreaming, wsState, wsError, send, loadHistory, clearMessages, reconnect }
}

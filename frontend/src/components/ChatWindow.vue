<script setup lang="ts">
import { ref, watch, nextTick, computed, toRef } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatSocket }    from '@/composables/useChatSocket'
import MessageBubble        from './MessageBubble.vue'

const props = defineProps<{ sessionId: string }>()

const sessionsStore = useSessionsStore()
const sidRef        = toRef(props, 'sessionId')

const { messages, isStreaming, wsState, wsError, send, loadHistory, reconnect } = useChatSocket(sidRef)

const query     = ref('')
const listEl    = ref<HTMLElement | null>(null)
const inputEl   = ref<HTMLTextAreaElement | null>(null)
const loading   = ref(false)

const currentSession = computed(() =>
  sessionsStore.sessions.find(s => s.session_id === props.sessionId),
)

// Load history whenever the session changes
watch(
  () => props.sessionId,
  async (sid) => {
    if (!sid) return
    loading.value = true
    try {
      const detail = await sessionsStore.fetchSession(sid)
      loadHistory(
        detail.messages.map(m => ({
          role: m.role,
          content: m.content,
          sources: m.sources ?? null,
        })),
      )
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

// Auto-scroll to bottom whenever messages change or new token arrives
watch(messages, () => nextTick(scrollBottom), { deep: true })

function scrollBottom() {
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function handleSend() {
  const q = query.value.trim()
  if (!q || isStreaming.value) return
  send(q)
  query.value = ''
  nextTick(() => inputEl.value?.focus())
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const statusLabel = computed(() => {
  if (wsState.value === 'connecting') return 'connecting…'
  if (wsState.value === 'error')      return 'disconnected'
  if (isStreaming.value)              return 'responding…'
  return ''
})

// Show the reconnect banner when the connection is unexpectedly lost
// (not 'idle' which is the initial/unmounted state)
const showReconnectBanner = computed(() =>
  wsState.value === 'error' || (wsState.value === 'closed' && messages.value.length > 0),
)
</script>

<template>
  <div class="chat-window">
    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <div class="chat-header">
      <div class="header-left">
        <span class="chat-title">{{ currentSession?.title ?? 'Chat' }}</span>
        <span v-if="statusLabel" class="status-label">
          <span v-if="wsState === 'connecting' || isStreaming" class="spinner" style="width:10px;height:10px" />
          {{ statusLabel }}
        </span>
        <span v-if="wsState === 'error'" class="status-error">⚠ {{ wsError }}</span>
      </div>
      <div class="header-meta">
        <span v-if="currentSession" class="meta-chip">
          {{ currentSession.provider }} · {{ currentSession.model }}
        </span>
      </div>
    </div>

    <!-- ── WS error / reconnect banner ───────────────────────────────────── -->
    <div v-if="showReconnectBanner" class="reconnect-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span>Connection lost{{ wsError ? `: ${wsError}` : '' }}</span>
      <button class="btn btn-sm btn-primary" @click="reconnect">Reconnect</button>
    </div>

    <!-- ── Message list ────────────────────────────────────────────────────── -->
    <div ref="listEl" class="message-list">
      <div v-if="loading" class="center-hint">
        <span class="spinner" /> Loading history…
      </div>
      <div v-else-if="!messages.length" class="center-hint">
        <div class="empty-chat-icon">💬</div>
        <p>Send a message to start the conversation.</p>
      </div>
      <template v-else>
        <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />
      </template>
    </div>

    <!-- ── Input ──────────────────────────────────────────────────────────── -->
    <div class="input-area">
      <div class="input-row">
        <textarea
          ref="inputEl"
          v-model="query"
          class="query-input"
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          rows="1"
          :disabled="isStreaming"
          @keydown="onKeydown"
        />
        <button
          class="btn btn-primary send-btn"
          :disabled="!query.trim() || isStreaming"
          @click="handleSend"
        >
          <span v-if="isStreaming" class="spinner" style="width:14px;height:14px" />
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
      <p class="input-hint">Enter to send · Shift+Enter for newline</p>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* ── Reconnect banner ───────────────────────────────────────────────────────── */
.reconnect-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  background: #fef3c7; border-bottom: 1px solid #fcd34d;
  font-size: 0.82rem; color: #92400e;
  flex-shrink: 0;
}
.reconnect-banner span { flex: 1; }

/* ── Header ─────────────────────────────────────────────────────────────────── */
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  flex-shrink: 0;
}
.header-left {
  display: flex; align-items: center; gap: 10px;
}
.chat-title {
  font-size: 0.95rem; font-weight: 600;
}
.status-label {
  display: flex; align-items: center; gap: 5px;
  font-size: 0.78rem; color: var(--txt-muted);
}
.status-error { font-size: 0.78rem; color: var(--clr-danger); }
.meta-chip {
  font-size: 0.75rem; color: var(--txt-muted);
  background: var(--bg-page); border: 1px solid var(--border);
  padding: 2px 8px; border-radius: 99px;
}

/* ── Message list ───────────────────────────────────────────────────────────── */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.center-hint {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 10px; color: var(--txt-muted); font-size: 0.875rem;
  padding: 40px 0;
}
.empty-chat-icon { font-size: 2.5rem; }

/* ── Input area ─────────────────────────────────────────────────────────────── */
.input-area {
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
  flex-shrink: 0;
}
.input-row {
  display: flex; gap: 10px; align-items: flex-end;
}
.query-input {
  flex: 1;
  min-height: 40px; max-height: 120px;
  padding: 9px 12px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  font-size: 0.875rem; font-family: inherit;
  color: var(--txt-base); background: var(--bg-page);
  resize: none; overflow-y: auto;
  line-height: 1.5;
  transition: border-color .15s;
}
.query-input:focus { outline: none; border-color: var(--clr-primary); }
.query-input:disabled { opacity: 0.6; }
.send-btn {
  height: 40px; width: 44px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  padding: 0;
}
.input-hint {
  font-size: 0.72rem; color: var(--txt-muted);
  margin-top: 5px;
}
</style>

<script setup lang="ts">
import { ref, watch, nextTick, computed, toRef } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatSocket }    from '@/composables/useChatSocket'
import MessageBubble        from './MessageBubble.vue'

const props = defineProps<{ sessionId: string }>()

const sessionsStore = useSessionsStore()
const sidRef        = toRef(props, 'sessionId')

const { messages, isStreaming, wsState, wsError, send, loadHistory, reconnect } = useChatSocket(sidRef)

const query   = ref('')
const listEl  = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
const loading = ref(false)

const currentSession = computed(() => sessionsStore.activeSession)

watch(
  () => props.sessionId,
  async (sid) => {
    if (!sid) return
    loading.value = true
    try {
      const detail = await sessionsStore.fetchSession(sid)
      loadHistory(
        detail.messages.map(m => ({
          role:    m.role,
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

watch(() => messages.value.length, () => nextTick(scrollBottom))

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

const showReconnectBanner = computed(() =>
  wsState.value === 'error' || (wsState.value === 'closed' && messages.value.length > 0),
)

function exportConversation() {
  const title = currentSession.value?.title ?? 'chat'
  const lines = [`# ${title}`, '']
  for (const m of messages.value) {
    lines.push(m.role === 'user' ? `## 🧑 You` : `## 🤖 Assistant`)
    lines.push('', m.content, '')
    if (m.sources?.length) {
      lines.push('**Sources:**')
      for (const s of m.sources) {
        const page = s.page != null ? ` (p.${s.page})` : ''
        lines.push(`- ${s.doc_name}${page} — ${(s.score * 100).toFixed(0)}%`)
      }
      lines.push('')
    }
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.replace(/[^\w-]+/g, '_')}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="chat-window">
    <!-- Header -->
    <div class="chat-header">
      <div class="header-left">
        <div class="header-avatar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div class="header-info">
          <span class="chat-title">{{ currentSession?.title ?? 'Chat' }}</span>
          <span v-if="statusLabel" class="status-label">
            <span v-if="wsState === 'connecting' || isStreaming" class="spinner" style="width:9px;height:9px" />
            {{ statusLabel }}
          </span>
        </div>
      </div>
      <div class="header-meta">
        <span v-if="currentSession" class="meta-chip">
          {{ currentSession.provider }} · {{ currentSession.model }}
        </span>
        <button
          v-if="messages.length"
          class="btn btn-icon btn-ghost btn-sm"
          title="Export conversation as Markdown"
          aria-label="Export conversation as Markdown"
          @click="exportConversation"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
        </button>
        <span v-if="wsState === 'error'" class="status-error">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          {{ wsError }}
        </span>
      </div>
    </div>

    <!-- Reconnect banner -->
    <div v-if="showReconnectBanner" class="reconnect-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <span>Connection lost{{ wsError ? `: ${wsError}` : '' }}</span>
      <button class="btn btn-sm btn-primary" @click="reconnect">Reconnect</button>
    </div>

    <!-- Message list -->
    <div ref="listEl" class="message-list">
      <div v-if="loading" class="center-hint">
        <span class="spinner" /> Loading history…
      </div>
      <div v-else-if="!messages.length" class="center-hint">
        <div class="empty-chat-art">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <p>Send a message to start the conversation.</p>
      </div>
      <template v-else>
        <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />
      </template>
    </div>

    <!-- Input -->
    <div class="input-area">
      <div class="input-row">
        <textarea
          ref="inputEl"
          v-model="query"
          class="query-input"
          placeholder="Ask anything about your documents…"
          rows="1"
          :disabled="isStreaming"
          @keydown="onKeydown"
        />
        <button
          class="send-btn"
          :class="{ streaming: isStreaming }"
          :disabled="!query.trim() || isStreaming"
          aria-label="Send message"
          @click="handleSend"
        >
          <span v-if="isStreaming" class="spinner" style="width:15px;height:15px" />
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
      <p class="input-hint">Enter to send · Shift+Enter for newline</p>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  display: flex; flex-direction: column;
  height: 100%; min-height: 0;
}

/* ── Header ──────────────────────────────────────────────────────────────────── */
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg); flex-shrink: 0;
}
.header-left { display: flex; align-items: center; gap: 10px; }

.header-avatar {
  width: 32px; height: 32px; border-radius: 9px; flex-shrink: 0;
  background: rgba(162,89,255,.12); color: var(--brand-purple);
  display: flex; align-items: center; justify-content: center;
}

.header-info { display: flex; align-items: baseline; gap: 8px; }
.chat-title { font-size: .95rem; font-weight: 600; }
.status-label {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: .75rem; color: var(--text-muted);
}

.header-meta { display: flex; align-items: center; gap: 8px; }
.meta-chip {
  font-size: .72rem; color: var(--text-muted);
  background: var(--bg-alt); border: 1px solid var(--border);
  padding: 3px 10px; border-radius: var(--radius-pill);
}
.status-error {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: .75rem; color: var(--clr-danger);
}

/* ── Reconnect banner ────────────────────────────────────────────────────────── */
.reconnect-banner {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 18px;
  background: rgba(245,158,11,.1); border-bottom: 1px solid rgba(245,158,11,.2);
  font-size: .82rem; color: #92400e; flex-shrink: 0;
}
.reconnect-banner span { flex: 1; }

/* ── Messages ────────────────────────────────────────────────────────────────── */
.message-list {
  flex: 1; overflow-y: auto;
  padding: 20px;
  display: flex; flex-direction: column; gap: 4px;
  background: var(--bg-alt);
}

.center-hint {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; color: var(--text-muted); font-size: .875rem;
  padding: 48px 0; text-align: center;
}
.empty-chat-art {
  width: 56px; height: 56px; border-radius: 16px;
  background: rgba(162,89,255,.1); color: var(--brand-purple); opacity: .7;
  display: flex; align-items: center; justify-content: center;
}

/* ── Input area ──────────────────────────────────────────────────────────────── */
.input-area {
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg); flex-shrink: 0;
}
.input-row { display: flex; gap: 10px; align-items: flex-end; }

.query-input {
  flex: 1;
  min-height: 44px; max-height: 120px;
  padding: 11px 14px;
  border: 1.5px solid var(--border); border-radius: var(--radius-sm);
  font-size: .875rem; font-family: inherit;
  color: var(--text); background: var(--bg-alt);
  resize: none; overflow-y: auto; line-height: 1.5;
  transition: border-color .15s, box-shadow .15s;
}
.query-input:focus {
  outline: none;
  border-color: var(--brand-purple);
  box-shadow: 0 0 0 3px rgba(162,89,255,.1);
}
.query-input:disabled { opacity: .5; }

.send-btn {
  width: 44px; height: 44px; flex-shrink: 0;
  border: none; border-radius: var(--radius-sm); cursor: pointer;
  background: var(--brand-purple); color: #fff;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, box-shadow .15s;
}
.send-btn:not(:disabled):hover { background: #9146f0; box-shadow: 0 4px 12px rgba(162,89,255,.3); }
.send-btn:disabled { opacity: .4; cursor: default; }
.send-btn.streaming { background: var(--text-muted); }

.input-hint { font-size: .71rem; color: var(--text-muted); margin-top: 6px; }
</style>

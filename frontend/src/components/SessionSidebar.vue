<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'

defineProps<{ activeSessionId: string | null }>()

const emit = defineEmits<{
  select:     [sessionId: string]
  newSession: []
}>()

const store     = useSessionsStore()
const editingId = ref<string | null>(null)
const editTitle = ref('')

onMounted(() => store.fetchSessions())

function formatDate(iso: string) {
  const d   = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function startEdit(id: string, title: string) {
  editingId.value = id
  editTitle.value = title
}

async function saveEdit(id: string) {
  if (!editTitle.value.trim()) return
  await store.renameSession(id, editTitle.value.trim())
  editingId.value = null
}

async function remove(id: string) {
  if (!confirm('Delete this session and all its messages?')) return
  await store.deleteSession(id)
}
</script>

<template>
  <aside class="session-sidebar">
    <div class="sidebar-toolbar">
      <span class="sidebar-label">Sessions</span>
      <button class="btn btn-sm btn-primary" @click="emit('newSession')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        New
      </button>
    </div>

    <div v-if="store.loading" class="sidebar-hint">
      <span class="spinner" /> Loading…
    </div>

    <div v-else-if="!store.sessions.length" class="sidebar-empty">
      <div class="sidebar-empty-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <p>No sessions yet.<br/>Hit <strong>New</strong> to start.</p>
    </div>

    <ul v-else class="session-list">
      <li
        v-for="sess in store.sessions"
        :key="sess.session_id"
        class="session-item"
        :class="{ active: sess.session_id === activeSessionId }"
        @click="emit('select', sess.session_id)"
      >
        <template v-if="editingId === sess.session_id">
          <input
            v-model="editTitle"
            class="edit-input"
            autofocus
            @keyup.enter="saveEdit(sess.session_id)"
            @keyup.esc="editingId = null"
            @click.stop
          />
          <button class="btn btn-xs btn-primary" @click.stop="saveEdit(sess.session_id)">✓</button>
          <button class="btn btn-xs btn-ghost"   @click.stop="editingId = null">✕</button>
        </template>
        <template v-else>
          <div class="session-avatar" :class="{ 'active-avatar': sess.session_id === activeSessionId }">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="session-info">
            <span class="session-title">{{ sess.title }}</span>
            <span class="session-meta">{{ formatDate(sess.created_at) }}</span>
          </div>
          <div class="session-actions" @click.stop>
            <button class="btn btn-icon btn-ghost btn-sm" title="Rename" @click="startEdit(sess.session_id, sess.title)">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="btn btn-icon btn-ghost btn-sm" title="Delete" style="color:var(--clr-danger)" @click="remove(sess.session_id)">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14H6L5 6"/>
              </svg>
            </button>
          </div>
        </template>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.session-sidebar {
  width: 232px; flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg);
  display: flex; flex-direction: column; overflow: hidden;
}

.sidebar-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.sidebar-label {
  font-size: .72rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .07em;
  color: var(--text-muted);
}

.sidebar-hint {
  display: flex; align-items: center; gap: 8px;
  padding: 14px; font-size: .84rem; color: var(--text-muted);
}

.sidebar-empty {
  padding: 28px 16px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.sidebar-empty-icon {
  width: 44px; height: 44px; border-radius: 12px;
  background: rgba(162,89,255,.1); color: var(--brand-purple); opacity: .7;
  display: flex; align-items: center; justify-content: center;
}
.sidebar-empty p { font-size: .84rem; color: var(--text-muted); line-height: 1.55; }

.session-list { list-style: none; overflow-y: auto; flex: 1; }

.session-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: background .12s; position: relative;
}
.session-item:hover  { background: var(--bg-alt); }
.session-item.active { background: rgba(162,89,255,.07); }

.session-avatar {
  width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
  background: rgba(162,89,255,.08); color: var(--text-muted);
  display: flex; align-items: center; justify-content: center;
  transition: background .12s, color .12s;
}
.active-avatar { background: rgba(162,89,255,.2); color: var(--brand-purple); }

.session-info { flex: 1; min-width: 0; }
.session-title {
  display: block; font-size: .84rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.session-item.active .session-title { color: var(--brand-purple); font-weight: 600; }
.session-meta { font-size: .72rem; color: var(--text-muted); }

.session-actions {
  display: flex; gap: 1px; opacity: 0; transition: opacity .15s; flex-shrink: 0;
}
.session-item:hover .session-actions,
.session-item.active .session-actions { opacity: 1; }

.edit-input {
  flex: 1; height: 28px; padding: 0 8px;
  border: 1.5px solid var(--brand-purple); border-radius: var(--radius-sm);
  font-size: .84rem; font-family: inherit;
  box-shadow: 0 0 0 3px rgba(162,89,255,.1);
}
.edit-input:focus { outline: none; }
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'

const props = defineProps<{
  activeSessionId: string | null
}>()

const emit = defineEmits<{
  select: [sessionId: string]
  newSession: []
}>()

const store = useSessionsStore()
const editingId = ref<string | null>(null)
const editTitle = ref('')

onMounted(() => store.fetchSessions())

function formatDate(iso: string) {
  const d = new Date(iso)
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
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        New
      </button>
    </div>

    <div v-if="store.loading" class="sidebar-hint">
      <span class="spinner" /> Loading…
    </div>

    <div v-else-if="!store.sessions.length" class="sidebar-hint">
      No sessions yet.<br>Click <strong>New</strong> to start.
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
            @keyup.enter="saveEdit(sess.session_id)"
            @keyup.esc="editingId = null"
            @click.stop
            autofocus
          />
          <button class="btn btn-sm btn-primary" @click.stop="saveEdit(sess.session_id)">✓</button>
          <button class="btn btn-sm btn-ghost" @click.stop="editingId = null">✕</button>
        </template>
        <template v-else>
          <div class="session-info">
            <span class="session-title">{{ sess.title }}</span>
            <span class="session-meta">{{ formatDate(sess.created_at) }}</span>
          </div>
          <div class="session-actions" @click.stop>
            <button
              class="btn btn-icon btn-ghost btn-sm"
              title="Rename"
              @click="startEdit(sess.session_id, sess.title)"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button
              class="btn btn-icon btn-ghost btn-sm"
              title="Delete"
              style="color:var(--clr-danger)"
              @click="remove(sess.session_id)"
            >
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
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-page);
}
.sidebar-label {
  font-size: 0.78rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .06em;
  color: var(--txt-muted);
}

.sidebar-hint {
  padding: 16px 14px;
  font-size: 0.82rem; color: var(--txt-muted); line-height: 1.6;
}

.session-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
}

.session-item {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: background .1s;
  position: relative;
}
.session-item:hover  { background: var(--bg-page); }
.session-item.active { background: #eff6ff; }

.session-info { flex: 1; min-width: 0; }
.session-title {
  display: block;
  font-size: 0.85rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.session-meta { font-size: 0.72rem; color: var(--txt-muted); }

.session-actions {
  display: flex; gap: 1px;
  opacity: 0; transition: opacity .15s;
  flex-shrink: 0;
}
.session-item:hover .session-actions,
.session-item.active .session-actions { opacity: 1; }

.edit-input {
  flex: 1; height: 26px; padding: 0 8px;
  border: 1px solid var(--clr-primary); border-radius: var(--radius-sm);
  font-size: 0.85rem;
}
</style>

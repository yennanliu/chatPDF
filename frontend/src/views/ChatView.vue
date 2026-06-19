<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useLibrariesStore } from '@/stores/libraries'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatWindow     from '@/components/ChatWindow.vue'

const sessStore     = useSessionsStore()
const libStore      = useLibrariesStore()

const activeSessionId   = ref<string | null>(null)
const showModal         = ref(false)
const sessionDrawerOpen = ref(false)

const form = ref({
  library_id: '',
  provider:   'openai' as 'openai' | 'google' | 'anthropic',
  model:      'gpt-4o',
  title:      '',
})
const creating    = ref(false)
const createError = ref<string | null>(null)

const MODELS: Record<string, string[]> = {
  openai:    ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  google:    ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
  anthropic: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
}

const PROVIDER_META: Record<string, { label: string; color: string; bg: string }> = {
  openai:    { label: 'OpenAI',    color: '#10a37f', bg: 'rgba(16,163,127,.1)' },
  google:    { label: 'Google',    color: '#1abcfe', bg: 'rgba(26,188,254,.1)' },
  anthropic: { label: 'Anthropic', color: '#a259ff', bg: 'rgba(162,89,255,.1)' },
}

function openModal() {
  createError.value = null
  form.value = { library_id: libStore.libraries[0]?.library_id ?? '', provider: 'openai', model: 'gpt-4o', title: '' }
  showModal.value = true
}

async function createSession() {
  if (!form.value.library_id) { createError.value = 'Choose a library first'; return }
  creating.value = true
  createError.value = null
  try {
    const sess = await sessStore.createSession({
      library_id: form.value.library_id,
      provider:   form.value.provider,
      model:      form.value.model,
      title:      form.value.title.trim() || undefined,
    })
    showModal.value        = false
    sessionDrawerOpen.value = false
    activeSessionId.value  = sess.session_id
  } catch (e) {
    createError.value = e instanceof Error ? e.message : String(e)
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await Promise.all([sessStore.fetchSessions(), libStore.fetchLibraries()])
  if (!activeSessionId.value && sessStore.sessions.length) {
    activeSessionId.value = sessStore.sessions[0].session_id
  }
})
</script>

<template>
  <div class="chat-layout">
    <!-- Mobile drawer backdrop -->
    <div v-if="sessionDrawerOpen" class="drawer-backdrop" @click="sessionDrawerOpen = false" />

    <!-- Session sidebar -->
    <div class="session-panel" :class="{ 'drawer-open': sessionDrawerOpen }">
      <SessionSidebar
        :active-session-id="activeSessionId"
        @select="(id) => { activeSessionId = id; sessionDrawerOpen = false }"
        @new-session="openModal"
      />
    </div>

    <!-- Chat area -->
    <div class="chat-area">
      <button class="mobile-sessions-btn btn btn-ghost btn-sm" @click="sessionDrawerOpen = true">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
        Sessions
      </button>

      <ChatWindow v-if="activeSessionId" :session-id="activeSessionId" />

      <div v-else class="no-session">
        <div class="no-session-art">
          <div class="art-circle art-c1" />
          <div class="art-circle art-c2" />
          <div class="art-circle art-c3" />
          <svg class="art-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <h2>Start a conversation</h2>
        <p>Select a session from the sidebar, or create a new one to get started.</p>
        <button class="btn btn-primary" @click="openModal">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Chat
        </button>
        <p v-if="!libStore.libraries.length" class="hint-warn">
          No libraries yet — <RouterLink to="/libraries">create one first</RouterLink>.
        </p>
      </div>
    </div>

    <!-- Create session modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-backdrop" @click.self="showModal = false">
        <div class="modal" role="dialog" aria-modal="true">
          <div class="modal-header">
            <div class="modal-title-wrap">
              <div class="modal-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <h2>New Chat Session</h2>
            </div>
            <button class="btn btn-icon btn-ghost" @click="showModal = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- Library -->
            <div class="field">
              <label class="field-label">Library <span class="required">*</span></label>
              <select v-model="form.library_id" class="input">
                <option value="" disabled>Choose a library…</option>
                <option v-for="lib in libStore.libraries" :key="lib.library_id" :value="lib.library_id">
                  {{ lib.name }} ({{ lib.documents.length }} docs)
                </option>
              </select>
              <p v-if="!libStore.libraries.length" class="field-hint warn">
                No libraries yet. <RouterLink to="/libraries">Create one first.</RouterLink>
              </p>
            </div>

            <!-- Provider -->
            <div class="field">
              <label class="field-label">Provider</label>
              <div class="provider-grid">
                <button
                  v-for="p in ['openai', 'google', 'anthropic']"
                  :key="p"
                  class="provider-btn"
                  :class="{ active: form.provider === p }"
                  :style="form.provider === p ? { background: PROVIDER_META[p].bg, color: PROVIDER_META[p].color, borderColor: PROVIDER_META[p].color } : {}"
                  @click="form.provider = p as typeof form.provider; form.model = MODELS[p][0]"
                >
                  {{ PROVIDER_META[p].label }}
                </button>
              </div>
            </div>

            <!-- Model -->
            <div class="field">
              <label class="field-label">Model</label>
              <select v-model="form.model" class="input">
                <option v-for="m in MODELS[form.provider]" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>

            <!-- Title -->
            <div class="field">
              <label class="field-label">Session title <span class="optional">(optional)</span></label>
              <input v-model="form.title" class="input" placeholder="New Chat" />
            </div>

            <div v-if="createError" class="error-msg">{{ createError }}</div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-ghost" @click="showModal = false">Cancel</button>
            <button class="btn btn-primary" :disabled="creating || !form.library_id" @click="createSession">
              <span v-if="creating" class="spinner" />
              Start chatting
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────────── */
.chat-layout { display: flex; height: 100vh; overflow: hidden; }
.session-panel { display: flex; flex-shrink: 0; }
.chat-area {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column;
  background: var(--bg-alt); position: relative;
}
.mobile-sessions-btn { display: none; }

/* ── Mobile ──────────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .chat-layout { height: calc(100vh - 54px); }
  .session-panel {
    position: fixed; top: 54px; left: 0; bottom: 0; z-index: 55;
    transform: translateX(-100%); transition: transform .25s ease;
  }
  .session-panel.drawer-open { transform: translateX(0); }
  .drawer-backdrop {
    position: fixed; inset: 0; top: 54px; z-index: 50;
    background: rgba(15,15,20,.35); backdrop-filter: blur(2px);
  }
  .mobile-sessions-btn {
    display: flex; position: absolute; top: 10px; left: 10px; z-index: 10;
    gap: 6px; background: var(--bg); border: 1.5px solid var(--border);
    box-shadow: var(--shadow-sm);
  }
}

/* ── No session empty state ──────────────────────────────────────────────────── */
.no-session {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 14px; padding: 40px; color: var(--text-muted);
}
.no-session h2 { color: var(--text); }

/* Illustration */
.no-session-art {
  position: relative; width: 88px; height: 88px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 4px;
}
.art-circle {
  position: absolute; border-radius: 50%; opacity: .18;
}
.art-c1 { width: 88px; height: 88px; background: var(--brand-purple); }
.art-c2 { width: 60px; height: 60px; background: var(--brand-blue); }
.art-c3 { width: 36px; height: 36px; background: var(--brand-red); }
.art-icon { position: relative; color: var(--brand-purple); opacity: .8; }

.hint-warn { font-size: .85rem; }
.hint-warn a { color: var(--brand-purple); font-weight: 500; }

/* ── Modal ───────────────────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(15,15,20,.45);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
}
.modal {
  background: var(--bg);
  border-radius: var(--radius-lg);
  width: 100%; max-width: 460px;
  box-shadow: var(--shadow-drop);
  display: flex; flex-direction: column;
  border: 1px solid var(--border);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 22px 16px;
  border-bottom: 1px solid var(--border);
}
.modal-title-wrap { display: flex; align-items: center; gap: 12px; }
.modal-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: rgba(162,89,255,.1); color: var(--brand-purple);
  display: flex; align-items: center; justify-content: center;
}
.modal-body   { padding: 22px; display: flex; flex-direction: column; gap: 18px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 16px 22px;
  border-top: 1px solid var(--border);
}

/* ── Form ────────────────────────────────────────────────────────────────────── */
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: .8rem; font-weight: 600; color: var(--text-muted); }
.required { color: var(--clr-danger); }
.optional  { color: var(--text-muted); font-weight: 400; }
.field-hint { font-size: .8rem; color: var(--text-muted); }
.field-hint.warn { color: var(--clr-warn); }
.field-hint a { color: var(--brand-purple); font-weight: 500; }

.provider-grid { display: flex; gap: 8px; }
.provider-btn {
  flex: 1; padding: 9px 10px;
  border: 1.5px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-alt); cursor: pointer;
  font-size: .84rem; font-weight: 500; color: var(--text-muted);
  transition: all .15s; font-family: inherit;
}
.provider-btn:hover { border-color: #c8c8d0; color: var(--text); background: var(--bg); }

.error-msg {
  padding: 10px 14px;
  background: rgba(242,78,30,.08); color: #b93200;
  border-radius: var(--radius-sm); font-size: .84rem;
}
</style>

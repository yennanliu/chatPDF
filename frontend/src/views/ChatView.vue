<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionsStore } from '@/stores/sessions'
import { useLibrariesStore } from '@/stores/libraries'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatWindow     from '@/components/ChatWindow.vue'

const router        = useRouter()
const sessStore     = useSessionsStore()
const libStore      = useLibrariesStore()

const activeSessionId  = ref<string | null>(null)
const showModal        = ref(false)
const sessionDrawerOpen = ref(false)  // mobile session panel toggle

// ── Create-session modal state ────────────────────────────────────────────────
const form = ref({
  library_id: '',
  provider:   'openai' as 'openai' | 'google' | 'anthropic',
  model:      'gpt-4o',
  title:      '',
})
const creating = ref(false)
const createError = ref<string | null>(null)

const MODELS: Record<string, string[]> = {
  openai:    ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  google:    ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  anthropic: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
}

function onProviderChange() {
  form.value.model = MODELS[form.value.provider][0]
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
      library_id:  form.value.library_id,
      provider:    form.value.provider,
      model:       form.value.model,
      title:      form.value.title.trim() || undefined,
    })
    showModal.value = false
    sessionDrawerOpen.value = false
    activeSessionId.value = sess.session_id
  } catch (e) {
    createError.value = e instanceof Error ? e.message : String(e)
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    sessStore.fetchSessions(),
    libStore.fetchLibraries(),
  ])
  // Auto-select most recent session if any
  if (!activeSessionId.value && sessStore.sessions.length) {
    activeSessionId.value = sessStore.sessions[0].session_id
  }
})
</script>

<template>
  <div class="chat-layout">
    <!-- ── Mobile drawer backdrop ────────────────────────────────────────── -->
    <div
      v-if="sessionDrawerOpen"
      class="drawer-backdrop"
      @click="sessionDrawerOpen = false"
    />

    <!-- ── Session sidebar ─────────────────────────────────────────────────── -->
    <div class="session-panel" :class="{ 'drawer-open': sessionDrawerOpen }">
      <SessionSidebar
        :active-session-id="activeSessionId"
        @select="(id) => { activeSessionId = id; sessionDrawerOpen = false }"
        @new-session="openModal"
      />
    </div>

    <!-- ── Chat window or placeholder ────────────────────────────────────── -->
    <div class="chat-area">
      <!-- Mobile sessions toggle button -->
      <button
        class="mobile-sessions-btn btn btn-ghost btn-sm"
        @click="sessionDrawerOpen = true"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
        Sessions
      </button>

      <ChatWindow v-if="activeSessionId" :session-id="activeSessionId" />
      <div v-else class="no-session">
        <div class="no-session-icon">💬</div>
        <h2>Start a conversation</h2>
        <p>Select a session from the sidebar, or create a new one.</p>
        <button class="btn btn-primary" @click="openModal">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Chat
        </button>
        <p v-if="!libStore.libraries.length" class="hint-warn">
          ⚠ No libraries yet.
          <RouterLink to="/libraries">Create one first</RouterLink>.
        </p>
      </div>
    </div>

    <!-- ── Create session modal ───────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-backdrop" @click.self="showModal = false">
        <div class="modal" role="dialog" aria-modal="true">
          <div class="modal-header">
            <h2>New Chat Session</h2>
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
                <option
                  v-for="lib in libStore.libraries"
                  :key="lib.library_id"
                  :value="lib.library_id"
                >
                  {{ lib.name }} ({{ lib.documents.length }} docs)
                </option>
              </select>
              <p v-if="!libStore.libraries.length" class="field-hint warn">
                No libraries found. <RouterLink to="/libraries">Create one first.</RouterLink>
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
                  @click="form.provider = p as typeof form.provider; onProviderChange()"
                >
                  {{ p === 'openai' ? 'OpenAI' : p === 'google' ? 'Google' : 'Anthropic' }}
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

            <!-- Title (optional) -->
            <div class="field">
              <label class="field-label">Session title <span class="optional">(optional)</span></label>
              <input v-model="form.title" class="input" placeholder="New Chat" />
            </div>

            <div v-if="createError" class="error-msg">{{ createError }}</div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-ghost" @click="showModal = false">Cancel</button>
            <button
              class="btn btn-primary"
              :disabled="creating || !form.library_id"
              @click="createSession"
            >
              <span v-if="creating" class="spinner" />
              Create Session
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────────── */
.chat-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.session-panel { display: flex; flex-shrink: 0; }

.chat-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
  position: relative;
}

.mobile-sessions-btn { display: none; }

/* ── Mobile ──────────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .chat-layout { height: calc(100vh - 52px); }

  /* Session panel becomes a slide-in drawer */
  .session-panel {
    position: fixed; top: 52px; left: 0; bottom: 0;
    z-index: 55;
    transform: translateX(-100%);
    transition: transform .25s ease;
  }
  .session-panel.drawer-open { transform: translateX(0); }

  .drawer-backdrop {
    position: fixed; inset: 0; top: 52px;
    z-index: 50;
    background: rgba(0,0,0,.4);
  }

  /* "Sessions" toggle button visible on mobile */
  .mobile-sessions-btn {
    display: flex;
    position: absolute; top: 8px; left: 8px; z-index: 10;
    gap: 6px; background: var(--bg-surface);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-sm);
  }
}

/* ── Empty state ─────────────────────────────────────────────────────────────── */
.no-session {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; padding: 32px;
  color: var(--txt-muted);
}
.no-session-icon { font-size: 3rem; }
.no-session h2   { color: var(--txt-base); }
.hint-warn { font-size: 0.85rem; }
.hint-warn a { color: var(--clr-primary); }

/* ── Modal ──────────────────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
}
.modal {
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  width: 100%; max-width: 460px;
  box-shadow: 0 16px 48px rgba(0,0,0,.18);
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border);
}
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
}

/* ── Form fields ────────────────────────────────────────────────────────────── */
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label {
  font-size: 0.82rem; font-weight: 600; color: var(--txt-muted);
}
.required { color: var(--clr-danger); }
.optional  { color: var(--txt-muted); font-weight: 400; }
.field-hint { font-size: 0.8rem; color: var(--txt-muted); }
.field-hint.warn { color: var(--clr-warn); }
.field-hint a { color: var(--clr-primary); }

.provider-grid {
  display: flex; gap: 8px;
}
.provider-btn {
  flex: 1; padding: 7px 10px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-page); cursor: pointer;
  font-size: 0.85rem; font-weight: 500; color: var(--txt-muted);
  transition: all .15s;
}
.provider-btn:hover  { border-color: var(--clr-primary); color: var(--clr-primary); }
.provider-btn.active { border-color: var(--clr-primary); background: #eff6ff; color: var(--clr-primary); font-weight: 600; }

.error-msg {
  padding: 8px 12px;
  background: #fee2e2; color: #991b1b;
  border-radius: var(--radius-sm); font-size: 0.85rem;
}
</style>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useLibrariesStore } from '@/stores/libraries'
import LibraryPicker from '@/components/LibraryPicker.vue'

const store = useLibrariesStore()

const showCreate = ref(false)
const newName    = ref('')
const newDesc    = ref('')
const creating   = ref(false)

const editingId  = ref<string | null>(null)
const editName   = ref('')

const selectedId  = ref<string | null>(null)
const selectedLib = computed(() =>
  store.libraries.find(l => l.library_id === selectedId.value) ?? null,
)

onMounted(() => store.fetchLibraries())

async function create() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    const lib = await store.createLibrary(newName.value.trim(), newDesc.value.trim() || undefined)
    selectedId.value = lib.library_id
    showCreate.value = false
    newName.value = ''
    newDesc.value = ''
  } finally {
    creating.value = false
  }
}

function startEdit(lib: { library_id: string; name: string }) {
  editingId.value = lib.library_id
  editName.value  = lib.name
}
async function saveEdit(id: string) {
  if (!editName.value.trim()) return
  await store.renameLibrary(id, editName.value.trim())
  editingId.value = null
}

async function remove(id: string) {
  if (!confirm('Delete this library? Sessions will also be deleted.')) return
  if (selectedId.value === id) selectedId.value = null
  await store.deleteLibrary(id)
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-eyebrow">
        <span class="eyebrow-dot" />
        Organize
      </div>
      <h1>Libraries</h1>
      <p>Group documents into named Libraries. Each Library powers its own chat sessions.</p>
    </div>

    <div class="split">
      <!-- Library list ──────────────────────────────────────────────────────── -->
      <aside class="lib-panel">
        <div class="panel-toolbar">
          <span class="panel-title">All libraries</span>
          <button class="btn btn-sm btn-green" @click="showCreate = !showCreate">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            New
          </button>
        </div>

        <!-- Create form -->
        <div v-if="showCreate" class="create-form">
          <input v-model="newName" class="input" placeholder="Library name" autofocus @keyup.enter="create" />
          <input v-model="newDesc" class="input" placeholder="Description (optional)" style="margin-top:8px" />
          <div class="form-actions">
            <button class="btn btn-sm btn-green" :disabled="creating || !newName.trim()" @click="create">
              <span v-if="creating" class="spinner" />
              Create
            </button>
            <button class="btn btn-sm btn-ghost" @click="showCreate = false; newName = ''; newDesc = ''">Cancel</button>
          </div>
        </div>

        <div v-if="store.loading" class="loading-row">
          <span class="spinner" /> Loading…
        </div>
        <div v-else-if="store.error" class="error-banner">{{ store.error }}</div>
        <div v-else-if="!store.libraries.length" class="empty-hint">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" style="color:var(--brand-green);opacity:.5;margin-bottom:8px">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <p>No libraries yet.<br/>Create one to get started.</p>
        </div>

        <ul v-else class="lib-list">
          <li
            v-for="lib in store.libraries"
            :key="lib.library_id"
            class="lib-row"
            :class="{ selected: selectedId === lib.library_id }"
            @click="selectedId = lib.library_id"
          >
            <template v-if="editingId === lib.library_id">
              <input
                v-model="editName" class="input"
                style="height:30px;font-size:.84rem;padding:0 8px"
                autofocus
                @keyup.enter="saveEdit(lib.library_id)"
                @keyup.esc="editingId = null"
                @click.stop
              />
              <button class="btn btn-xs btn-green" @click.stop="saveEdit(lib.library_id)">Save</button>
              <button class="btn btn-xs btn-ghost" @click.stop="editingId = null">✕</button>
            </template>
            <template v-else>
              <div class="lib-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <div class="lib-info">
                <span class="lib-name">{{ lib.name }}</span>
                <span class="lib-meta">{{ lib.documents.length }} doc{{ lib.documents.length !== 1 ? 's' : '' }}</span>
              </div>
              <div class="lib-row-actions" @click.stop>
                <button class="btn btn-icon btn-ghost btn-sm" title="Rename" @click="startEdit(lib)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="btn btn-icon btn-ghost btn-sm" title="Delete" style="color:var(--clr-danger)" @click="remove(lib.library_id)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6l-1 14H6L5 6"/>
                  </svg>
                </button>
              </div>
            </template>
          </li>
        </ul>
      </aside>

      <!-- Library detail ────────────────────────────────────────────────────── -->
      <section class="detail-panel">
        <div v-if="!selectedLib" class="empty-state">
          <div class="empty-illustration">
            <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <p>Select a library on the left to manage its documents.</p>
        </div>
        <template v-else>
          <div class="detail-header">
            <div class="detail-title-row">
              <div class="detail-lib-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <div>
                <h2>{{ selectedLib.name }}</h2>
                <p v-if="selectedLib.description" style="font-size:.84rem;margin-top:2px">{{ selectedLib.description }}</p>
              </div>
            </div>
          </div>
          <LibraryPicker :library-id="selectedLib.library_id" />
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 40px 36px; }
.page-header { margin-bottom: 32px; max-width: 860px; }

.page-eyebrow {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: .75rem; font-weight: 600; letter-spacing: .07em;
  text-transform: uppercase; color: var(--brand-green);
  margin-bottom: 10px;
}
.eyebrow-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--brand-green); display: inline-block;
}

.page-header h1 { margin-bottom: 8px; }

/* ── Green button variant ────────────────────────────────────────────────────── */
.btn-green { background: var(--brand-green); color: #fff; border: none; }
.btn-green:not(:disabled):hover { background: #08b872; }

/* ── Split layout ────────────────────────────────────────────────────────────── */
.split {
  display: grid;
  grid-template-columns: 268px 1fr;
  gap: 20px;
  align-items: start;
}

@media (max-width: 768px) {
  .page  { padding: 20px 16px; }
  .split { grid-template-columns: 1fr; }
}

/* ── Library list panel ──────────────────────────────────────────────────────── */
.lib-panel {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.panel-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.panel-title {
  font-size: .72rem; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: .06em;
}

.create-form { padding: 12px 14px; border-bottom: 1px solid var(--border); }
.form-actions { display: flex; gap: 8px; margin-top: 10px; }

.loading-row {
  display: flex; align-items: center; gap: 8px;
  padding: 16px 14px; color: var(--text-muted); font-size: .875rem;
}
.error-banner {
  padding: 12px 14px;
  background: rgba(242,78,30,.08); color: #b93200; font-size: .875rem;
}
.empty-hint {
  padding: 32px 16px; text-align: center; color: var(--text-muted);
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.empty-hint p { font-size: .85rem; }

.lib-list { list-style: none; }
.lib-row {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: background .12s;
}
.lib-row:last-child { border-bottom: none; }
.lib-row:hover    { background: var(--bg-alt); }
.lib-row.selected { background: rgba(10,207,131,.07); }

.lib-icon {
  width: 28px; height: 28px; border-radius: 7px; flex-shrink: 0;
  background: rgba(10,207,131,.1); color: var(--brand-green);
  display: flex; align-items: center; justify-content: center;
}
.lib-row.selected .lib-icon { background: rgba(10,207,131,.18); }

.lib-info { flex: 1; min-width: 0; }
.lib-name {
  display: block; font-size: .875rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.lib-row.selected .lib-name { color: #089e62; font-weight: 600; }
.lib-meta { display: block; font-size: .72rem; color: var(--text-muted); margin-top: 1px; }

.lib-row-actions { display: flex; gap: 2px; opacity: 0; transition: opacity .15s; }
.lib-row:hover .lib-row-actions { opacity: 1; }

/* ── Detail panel ────────────────────────────────────────────────────────────── */
.detail-panel {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
  min-height: 320px;
}

.empty-state {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  min-height: 280px; gap: 12px;
}
.empty-illustration {
  width: 72px; height: 72px; border-radius: 20px;
  background: rgba(10,207,131,.1);
  color: var(--brand-green); opacity: .7;
  display: flex; align-items: center; justify-content: center;
}

.detail-header {
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
}
.detail-title-row { display: flex; align-items: center; gap: 12px; }
.detail-lib-icon {
  width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0;
  background: rgba(10,207,131,.12);
  color: var(--brand-green);
  display: flex; align-items: center; justify-content: center;
}
</style>

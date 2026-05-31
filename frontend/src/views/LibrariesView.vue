<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useLibrariesStore } from '@/stores/libraries'
import LibraryPicker from '@/components/LibraryPicker.vue'

const store = useLibrariesStore()

// — Create form
const showCreate = ref(false)
const newName = ref('')
const newDesc = ref('')
const creating = ref(false)

// — Rename form
const editingId = ref<string | null>(null)
const editName = ref('')

// — Selected library for doc management
const selectedId = ref<string | null>(null)
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
  editName.value = lib.name
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
      <h1>Libraries</h1>
      <p>Group documents into named Libraries. Each Library has its own RAG config and can power multiple chat sessions.</p>
    </div>

    <div class="split">
      <!-- ── Library list ───────────────────────────────────────────────────── -->
      <aside class="lib-panel">
        <div class="panel-toolbar">
          <span class="panel-title">All libraries</span>
          <button class="btn btn-sm btn-primary" @click="showCreate = !showCreate">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New
          </button>
        </div>

        <!-- Create form -->
        <div v-if="showCreate" class="create-form card">
          <input v-model="newName" class="input" placeholder="Library name" @keyup.enter="create" autofocus />
          <input v-model="newDesc" class="input" placeholder="Description (optional)" style="margin-top:8px" />
          <div class="form-actions">
            <button class="btn btn-sm btn-primary" :disabled="creating || !newName.trim()" @click="create">
              <span v-if="creating" class="spinner" />
              Create
            </button>
            <button class="btn btn-sm btn-ghost" @click="showCreate = false; newName = ''; newDesc = ''">Cancel</button>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="store.loading" class="loading-row">
          <span class="spinner" /> Loading…
        </div>

        <!-- Error -->
        <div v-else-if="store.error" class="error-banner">{{ store.error }}</div>

        <!-- Empty -->
        <div v-else-if="!store.libraries.length" class="empty-state">
          <p>No libraries yet. Create one to get started.</p>
        </div>

        <!-- List -->
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
                v-model="editName"
                class="input"
                style="height:28px;font-size:0.85rem"
                @keyup.enter="saveEdit(lib.library_id)"
                @keyup.esc="editingId = null"
                @click.stop
                autofocus
              />
              <button class="btn btn-sm btn-primary" @click.stop="saveEdit(lib.library_id)">Save</button>
              <button class="btn btn-sm btn-ghost" @click.stop="editingId = null">✕</button>
            </template>
            <template v-else>
              <div class="lib-info">
                <span class="lib-name">{{ lib.name }}</span>
                <span class="lib-meta">{{ lib.documents.length }} doc{{ lib.documents.length !== 1 ? 's' : '' }}</span>
              </div>
              <div class="lib-row-actions" @click.stop>
                <button class="btn btn-icon btn-ghost btn-sm" title="Rename" @click="startEdit(lib)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="btn btn-icon btn-ghost btn-sm" title="Delete" @click="remove(lib.library_id)" style="color:var(--clr-danger)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/></svg>
                </button>
              </div>
            </template>
          </li>
        </ul>
      </aside>

      <!-- ── Library detail ─────────────────────────────────────────────────── -->
      <section class="detail-panel">
        <div v-if="!selectedLib" class="empty-state" style="height:100%">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <p>Select a library to manage its documents.</p>
        </div>
        <template v-else>
          <div class="detail-header">
            <div>
              <h2>{{ selectedLib.name }}</h2>
              <p v-if="selectedLib.description" style="font-size:0.875rem;color:var(--txt-muted);margin-top:2px">{{ selectedLib.description }}</p>
            </div>
          </div>
          <LibraryPicker :library-id="selectedLib.library_id" />
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px; }
.page-header { margin-bottom: 24px; max-width: 820px; }
.page-header h1 { margin-bottom: 6px; }

.split {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 24px;
  align-items: start;
}

/* ── Library panel ─────────────────────────────────────────────────────────── */
.lib-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.panel-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-page);
}
.panel-title { font-size: 0.8rem; font-weight: 600; color: var(--txt-muted); text-transform: uppercase; letter-spacing: .05em; }

.create-form { margin: 12px; }
.form-actions { display: flex; gap: 8px; margin-top: 8px; }

.loading-row { display: flex; align-items: center; gap: 8px; padding: 16px; color: var(--txt-muted); }
.error-banner { padding: 12px 14px; background: #fee2e2; color: #991b1b; font-size: 0.875rem; }

.lib-list { list-style: none; }
.lib-row {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: background 0.1s;
}
.lib-row:last-child { border-bottom: none; }
.lib-row:hover    { background: var(--bg-page); }
.lib-row.selected { background: #eff6ff; }

.lib-info { flex: 1; min-width: 0; }
.lib-name { display: block; font-size: 0.875rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lib-meta { display: block; font-size: 0.75rem; color: var(--txt-muted); }
.lib-row-actions { display: flex; gap: 2px; opacity: 0; transition: opacity 0.15s; }
.lib-row:hover .lib-row-actions { opacity: 1; }

/* ── Detail panel ──────────────────────────────────────────────────────────── */
.detail-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  min-height: 300px;
}
.detail-header {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
</style>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useLibrariesStore } from '@/stores/libraries'
import { useDocumentsStore } from '@/stores/documents'

const props = defineProps<{ libraryId: string }>()

const libStore = useLibrariesStore()
const docStore = useDocumentsStore()

onMounted(() => docStore.fetchDocuments())

const library       = computed(() => libStore.libraries.find(l => l.library_id === props.libraryId))
const inLibrary     = computed(() => library.value?.documents ?? [])
const inLibraryIds  = computed(() => new Set(inLibrary.value.map(d => d.doc_id)))
const available     = computed(() => docStore.documents.filter(d => !inLibraryIds.value.has(d.doc_id)))

async function add(doc_id: string)    { await libStore.addDocument(props.libraryId, doc_id) }
async function remove(doc_id: string) { await libStore.removeDocument(props.libraryId, doc_id) }
</script>

<template>
  <div class="picker">
    <!-- Docs in library -->
    <div class="section">
      <h3 class="section-title">
        <span class="section-dot" style="background:var(--brand-green)" />
        In this library
        <span class="count-chip">{{ inLibrary.length }}</span>
      </h3>
      <p v-if="!inLibrary.length" class="empty-hint">No documents yet — add from below.</p>
      <ul v-else class="pick-list">
        <li v-for="doc in inLibrary" :key="doc.doc_id" class="pick-row pick-row-in">
          <div class="pick-icon pick-icon-green">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <span class="pick-name">{{ doc.name }}</span>
          <span :class="['badge', `badge-${doc.status}`]">{{ doc.status }}</span>
          <button class="btn btn-sm btn-ghost btn-icon remove-btn" title="Remove from library" @click="remove(doc.doc_id)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </li>
      </ul>
    </div>

    <!-- Available docs -->
    <div class="section">
      <h3 class="section-title">
        <span class="section-dot" style="background:var(--brand-blue)" />
        Available to add
        <span class="count-chip">{{ available.length }}</span>
      </h3>
      <p v-if="!available.length && !docStore.documents.length" class="empty-hint">
        Upload PDFs on the Documents page first.
      </p>
      <p v-else-if="!available.length" class="empty-hint">All uploaded documents are already in this library.</p>
      <ul v-else class="pick-list">
        <li v-for="doc in available" :key="doc.doc_id" class="pick-row">
          <div class="pick-icon">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <span class="pick-name">{{ doc.name }}</span>
          <span :class="['badge', `badge-${doc.status}`]">{{ doc.status }}</span>
          <button
            class="btn btn-sm btn-primary"
            :disabled="doc.status !== 'indexed'"
            :title="doc.status !== 'indexed' ? 'Wait for indexing to complete' : 'Add to this library'"
            @click="add(doc.doc_id)"
          >
            + Add
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.picker { display: flex; flex-direction: column; gap: 24px; }

.section { display: flex; flex-direction: column; gap: 10px; }

.section-title {
  display: flex; align-items: center; gap: 8px;
  font-size: .8rem; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: .06em;
}
.section-dot {
  width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0;
}
.count-chip {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 20px; height: 20px; padding: 0 6px;
  background: var(--bg-alt); border: 1px solid var(--border);
  border-radius: var(--radius-pill); font-size: .72rem; font-weight: 600;
  color: var(--text-muted);
}

.empty-hint { font-size: .84rem; color: var(--text-muted); padding: 6px 0; }

.pick-list { list-style: none; display: flex; flex-direction: column; gap: 5px; }

.pick-row {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 12px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg); transition: box-shadow .15s;
}
.pick-row:hover { box-shadow: var(--shadow-card); }
.pick-row-in  { border-color: rgba(10,207,131,.2); background: rgba(10,207,131,.03); }

.pick-icon {
  width: 26px; height: 26px; border-radius: 7px; flex-shrink: 0;
  background: rgba(162,89,255,.1); color: var(--brand-purple);
  display: flex; align-items: center; justify-content: center;
}
.pick-icon-green { background: rgba(10,207,131,.12); color: var(--brand-green); }

.pick-name {
  flex: 1; font-size: .875rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.remove-btn { color: var(--clr-danger); border-color: transparent; }
.remove-btn:hover { background: rgba(242,78,30,.08); border-color: transparent; }
</style>

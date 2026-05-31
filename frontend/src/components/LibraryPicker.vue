<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useLibrariesStore } from '@/stores/libraries'
import { useDocumentsStore } from '@/stores/documents'

const props = defineProps<{ libraryId: string }>()

const libStore = useLibrariesStore()
const docStore = useDocumentsStore()

onMounted(() => docStore.fetchDocuments())

const library = computed(() =>
  libStore.libraries.find(l => l.library_id === props.libraryId),
)

const inLibrary = computed(() => library.value?.documents ?? [])

const inLibraryIds = computed(() => new Set(inLibrary.value.map(d => d.doc_id)))

const available = computed(() =>
  docStore.documents.filter(d => !inLibraryIds.value.has(d.doc_id)),
)

async function add(doc_id: string) {
  await libStore.addDocument(props.libraryId, doc_id)
}
async function remove(doc_id: string) {
  await libStore.removeDocument(props.libraryId, doc_id)
}
</script>

<template>
  <div class="picker">
    <!-- Docs in library -->
    <div class="section">
      <h3 class="section-title">
        <span>In this library</span>
        <span class="count-badge">{{ inLibrary.length }}</span>
      </h3>
      <p v-if="!inLibrary.length" class="empty-hint">No documents yet. Add from the list below.</p>
      <ul v-else class="pick-list">
        <li v-for="doc in inLibrary" :key="doc.doc_id" class="pick-row">
          <span class="pick-name">{{ doc.name }}</span>
          <span :class="['badge', `badge-${doc.status}`]">{{ doc.status }}</span>
          <button class="btn btn-sm btn-ghost btn-icon remove-btn" title="Remove" @click="remove(doc.doc_id)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </li>
      </ul>
    </div>

    <!-- Available docs -->
    <div class="section">
      <h3 class="section-title">
        <span>Available documents</span>
        <span class="count-badge">{{ available.length }}</span>
      </h3>
      <p v-if="!available.length && !docStore.documents.length" class="empty-hint">
        Upload PDFs on the Documents page first.
      </p>
      <p v-else-if="!available.length" class="empty-hint">All uploaded documents are already in this library.</p>
      <ul v-else class="pick-list">
        <li v-for="doc in available" :key="doc.doc_id" class="pick-row">
          <span class="pick-name">{{ doc.name }}</span>
          <span :class="['badge', `badge-${doc.status}`]">{{ doc.status }}</span>
          <button
            class="btn btn-sm btn-primary"
            :disabled="doc.status !== 'indexed'"
            :title="doc.status !== 'indexed' ? 'Wait for indexing to finish' : 'Add to library'"
            @click="add(doc.doc_id)"
          >
            Add
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.picker { display: flex; flex-direction: column; gap: 20px; }

.section { display: flex; flex-direction: column; gap: 8px; }
.section-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 0.85rem; font-weight: 600; color: var(--txt-muted); text-transform: uppercase; letter-spacing: .05em;
}
.count-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 20px; height: 20px; padding: 0 6px;
  background: var(--bg-page); border: 1px solid var(--border);
  border-radius: 99px; font-size: 0.75rem; font-weight: 600;
  color: var(--txt-muted);
}

.empty-hint { font-size: 0.85rem; color: var(--txt-muted); padding: 8px 0; }

.pick-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
.pick-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-surface);
}
.pick-name {
  flex: 1; font-size: 0.875rem;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.remove-btn { color: var(--clr-danger); border-color: transparent; }
.remove-btn:hover { background: #fee2e2; }
</style>

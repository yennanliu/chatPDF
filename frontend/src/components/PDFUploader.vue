<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDocumentsStore } from '@/stores/documents'

const store = useDocumentsStore()
const fileInput = ref<HTMLInputElement | null>(null)
const isDragOver = ref(false)
const uploading = ref(false)

onMounted(() => store.fetchDocuments())

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

async function handleFiles(files: FileList | null) {
  if (!files?.length) return
  uploading.value = true
  for (const file of Array.from(files)) {
    if (!file.name.endsWith('.pdf')) {
      store.error = `${file.name} is not a PDF`
      continue
    }
    await store.uploadDocument(file)
  }
  uploading.value = false
  if (fileInput.value) fileInput.value.value = ''
}

function onDrop(e: DragEvent) {
  isDragOver.value = false
  handleFiles(e.dataTransfer?.files ?? null)
}
</script>

<template>
  <div class="uploader">
    <!-- Drop zone -->
    <div
      class="drop-zone"
      :class="{ 'drag-over': isDragOver }"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".pdf"
        multiple
        style="display:none"
        @change="handleFiles(($event.target as HTMLInputElement).files)"
      />
      <div class="drop-icon">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <polyline points="9 15 12 12 15 15"/>
        </svg>
      </div>
      <p class="drop-label">
        <span v-if="uploading"><span class="spinner" /> Uploading…</span>
        <span v-else>Drop PDFs here or <strong>click to browse</strong></span>
      </p>
      <p class="drop-hint">Only .pdf files · multiple selection supported</p>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="error-banner">
      {{ store.error }}
      <button class="btn btn-sm btn-ghost" @click="store.error = null">✕</button>
    </div>

    <!-- Document list -->
    <div v-if="store.loading && !store.documents.length" class="loading-row">
      <span class="spinner" /> Loading documents…
    </div>

    <div v-else-if="!store.documents.length" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <p>No documents yet. Upload a PDF above.</p>
    </div>

    <ul v-else class="doc-list">
      <li v-for="doc in store.documents" :key="doc.doc_id" class="doc-row">
        <div class="doc-info">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;color:var(--clr-primary)">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <div>
            <span class="doc-name">{{ doc.name }}</span>
            <span class="doc-meta">
              {{ doc.page_count != null ? `${doc.page_count}p · ` : '' }}{{ formatDate(doc.created_at) }}
            </span>
          </div>
        </div>
        <div class="doc-actions">
          <span :class="['badge', `badge-${doc.status}`]">
            <span v-if="doc.status === 'pending'" class="spinner" style="width:9px;height:9px;margin-right:4px" />
            {{ doc.status }}
          </span>
          <button class="btn btn-sm btn-ghost btn-icon" title="Delete" @click="store.deleteDocument(doc.doc_id)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6m4-6v6"/>
            </svg>
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.uploader { display: flex; flex-direction: column; gap: 16px; }

.drop-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-md);
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: var(--bg-surface);
}
.drop-zone:hover, .drop-zone.drag-over {
  border-color: var(--clr-primary);
  background: #eff6ff;
}
.drop-icon { color: var(--clr-primary); margin-bottom: 10px; }
.drop-label { font-size: 0.9rem; color: var(--txt-base); margin-bottom: 4px; }
.drop-hint  { font-size: 0.8rem; color: var(--txt-muted); }

.error-banner {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; background: #fee2e2; border-radius: var(--radius-sm);
  color: #991b1b; font-size: 0.875rem;
}

.loading-row {
  display: flex; align-items: center; gap: 8px;
  padding: 16px; color: var(--txt-muted);
}

.doc-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.doc-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.doc-info {
  display: flex; align-items: center; gap: 10px; min-width: 0;
}
.doc-name {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}
.doc-meta { display: block; font-size: 0.75rem; color: var(--txt-muted); }
.doc-actions {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
</style>

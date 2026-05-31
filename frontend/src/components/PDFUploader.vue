<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDocumentsStore, type Document } from '@/stores/documents'

const store = useDocumentsStore()
const fileInput  = ref<HTMLInputElement | null>(null)
const isDragOver = ref(false)

// Tracks filenames currently in-flight (POST request not yet returned)
const uploadingNames = ref<Set<string>>(new Set())

onMounted(() => store.fetchDocuments())

// Merge in-flight entries into the display list so the drop-zone always empties
const displayDocs = computed<Array<Document | { _uploading: true; name: string }>>(() => {
  const uploading = [...uploadingNames.value].map(n => ({ _uploading: true as const, name: n }))
  return [...uploading, ...store.documents]
})

function statusLabel(doc: Document): string {
  if (doc.status === 'pending') return 'indexing'
  return doc.status
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

async function handleFiles(files: FileList | null) {
  if (!files?.length) return
  if (fileInput.value) fileInput.value.value = ''

  for (const file of Array.from(files)) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      store.error = `"${file.name}" is not a PDF — only .pdf files are accepted`
      continue
    }
    // Mark as in-flight so the UI shows "uploading" immediately
    uploadingNames.value = new Set([...uploadingNames.value, file.name])
    await store.uploadDocument(file)
    uploadingNames.value = new Set([...uploadingNames.value].filter(n => n !== file.name))
  }
}

function onDrop(e: DragEvent) {
  isDragOver.value = false
  handleFiles(e.dataTransfer?.files ?? null)
}

function isUploading(name: string) { return uploadingNames.value.has(name) }
</script>

<template>
  <div class="uploader">
    <!-- ── Drop zone ──────────────────────────────────────────────────────── -->
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
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="12" y1="18" x2="12" y2="12" />
          <polyline points="9 15 12 12 15 15" />
        </svg>
      </div>
      <p class="drop-label">Drop PDFs here or <strong>click to browse</strong></p>
      <p class="drop-hint">Only .pdf files · multiple selection supported</p>
    </div>

    <!-- ── Error ──────────────────────────────────────────────────────────── -->
    <div v-if="store.error" class="error-banner">
      <span>{{ store.error }}</span>
      <button class="btn btn-sm btn-ghost" @click="store.error = null">✕</button>
    </div>

    <!-- ── Loading skeleton ───────────────────────────────────────────────── -->
    <div v-if="store.loading && !displayDocs.length" class="loading-row">
      <span class="spinner" /> Loading documents…
    </div>

    <!-- ── Empty state ────────────────────────────────────────────────────── -->
    <div v-else-if="!displayDocs.length" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
      <p>No documents yet. Drop a PDF above to get started.</p>
    </div>

    <!-- ── Document list ──────────────────────────────────────────────────── -->
    <ul v-else class="doc-list">
      <!-- In-flight rows (POST in progress) -->
      <li
        v-for="entry in displayDocs"
        :key="'_uploading' in entry ? `up_${entry.name}` : entry.doc_id"
        class="doc-row"
      >
        <!-- Uploading (POST in-flight) -->
        <template v-if="'_uploading' in entry">
          <div class="doc-info">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;color:var(--clr-primary)">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <div>
              <span class="doc-name">{{ entry.name }}</span>
              <span class="doc-meta">Uploading…</span>
            </div>
          </div>
          <div class="doc-actions">
            <span class="badge badge-uploading">
              <span class="spinner" style="width:9px;height:9px;margin-right:4px" /> uploading
            </span>
          </div>
        </template>

        <!-- Indexed / pending / error rows -->
        <template v-else>
          <div class="doc-info">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;color:var(--clr-primary)">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <div>
              <span class="doc-name">{{ (entry as Document).name }}</span>
              <span class="doc-meta">
                {{ (entry as Document).page_count != null ? `${(entry as Document).page_count}p · ` : '' }}
                {{ formatDate((entry as Document).created_at) }}
              </span>
            </div>
          </div>
          <div class="doc-actions">
            <span :class="['badge', `badge-${(entry as Document).status}`]">
              <span
                v-if="(entry as Document).status === 'pending'"
                class="spinner"
                style="width:9px;height:9px;margin-right:4px"
              />
              {{ statusLabel(entry as Document) }}
            </span>
            <button
              class="btn btn-sm btn-ghost btn-icon"
              title="Delete document"
              :disabled="isUploading((entry as Document).name)"
              @click="store.deleteDocument((entry as Document).doc_id)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14H6L5 6" />
                <path d="M10 11v6m4-6v6" />
              </svg>
            </button>
          </div>
        </template>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.uploader { display: flex; flex-direction: column; gap: 16px; }

/* ── Drop zone ──────────────────────────────────────────────────────────────── */
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-md);
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color .15s, background .15s;
  background: var(--bg-surface);
}
.drop-zone:hover, .drop-zone.drag-over {
  border-color: var(--clr-primary);
  background: #eff6ff;
}
.drop-icon  { color: var(--clr-primary); margin-bottom: 10px; }
.drop-label { font-size: 0.9rem; color: var(--txt-base); margin-bottom: 4px; }
.drop-hint  { font-size: 0.8rem; color: var(--txt-muted); }

/* ── Error banner ───────────────────────────────────────────────────────────── */
.error-banner {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px;
  background: #fee2e2; border-radius: var(--radius-sm);
  color: #991b1b; font-size: 0.875rem;
}

/* ── States ─────────────────────────────────────────────────────────────────── */
.loading-row { display: flex; align-items: center; gap: 8px; padding: 16px; color: var(--txt-muted); }

/* ── Badge overrides ────────────────────────────────────────────────────────── */
.badge-uploading { background: #dbeafe; color: #1e40af; display: inline-flex; align-items: center; }

/* ── Document list ──────────────────────────────────────────────────────────── */
.doc-list { list-style: none; display: flex; flex-direction: column; gap: 6px; }

.doc-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.doc-info { display: flex; align-items: center; gap: 10px; min-width: 0; }
.doc-name {
  display: block; font-size: 0.875rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: min(400px, 55vw);
}
.doc-meta { display: block; font-size: 0.75rem; color: var(--txt-muted); }
.doc-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
</style>

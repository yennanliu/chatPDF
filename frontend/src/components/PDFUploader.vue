<script setup lang="ts">
import { ref, onMounted, computed, triggerRef } from 'vue'
import { useDocumentsStore, type Document } from '@/stores/documents'

const store      = useDocumentsStore()
const fileInput  = ref<HTMLInputElement | null>(null)
const isDragOver = ref(false)

const uploadingNames = ref<Set<string>>(new Set())

onMounted(() => store.fetchDocuments())

const displayDocs = computed<Array<Document | { _uploading: true; name: string }>>(() => {
  const uploading = [...uploadingNames.value].map(n => ({ _uploading: true as const, name: n }))
  return [...uploading, ...store.documents]
})

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
    uploadingNames.value.add(file.name)
    triggerRef(uploadingNames)
    await store.uploadDocument(file)
    uploadingNames.value.delete(file.name)
    triggerRef(uploadingNames)
  }
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
        type="file" accept=".pdf" multiple
        style="display:none"
        @change="handleFiles(($event.target as HTMLInputElement).files)"
      />
      <div class="drop-art">
        <div class="drop-ring" />
        <div class="drop-icon-wrap">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <polyline points="9 15 12 12 15 15"/>
          </svg>
        </div>
      </div>
      <p class="drop-label">Drop PDFs here or <strong>click to browse</strong></p>
      <p class="drop-hint">Only .pdf files · multiple files supported</p>
    </div>

    <!-- Error -->
    <div v-if="store.error" class="error-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span>{{ store.error }}</span>
      <button class="btn btn-sm btn-ghost" style="padding:4px 10px" @click="store.error = null">✕</button>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && !displayDocs.length" class="loading-row">
      <span class="spinner" /> Loading your documents…
    </div>

    <!-- Empty -->
    <div v-else-if="!displayDocs.length" class="empty-docs">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <p>No documents yet — drop a PDF above to get started.</p>
    </div>

    <!-- Document list -->
    <ul v-else class="doc-list">
      <li
        v-for="entry in displayDocs"
        :key="'_uploading' in entry ? `up_${entry.name}` : entry.doc_id"
        class="doc-row"
      >
        <!-- Uploading -->
        <template v-if="'_uploading' in entry">
          <div class="doc-file-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div class="doc-info">
            <span class="doc-name">{{ entry.name }}</span>
            <span class="doc-meta">Uploading…</span>
          </div>
          <span class="badge badge-uploading">
            <span class="spinner" style="width:9px;height:9px;margin-right:5px" /> uploading
          </span>
        </template>

        <!-- Real doc -->
        <template v-else>
          <div class="doc-file-icon" :class="`status-${(entry as Document).status}`">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div class="doc-info">
            <span class="doc-name">{{ (entry as Document).name }}</span>
            <span class="doc-meta">
              {{ (entry as Document).page_count != null ? `${(entry as Document).page_count}p · ` : '' }}
              {{ formatDate((entry as Document).created_at) }}
            </span>
          </div>
          <div class="doc-actions">
            <span :class="['badge', `badge-${(entry as Document).status}`]">
              <span v-if="(entry as Document).status === 'pending'" class="spinner" style="width:9px;height:9px;margin-right:5px" />
              {{ (entry as Document).status === 'pending' ? 'indexing…' : (entry as Document).status }}
            </span>
            <button
              class="btn btn-sm btn-ghost btn-icon"
              title="Delete document"
              :disabled="uploadingNames.value.has((entry as Document).name)"
              style="color:var(--clr-danger)"
              @click="store.deleteDocument((entry as Document).doc_id)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6m4-6v6"/>
              </svg>
            </button>
          </div>
        </template>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.uploader { display: flex; flex-direction: column; gap: 14px; }

/* ── Drop zone ───────────────────────────────────────────────────────────────── */
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-md);
  padding: 36px 24px 28px;
  text-align: center; cursor: pointer;
  transition: border-color .15s, background .15s;
  background: var(--bg);
  display: flex; flex-direction: column; align-items: center;
}
.drop-zone:hover, .drop-zone.drag-over {
  border-color: var(--brand-orange);
  background: rgba(242,78,30,.03);
}

.drop-art {
  position: relative; width: 64px; height: 64px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 14px;
}
.drop-ring {
  position: absolute; inset: 0; border-radius: 50%;
  background: rgba(242,78,30,.1);
  transition: background .15s;
}
.drop-zone:hover .drop-ring,
.drop-zone.drag-over .drop-ring { background: rgba(242,78,30,.18); }

.drop-icon-wrap {
  position: relative;
  color: var(--brand-orange);
}

.drop-label { font-size: .9rem; color: var(--text); margin-bottom: 4px; }
.drop-label strong { color: var(--brand-orange); }
.drop-hint  { font-size: .8rem; color: var(--text-muted); }

/* ── Error ───────────────────────────────────────────────────────────────────── */
.error-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px;
  background: rgba(242,78,30,.08); border-radius: var(--radius-sm);
  color: #b93200; font-size: .875rem;
}
.error-banner span:nth-child(2) { flex: 1; }

/* ── States ──────────────────────────────────────────────────────────────────── */
.loading-row {
  display: flex; align-items: center; gap: 8px;
  padding: 16px; color: var(--text-muted); font-size: .875rem;
}
.empty-docs {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 32px 0; color: var(--text-muted); opacity: .6; text-align: center;
}
.empty-docs p { font-size: .875rem; }

/* ── Badge override ──────────────────────────────────────────────────────────── */
.badge-uploading {
  background: rgba(26,188,254,.12); color: #0896c8;
  display: inline-flex; align-items: center;
}

/* ── Document list ───────────────────────────────────────────────────────────── */
.doc-list { list-style: none; display: flex; flex-direction: column; gap: 6px; }

.doc-row {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: box-shadow .15s;
}
.doc-row:hover { box-shadow: var(--shadow-card); }

.doc-file-icon {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  background: rgba(242,78,30,.1); color: var(--brand-orange);
  display: flex; align-items: center; justify-content: center;
}
.doc-file-icon.status-indexed { background: rgba(10,207,131,.1);  color: var(--brand-green); }
.doc-file-icon.status-error   { background: rgba(242,78,30,.1);   color: var(--brand-orange); }
.doc-file-icon.status-pending { background: rgba(245,158,11,.12); color: #d97706; }

.doc-info  { flex: 1; min-width: 0; }
.doc-name  {
  display: block; font-size: .875rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: min(400px, 55vw);
}
.doc-meta  { display: block; font-size: .72rem; color: var(--text-muted); margin-top: 1px; }
.doc-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
</style>

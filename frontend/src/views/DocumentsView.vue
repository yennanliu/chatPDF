<script setup lang="ts">
import { ref } from 'vue'
import PDFUploader from '@/components/PDFUploader.vue'
import { useDocumentsStore } from '@/stores/documents'
import { useSessionsStore } from '@/stores/sessions'

const docStore  = useDocumentsStore()
const sessStore = useSessionsStore()
const clearing  = ref(false)

async function clearAll() {
  if (!confirm('Delete ALL documents and chat sessions? This cannot be undone.')) return
  clearing.value = true
  try {
    await Promise.all([docStore.deleteAllDocuments(), sessStore.deleteAllSessions()])
  } finally {
    clearing.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="header-row">
        <div>
          <div class="page-eyebrow">
            <span class="eyebrow-dot" style="background:var(--brand-orange)" />
            Upload
          </div>
          <h1>Your Documents</h1>
        </div>
        <button
          class="btn btn-sm btn-danger"
          :disabled="clearing || !docStore.documents.length"
          @click="clearAll"
        >
          <span v-if="clearing" class="spinner" />
          Clear all
        </button>
      </div>
      <p>Drop PDFs here to index them. Once indexed, start a chat and pick which documents to ask about.</p>
    </div>
    <div class="page-body">
      <PDFUploader />
    </div>
  </div>
</template>

<style scoped>
.page { padding: 40px 36px; max-width: 860px; }

.page-header { margin-bottom: 32px; }
.header-row {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 4px;
}

.page-eyebrow {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: .75rem; font-weight: 600; letter-spacing: .07em;
  text-transform: uppercase; color: var(--brand-orange);
  margin-bottom: 10px;
}
.eyebrow-dot {
  width: 7px; height: 7px; border-radius: 50%;
  display: inline-block;
}

.page-header h1 { margin-bottom: 8px; }

@media (max-width: 768px) {
  .page { padding: 20px 16px; }
}
</style>

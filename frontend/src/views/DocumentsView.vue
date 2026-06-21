<script setup lang="ts">
import PDFUploader from '@/components/PDFUploader.vue'
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-eyebrow">
        <span class="eyebrow-dot" style="background:var(--brand-orange)" />
        Upload
      </div>
      <h1>Your Documents</h1>
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

<script setup lang="ts">
import PDFUploader from '@/components/PDFUploader.vue'
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Documents</h1>
      <p>Upload PDFs to index them. Once indexed, add them to Libraries and start chatting.</p>
    </div>
    <div class="page-body">
      <PDFUploader />
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 820px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin-bottom: 6px; }
.page-body {}

@media (max-width: 768px) {
  .page { padding: 16px; }
}
</style>

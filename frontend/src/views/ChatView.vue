<script setup lang="ts">
// Phase 6 will wire up the full chat UI (WebSocket streaming, session sidebar, source citations).
// For now this view shows the available libraries so users can see what's ready to chat about.
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useLibrariesStore } from '@/stores/libraries'

const store = useLibrariesStore()
onMounted(() => store.fetchLibraries())
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Chat</h1>
      <p>Full chat UI with WebSocket streaming and source citations is coming in Phase 6.</p>
    </div>

    <div class="coming-soon card">
      <div class="cs-icon">💬</div>
      <h2>Chat UI — Coming in Phase 6</h2>
      <p class="cs-desc">
        Phase 6 will add the full streaming chat interface:<br>
        session sidebar · streaming token display · source citations · history reload.
      </p>

      <div v-if="store.libraries.length" class="lib-preview">
        <p class="preview-label">Libraries ready to chat:</p>
        <ul class="lib-chips">
          <li v-for="lib in store.libraries" :key="lib.library_id" class="lib-chip">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <span>{{ lib.name }}</span>
            <span class="chip-count">{{ lib.documents.length }} doc{{ lib.documents.length !== 1 ? 's' : '' }}</span>
          </li>
        </ul>
      </div>

      <RouterLink to="/libraries" class="btn btn-primary" style="align-self:center;margin-top:8px">
        Manage Libraries →
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 680px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin-bottom: 6px; }

.coming-soon {
  display: flex; flex-direction: column; gap: 16px;
  padding: 32px;
}
.cs-icon { font-size: 2.5rem; text-align: center; }
.cs-desc { color: var(--txt-muted); font-size: 0.875rem; line-height: 1.7; }

.lib-preview { border-top: 1px solid var(--border); padding-top: 16px; }
.preview-label { font-size: 0.8rem; font-weight: 600; color: var(--txt-muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }
.lib-chips { list-style: none; display: flex; flex-direction: column; gap: 6px; }
.lib-chip {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  font-size: 0.875rem; background: var(--bg-page);
}
.chip-count { margin-left: auto; font-size: 0.75rem; color: var(--txt-muted); }
</style>

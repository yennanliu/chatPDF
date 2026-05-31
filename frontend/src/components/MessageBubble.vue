<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ChatMessage, Source } from '@/composables/useChatSocket'

const props = defineProps<{ message: ChatMessage }>()

const sourcesOpen = ref(false)

const hasSources = computed(
  () => !props.message.isStreaming && (props.message.sources?.length ?? 0) > 0,
)

function scoreColor(score: number) {
  if (score >= 0.8) return '#16a34a'
  if (score >= 0.5) return '#d97706'
  return '#64748b'
}

function truncate(text: string, max = 160) {
  return text.length <= max ? text : text.slice(0, max) + '…'
}
</script>

<template>
  <!-- User message -->
  <div v-if="message.role === 'user'" class="row row-user">
    <div class="bubble bubble-user">
      <span class="content">{{ message.content }}</span>
    </div>
  </div>

  <!-- Assistant message -->
  <div v-else class="row row-assistant">
    <div class="avatar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3" /><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
      </svg>
    </div>
    <div class="assistant-body">
      <div class="bubble bubble-assistant" :class="{ streaming: message.isStreaming }">
        <span class="content">{{ message.content }}</span>
        <span v-if="message.isStreaming && !message.content" class="thinking">thinking…</span>
        <span v-if="message.isStreaming" class="cursor" aria-hidden="true" />
      </div>

      <!-- Source citations -->
      <div v-if="hasSources" class="sources-wrap">
        <button class="sources-toggle" @click="sourcesOpen = !sourcesOpen">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
          </svg>
          {{ (message.sources?.length ?? 0) }} source{{ (message.sources?.length ?? 0) !== 1 ? 's' : '' }}
          <svg
            width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            :style="{ transform: sourcesOpen ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        <div v-if="sourcesOpen" class="sources-list">
          <div v-for="(src, i) in (message.sources as Source[])" :key="i" class="source-card">
            <div class="source-header">
              <span class="source-name">{{ src.doc_name }}</span>
              <span class="source-score" :style="{ color: scoreColor(src.score) }">
                {{ (src.score * 100).toFixed(0) }}%
              </span>
            </div>
            <p class="source-preview">{{ truncate(src.chunk_preview) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Row layout ─────────────────────────────────────────────────────────────── */
.row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
}
.row-user      { justify-content: flex-end; }
.row-assistant { justify-content: flex-start; }

/* ── Avatar ─────────────────────────────────────────────────────────────────── */
.avatar {
  width: 28px; height: 28px; flex-shrink: 0;
  background: var(--clr-primary); color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin-top: 4px;
}

/* ── Bubbles ────────────────────────────────────────────────────────────────── */
.bubble {
  max-width: min(560px, 80vw);
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.9rem;
  line-height: 1.6;
  word-break: break-word;
}

.bubble-user {
  background: var(--clr-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble-assistant {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
  position: relative;
}

.content { white-space: pre-wrap; }

/* ── Streaming indicators ───────────────────────────────────────────────────── */
.thinking { color: var(--txt-muted); font-style: italic; }

.cursor {
  display: inline-block;
  width: 2px; height: 1.1em;
  background: var(--clr-primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink .7s step-end infinite;
}
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* ── Assistant body (bubble + sources) ─────────────────────────────────────── */
.assistant-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }

/* ── Sources ────────────────────────────────────────────────────────────────── */
.sources-wrap { display: flex; flex-direction: column; gap: 4px; }

.sources-toggle {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  background: var(--bg-page); border: 1px solid var(--border);
  border-radius: 99px; cursor: pointer;
  font-size: 0.78rem; color: var(--txt-muted);
  transition: background .15s;
  align-self: flex-start;
}
.sources-toggle:hover { background: var(--border); }

.sources-list {
  display: flex; flex-direction: column; gap: 6px;
  max-width: min(520px, 78vw);
}

.source-card {
  padding: 8px 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.source-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 4px;
}
.source-name {
  font-size: 0.8rem; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 320px;
}
.source-score { font-size: 0.78rem; font-weight: 700; flex-shrink: 0; }
.source-preview {
  font-size: 0.78rem; color: var(--txt-muted);
  line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ChatMessage, Source } from '@/composables/useChatSocket'
import { useToast } from '@/composables/useToast'

const props = defineProps<{ message: ChatMessage }>()
const toast = useToast()

const sourcesOpen = ref(false)

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Could not copy')
  }
}

const hasSources = computed(
  () => !props.message.isStreaming && (props.message.sources?.length ?? 0) > 0,
)

function truncate(text: string, max = 180) {
  return text.length <= max ? text : text.slice(0, max) + '…'
}

function scoreColor(score: number) {
  if (score >= 0.8) return 'var(--brand-green)'
  if (score >= 0.5) return '#f59e0b'
  return 'var(--text-muted)'
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
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    </div>

    <div class="assistant-body">
      <div class="bubble bubble-assistant" :class="{ streaming: message.isStreaming }">
        <span class="content">{{ message.content }}</span>
        <span v-if="message.isStreaming && !message.content" class="thinking">thinking…</span>
        <span v-if="message.isStreaming" class="cursor" aria-hidden="true" />
      </div>

      <button
        v-if="!message.isStreaming && message.content"
        class="copy-btn"
        aria-label="Copy answer to clipboard"
        title="Copy"
        @click="copyContent"
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copy
      </button>

      <!-- Sources -->
      <div v-if="hasSources" class="sources-wrap">
        <button class="sources-toggle" @click="sourcesOpen = !sourcesOpen">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          {{ message.sources?.length }} source{{ (message.sources?.length ?? 0) !== 1 ? 's' : '' }}
          <svg
            width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            :style="{ transform: sourcesOpen ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }"
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        <div v-if="sourcesOpen" class="sources-list">
          <div v-for="(src, i) in (message.sources as Source[])" :key="i" class="source-card">
            <div class="source-header">
              <div class="source-file-icon">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <span class="source-name">{{ src.doc_name }}</span>
              <span v-if="src.page != null" class="source-page">p.{{ src.page }}</span>
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
/* ── Row layout ──────────────────────────────────────────────────────────────── */
.row { display: flex; align-items: flex-start; gap: 10px; padding: 6px 0; }
.row-user      { justify-content: flex-end; }
.row-assistant { justify-content: flex-start; }

/* ── Avatar ──────────────────────────────────────────────────────────────────── */
.avatar {
  width: 30px; height: 30px; flex-shrink: 0;
  background: rgba(162,89,255,.15); color: var(--brand-purple);
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  margin-top: 2px;
}

/* ── Bubbles ─────────────────────────────────────────────────────────────────── */
.bubble {
  max-width: min(560px, 80vw);
  padding: 11px 15px;
  border-radius: 14px;
  font-size: .9rem; line-height: 1.65;
  word-break: break-word;
}

.bubble-user {
  background: var(--brand-purple);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble-assistant {
  background: var(--bg);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-sm);
}

.content { white-space: pre-wrap; }

/* ── Streaming ───────────────────────────────────────────────────────────────── */
.thinking { color: var(--text-muted); font-style: italic; }
.cursor {
  display: inline-block; width: 2px; height: 1.1em;
  background: var(--brand-purple);
  margin-left: 2px; vertical-align: text-bottom;
  animation: blink .7s step-end infinite;
}
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* ── Assistant body ──────────────────────────────────────────────────────────── */
.assistant-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }

/* ── Sources ─────────────────────────────────────────────────────────────────── */
.sources-wrap { display: flex; flex-direction: column; gap: 6px; }

.sources-toggle {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 12px;
  background: rgba(10,207,131,.08); border: 1px solid rgba(10,207,131,.2);
  color: #089e62;
  border-radius: var(--radius-pill); cursor: pointer;
  font-size: .76rem; font-weight: 600;
  transition: background .15s;
  align-self: flex-start;
}
.sources-toggle:hover { background: rgba(10,207,131,.14); }

.sources-list {
  display: flex; flex-direction: column; gap: 6px;
  max-width: min(520px, 78vw);
}

.source-card {
  padding: 10px 13px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  transition: box-shadow .15s;
}
.source-card:hover { box-shadow: var(--shadow-card); }

.source-header {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 5px;
}
.source-file-icon {
  width: 20px; height: 20px; border-radius: 5px; flex-shrink: 0;
  background: rgba(10,207,131,.1); color: var(--brand-green);
  display: flex; align-items: center; justify-content: center;
}
.source-name {
  flex: 1; font-size: .8rem; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 280px;
}
.source-page {
  font-size: .7rem; font-weight: 600; flex-shrink: 0;
  color: var(--text-muted); background: var(--bg-alt);
  padding: 1px 6px; border-radius: var(--radius-pill);
}
.source-score { font-size: .76rem; font-weight: 700; flex-shrink: 0; }

/* Copy button */
.copy-btn {
  align-self: flex-start;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; border: 1px solid var(--border); border-radius: var(--radius-pill);
  background: var(--bg); color: var(--text-muted);
  font-size: .72rem; font-weight: 500; cursor: pointer; font-family: inherit;
  transition: color .15s, border-color .15s; opacity: 0;
}
.row-assistant:hover .copy-btn { opacity: 1; }
.copy-btn:hover { color: var(--text); border-color: #c8c8d0; }

.source-preview {
  font-size: .78rem; color: var(--text-muted); line-height: 1.55;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

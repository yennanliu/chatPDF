<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="toast-host" role="status" aria-live="polite">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="`toast-${t.kind}`">
        <span class="toast-msg">{{ t.message }}</span>
        <button class="toast-close" aria-label="Dismiss notification" @click="dismiss(t.id)">✕</button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-host {
  position: fixed; bottom: 20px; right: 20px; z-index: 200;
  display: flex; flex-direction: column; gap: 10px;
  max-width: min(360px, calc(100vw - 32px));
}
.toast {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 14px; border-radius: var(--radius-sm);
  font-size: .85rem; color: #fff;
  box-shadow: var(--shadow-drop);
  animation: toast-in .2s ease;
}
.toast-msg { flex: 1; word-break: break-word; }
.toast-close {
  background: none; border: none; color: inherit; cursor: pointer;
  opacity: .8; font-size: .8rem; padding: 2px;
}
.toast-close:hover { opacity: 1; }
.toast-success { background: #089e62; }
.toast-error   { background: #b93200; }
.toast-info    { background: #3b3b46; }
@keyframes toast-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
</style>

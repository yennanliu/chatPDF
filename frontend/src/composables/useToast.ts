// Tiny global toast store (§3.2). Shared singleton state so any component can
// push a toast and a single <ToastHost> renders them.
import { ref } from 'vue'

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
}

const toasts = ref<Toast[]>([])
let _seq = 0

function push(kind: ToastKind, message: string, ttlMs = 4000): void {
  const id = ++_seq
  toasts.value.push({ id, kind, message })
  if (ttlMs > 0) setTimeout(() => dismiss(id), ttlMs)
}

function dismiss(id: number): void {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

export function useToast() {
  return {
    toasts,
    dismiss,
    success: (m: string) => push('success', m),
    error: (m: string) => push('error', m, 6000),
    info: (m: string) => push('info', m),
  }
}

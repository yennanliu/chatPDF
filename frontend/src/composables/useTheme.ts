// Dark/light theme toggle (§3.5). Persists to localStorage and reflects the
// choice as data-theme on <html>, which main.css keys its variables off.
import { ref } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'chatpdf-theme'
const theme = ref<Theme>('light')

function apply(t: Theme): void {
  theme.value = t
  document.documentElement.setAttribute('data-theme', t)
  try { localStorage.setItem(STORAGE_KEY, t) } catch { /* ignore */ }
}

export function initTheme(): void {
  let saved: Theme | null = null
  try { saved = localStorage.getItem(STORAGE_KEY) as Theme | null } catch { /* ignore */ }
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  apply(saved ?? (prefersDark ? 'dark' : 'light'))
}

export function useTheme() {
  return {
    theme,
    toggle: () => apply(theme.value === 'dark' ? 'light' : 'dark'),
  }
}

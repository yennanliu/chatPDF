<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView, RouterLink, useRoute } from 'vue-router'
import ToastHost from '@/components/ToastHost.vue'
import { useTheme, initTheme } from '@/composables/useTheme'
import { API_BASE } from '@/lib/api'

const route   = useRoute()
const navOpen = ref(false)
const { theme, toggle: toggleTheme } = useTheme()

const docsUrl = `${API_BASE}/docs`

onMounted(initTheme)

function closeNav() { navOpen.value = false }
</script>

<template>
  <div class="layout">
    <!-- Mobile top bar ───────────────────────────────────────────────────────── -->
    <div class="mobile-bar">
      <button class="hamburger" :aria-expanded="navOpen" @click="navOpen = !navOpen">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <line v-if="!navOpen" x1="3" y1="6" x2="21" y2="6" />
          <line v-if="!navOpen" x1="3" y1="12" x2="21" y2="12" />
          <line v-if="!navOpen" x1="3" y1="18" x2="21" y2="18" />
          <line v-if="navOpen" x1="18" y1="6" x2="6" y2="18" />
          <line v-if="navOpen" x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
      <div class="mobile-brand">
        <div class="brand-mark-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>
        <span class="mobile-title">ChatPDF</span>
      </div>
    </div>

    <!-- Nav backdrop (mobile) ────────────────────────────────────────────────── -->
    <div v-if="navOpen" class="nav-backdrop" @click="closeNav" />

    <!-- Sidebar ──────────────────────────────────────────────────────────────── -->
    <aside class="sidebar" :class="{ open: navOpen }">
      <div class="sidebar-brand">
        <div class="brand-mark">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </div>
        <span class="brand-text">ChatPDF</span>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          to="/"
          :class="['nav-item', 'nav-docs', route.path === '/' ? 'active' : '']"
          @click="closeNav"
        >
          <span class="nav-icon nav-icon-orange">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </span>
          Documents
        </RouterLink>

        <RouterLink
          to="/chat"
          :class="['nav-item', 'nav-chat', route.path.startsWith('/chat') ? 'active' : '']"
          @click="closeNav"
        >
          <span class="nav-icon nav-icon-purple">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </span>
          Chat
        </RouterLink>

        <RouterLink
          to="/eval"
          :class="['nav-item', 'nav-eval', route.path.startsWith('/eval') ? 'active' : '']"
          @click="closeNav"
        >
          <span class="nav-icon nav-icon-blue">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
          </span>
          Evaluation
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <a :href="docsUrl" target="_blank" class="sidebar-link">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          API Docs
        </a>
        <button class="sidebar-link theme-toggle" :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'" @click="toggleTheme">
          <svg v-if="theme === 'dark'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
          <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
          {{ theme === 'dark' ? 'Light mode' : 'Dark mode' }}
        </button>
      </div>
    </aside>

    <!-- Main content ─────────────────────────────────────────────────────────── -->
    <main class="main-content">
      <RouterView />
    </main>

    <ToastHost />
  </div>
</template>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────────── */
.layout { display: flex; min-height: 100vh; }

/* ── Sidebar ─────────────────────────────────────────────────────────────────── */
.sidebar {
  width: 232px; flex-shrink: 0;
  background: var(--bg);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
}

.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 18px 14px;
}

.brand-mark {
  width: 34px; height: 34px; flex-shrink: 0;
  background: var(--brand-purple);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 4px 12px rgba(162,89,255,.3);
}

.brand-text {
  font-size: 1.05rem; font-weight: 700;
  color: var(--text); letter-spacing: -.02em;
}

/* ── Nav ─────────────────────────────────────────────────────────────────────── */
.sidebar-nav {
  flex: 1; padding: 8px 10px;
  display: flex; flex-direction: column; gap: 2px;
}

.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: 10px;
  color: var(--text-muted); text-decoration: none;
  font-size: .875rem; font-weight: 500;
  transition: background .15s, color .15s;
}
.nav-item:hover { background: var(--bg-alt); color: var(--text); }

.nav-item.active { font-weight: 600; }
.nav-docs.active  { background: rgba(242,78,30,.08);  color: var(--brand-orange); }
.nav-libs.active  { background: rgba(10,207,131,.08); color: #089e62; }
.nav-chat.active  { background: rgba(162,89,255,.1);  color: var(--brand-purple); }
.nav-eval.active  { background: rgba(26,188,254,.1);  color: #0b7fb0; }

/* Nav icon pill */
.nav-icon {
  width: 26px; height: 26px; flex-shrink: 0;
  border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s;
}
.nav-icon-orange { background: rgba(242,78,30,.1);   color: var(--brand-orange); }
.nav-icon-green  { background: rgba(10,207,131,.1);  color: var(--brand-green); }
.nav-icon-purple { background: rgba(162,89,255,.1);  color: var(--brand-purple); }
.nav-icon-blue   { background: rgba(26,188,254,.1);  color: var(--brand-blue); }

/* ── Sidebar footer ──────────────────────────────────────────────────────────── */
.sidebar-footer {
  padding: 14px 18px;
  border-top: 1px solid var(--border);
}
.sidebar-link {
  display: flex; align-items: center; gap: 7px;
  color: var(--text-muted); text-decoration: none;
  font-size: .8rem; font-weight: 500;
  transition: color .15s;
}
.sidebar-link:hover { color: var(--text); }
.theme-toggle {
  width: 100%; margin-top: 10px;
  background: none; border: none; cursor: pointer;
  font-family: inherit; font-size: .8rem; font-weight: 500;
  padding: 0;
}

/* ── Main content ────────────────────────────────────────────────────────────── */
.main-content { flex: 1; min-width: 0; overflow-y: auto; }

/* ── Mobile elements (hidden on desktop) ─────────────────────────────────────── */
.mobile-bar   { display: none; }
.nav-backdrop { display: none; }

/* ── Responsive ≤ 768 px ─────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .layout { flex-direction: column; }

  .mobile-bar {
    display: flex; align-items: center; gap: 12px;
    height: 54px; padding: 0 16px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 60; flex-shrink: 0;
  }
  .hamburger {
    background: none; border: none; cursor: pointer;
    color: var(--text-muted); padding: 4px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
  }
  .hamburger:hover { background: var(--bg-alt); color: var(--text); }

  .mobile-brand { display: flex; align-items: center; gap: 8px; }
  .brand-mark-sm {
    width: 26px; height: 26px;
    background: var(--brand-purple); border-radius: 7px;
    display: flex; align-items: center; justify-content: center;
    color: #fff;
  }
  .mobile-title { font-size: .95rem; font-weight: 700; color: var(--text); }

  .sidebar {
    position: fixed; top: 0; left: 0; bottom: 0; z-index: 70;
    transform: translateX(-100%);
    transition: transform .25s ease;
    box-shadow: 4px 0 32px rgba(15,15,20,.12);
  }
  .sidebar.open { transform: translateX(0); }

  .nav-backdrop {
    display: block; position: fixed; inset: 0; z-index: 65;
    background: rgba(15,15,20,.35);
    backdrop-filter: blur(2px);
  }

  .main-content { min-height: calc(100vh - 54px); overflow-y: auto; }
}
</style>

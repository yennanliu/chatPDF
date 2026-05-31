<script setup lang="ts">
import { ref } from 'vue'
import { RouterView, RouterLink, useRoute } from 'vue-router'

const route   = useRoute()
const navOpen = ref(false)

function closeNav() { navOpen.value = false }
</script>

<template>
  <div class="layout">
    <!-- Mobile top bar ──────────────────────────────────────────────────────── -->
    <div class="mobile-bar">
      <button class="hamburger" :aria-expanded="navOpen" @click="navOpen = !navOpen">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <line v-if="!navOpen" x1="3" y1="6" x2="21" y2="6"/>
          <line v-if="!navOpen" x1="3" y1="12" x2="21" y2="12"/>
          <line v-if="!navOpen" x1="3" y1="18" x2="21" y2="18"/>
          <line v-if="navOpen" x1="18" y1="6" x2="6" y2="18"/>
          <line v-if="navOpen" x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
      <span class="mobile-title">📄 ChatPDF</span>
    </div>

    <!-- Nav backdrop (mobile) ───────────────────────────────────────────────── -->
    <div v-if="navOpen" class="nav-backdrop" @click="closeNav" />

    <!-- Sidebar nav ─────────────────────────────────────────────────────────── -->
    <aside class="sidebar" :class="{ open: navOpen }">
      <div class="sidebar-brand">
        <span class="brand-icon">📄</span>
        <span class="brand-text">ChatPDF</span>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          to="/"
          :class="['nav-item', route.path === '/' ? 'active' : '']"
          @click="closeNav"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          Documents
        </RouterLink>
        <RouterLink
          to="/libraries"
          :class="['nav-item', route.path.startsWith('/libraries') ? 'active' : '']"
          @click="closeNav"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          Libraries
        </RouterLink>
        <RouterLink
          to="/chat"
          :class="['nav-item', route.path.startsWith('/chat') ? 'active' : '']"
          @click="closeNav"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          Chat
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <a href="http://localhost:8000/docs" target="_blank" class="sidebar-link">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          API Docs
        </a>
      </div>
    </aside>

    <!-- Main content ────────────────────────────────────────────────────────── -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
/* ── Base layout ─────────────────────────────────────────────────────────────── */
.layout { display: flex; min-height: 100vh; }

/* ── Sidebar ─────────────────────────────────────────────────────────────────── */
.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
}

.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 18px 16px;
  border-bottom: 1px solid rgba(255,255,255,.08);
}
.brand-icon { font-size: 1.4rem; }
.brand-text { font-size: 1.1rem; font-weight: 700; color: #f8fafc; }

.sidebar-nav {
  flex: 1; padding: 12px 8px;
  display: flex; flex-direction: column; gap: 2px;
}

.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 12px; border-radius: 6px;
  color: #94a3b8; text-decoration: none;
  font-size: 0.9rem; font-weight: 500;
  transition: background .15s, color .15s;
}
.nav-item:hover  { background: rgba(255,255,255,.08); color: #e2e8f0; }
.nav-item.active { background: var(--clr-primary); color: #fff; }
.nav-item svg    { flex-shrink: 0; }

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,.08);
}
.sidebar-link {
  display: flex; align-items: center; gap: 6px;
  color: #64748b; text-decoration: none; font-size: 0.8rem;
  transition: color .15s;
}
.sidebar-link:hover { color: #94a3b8; }

/* ── Main content ────────────────────────────────────────────────────────────── */
.main-content { flex: 1; min-width: 0; overflow-y: auto; }

/* ── Mobile elements (hidden on desktop) ─────────────────────────────────────── */
.mobile-bar  { display: none; }
.nav-backdrop { display: none; }

/* ── Responsive: ≤ 768 px ────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .layout { flex-direction: column; }

  /* Top bar */
  .mobile-bar {
    display: flex; align-items: center; gap: 12px;
    height: 52px; padding: 0 16px;
    background: var(--bg-sidebar);
    position: sticky; top: 0; z-index: 60;
    flex-shrink: 0;
  }
  .hamburger {
    background: none; border: none; cursor: pointer;
    color: #94a3b8; padding: 4px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
  }
  .hamburger:hover { color: #f1f5f9; }
  .mobile-title { font-size: 1rem; font-weight: 700; color: #f8fafc; }

  /* Sidebar becomes a slide-in drawer */
  .sidebar {
    position: fixed; top: 0; left: 0; bottom: 0;
    z-index: 70;
    transform: translateX(-100%);
    transition: transform .25s ease;
    box-shadow: 4px 0 24px rgba(0,0,0,.3);
  }
  .sidebar.open { transform: translateX(0); }

  /* Backdrop */
  .nav-backdrop {
    display: block;
    position: fixed; inset: 0; z-index: 65;
    background: rgba(0,0,0,.45);
  }

  .main-content { min-height: calc(100vh - 52px); overflow-y: auto; }
}
</style>

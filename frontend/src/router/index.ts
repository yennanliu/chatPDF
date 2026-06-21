import { createRouter, createWebHistory } from 'vue-router'
import DocumentsView from '@/views/DocumentsView.vue'
import ChatView from '@/views/ChatView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/',          component: DocumentsView },
    { path: '/chat',      component: ChatView },
    { path: '/chat/:sessionId', component: ChatView },
  ],
})

export default router

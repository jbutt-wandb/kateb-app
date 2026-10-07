import { createRouter, createWebHistory } from 'vue-router'
import UploadView from '../views/UploadView.vue'
import EditorView from '../views/EditorView.vue'
import CompareView from '../views/CompareView.vue'

const routes = [
  {
    path: '/',
    name: 'upload',
    component: UploadView
  },
  {
    path: '/editor',
    name: 'editor',
    component: EditorView
  },
  {
    path: '/compare',
    name: 'compare',
    component: CompareView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

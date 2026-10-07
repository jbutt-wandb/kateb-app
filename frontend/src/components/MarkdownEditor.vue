<script setup>
import { ref, computed, watch } from 'vue'
import { marked } from 'marked'
import katex from 'katex'

const props = defineProps({
  results: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['update'])

const editableContent = ref([])
const showPreview = ref([])

watch(() => props.results, (newResults) => {
  editableContent.value = newResults.map(r => r.markdown)
  showPreview.value = newResults.map(() => false)
}, { immediate: true })

function updateMarkdown(index, value) {
  editableContent.value[index] = value
  emit('update', index, value)
}

function togglePreview(index) {
  showPreview.value[index] = !showPreview.value[index]
}

function renderLatex(text) {
  if (!text) return ''

  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, latex) => {
    try {
      return katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="text-red-400">${match}</span>`
    }
  })

  result = result.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (match, latex) => {
    try {
      return katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span class="text-red-400">${match}</span>`
    }
  })

  return result
}

function renderMarkdown(content) {
  if (!content) return ''
  const withLatex = renderLatex(content)
  return marked.parse(withLatex)
}

const renderedContent = computed(() => {
  return editableContent.value.map(content => renderMarkdown(content))
})
</script>

<template>
  <div class="h-full overflow-y-auto p-3 space-y-3">
    <div
      v-for="(result, index) in props.results"
      :key="index"
      class="rounded-md overflow-hidden border border-dark-border"
    >
      <!-- Section header -->
      <div class="px-3 py-1.5 bg-dark-bg border-b border-dark-border flex items-center justify-between">
        <span class="text-xs text-dark-text-muted">
          {{ result.filename || `Section ${index + 1}` }}
        </span>
        <button
          @click="togglePreview(index)"
          class="flex items-center gap-1 px-2 py-0.5 text-xs rounded transition-colors"
          :class="showPreview[index]
            ? 'bg-accent/20 text-accent'
            : 'text-dark-text-muted hover:text-dark-text-secondary hover:bg-white/5'"
        >
          <svg v-if="showPreview[index]" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
          </svg>
          <span>Preview</span>
        </button>
      </div>

      <!-- Editor -->
      <div class="p-3">
        <textarea
          :value="editableContent[index]"
          @input="updateMarkdown(index, $event.target.value)"
          class="w-full h-72 p-3 bg-dark-bg border border-dark-border rounded-md font-mono text-sm text-dark-text-primary resize-none focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent placeholder-dark-text-muted"
          placeholder="Markdown content..."
        />
      </div>

      <!-- Preview (conditional) -->
      <div
        v-if="showPreview[index]"
        class="p-3 border-t border-dark-border"
      >
        <div
          class="prose prose-sm prose-invert max-w-none max-h-80 overflow-y-auto p-3 bg-dark-bg border border-dark-border rounded-md"
          v-html="renderedContent[index]"
        />
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="props.results.length === 0"
      class="h-full flex items-center justify-center text-dark-text-muted"
    >
      <p class="text-sm">No content to edit</p>
    </div>
  </div>
</template>

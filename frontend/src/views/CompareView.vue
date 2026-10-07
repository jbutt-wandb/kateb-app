<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import katex from 'katex'

import { useNotesStore } from '../stores/notes'
import { useConfigStore } from '../stores/config'
import { processCompare, saveConfig } from '../services/api'

const router = useRouter()
const notesStore = useNotesStore()
const configStore = useConfigStore()

const sourceImage = ref(null)              // { id, file, preview, filename } from notesStore
const showPicker = ref(false)
const isRunning = ref(false)
const results = ref([])                    // [{ model_id, model_label, markdown, error }]
const topLevelError = ref(null)
const viewMode = ref('preview')            // 'editor' | 'preview' — synced across both panes
const selectedModelIds = ref([])
const lightboxOpen = ref(false)

function handleLightboxKey(e) {
  if (e.key === 'Escape' && lightboxOpen.value) {
    lightboxOpen.value = false
  }
}

const availableModels = computed(() => configStore.status?.available_models || {})
const availableEntries = computed(() => Object.entries(availableModels.value))
const hasResults = computed(() => results.value.length > 0)
const canRun = computed(() => selectedModelIds.value.length === 2)
const selectedLabels = computed(() =>
  selectedModelIds.value.map(id => availableModels.value[id] || id)
)

function toggleModel(modelId) {
  const idx = selectedModelIds.value.indexOf(modelId)
  if (idx >= 0) {
    selectedModelIds.value.splice(idx, 1)
    return
  }
  if (selectedModelIds.value.length >= 2) return
  selectedModelIds.value.push(modelId)
}

function isSelected(modelId) {
  return selectedModelIds.value.includes(modelId)
}

function isDisabledForSelection(modelId) {
  return !isSelected(modelId) && selectedModelIds.value.length >= 2
}

function renderLatex(text) {
  if (!text) return ''
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, latex) => {
    try {
      return katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span style="color: #f87171;">${match}</span>`
    }
  })
  result = result.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (match, latex) => {
    try {
      return katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span style="color: #f87171;">${match}</span>`
    }
  })
  return result
}

function renderedFor(markdown) {
  if (!markdown) return ''
  return marked.parse(renderLatex(markdown))
}

async function runComparison() {
  if (!canRun.value) return
  showPicker.value = false
  isRunning.value = true
  topLevelError.value = null
  results.value = []

  try {
    const data = await processCompare(
      { file: sourceImage.value.file },
      {
        containsLatex: notesStore.options.containsLatex,
        containsDiagrams: notesStore.options.containsDiagrams,
        customInstructions: notesStore.customInstructions,
        modelIds: selectedModelIds.value
      }
    )
    results.value = data.results || []
  } catch (err) {
    topLevelError.value = err.message || 'Comparison failed'
  } finally {
    isRunning.value = false
  }
}

onMounted(() => {
  const img = notesStore.images?.[0]
  if (!img) {
    router.replace('/')
    return
  }
  sourceImage.value = img
  showPicker.value = true
  document.addEventListener('keydown', handleLightboxKey)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleLightboxKey)
})

function cancelPicker() {
  showPicker.value = false
  router.push('/')
}

async function useThisModel(result) {
  if (!result || !result.markdown) return

  try {
    await saveConfig({ model: result.model_id })
    if (configStore.fetchStatus) {
      try { await configStore.fetchStatus() } catch (_) { /* ignore */ }
    }

    notesStore.setImages([sourceImage.value])
    notesStore.setResults([
      {
        filename: sourceImage.value.filename,
        markdown: result.markdown,
        preview: sourceImage.value.preview
      }
    ])

    router.push('/editor')
  } catch (err) {
    topLevelError.value = err.message || 'Could not switch to that model'
  }
}

function backToUpload() {
  router.push('/')
}
</script>

<template>
  <div>
    <!-- Loading overlay -->
    <div
      v-if="isRunning"
      style="position: fixed; inset: 0; background-color: rgba(0, 0, 0, 0.75); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 9999;"
    >
      <svg style="width: 48px; height: 48px; color: var(--color-accent); animation: spin 1s linear infinite;" fill="none" viewBox="0 0 24 24">
        <circle style="opacity: 0.25;" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
        <path style="opacity: 0.75;" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p style="margin-top: 16px; font-size: 18px; font-weight: 500; color: var(--color-text-primary);">
        Running 2 models on this image…
      </p>
      <p style="margin-top: 6px; font-size: 13px; color: var(--color-text-muted);">
        {{ selectedLabels.join(' · ') }}
      </p>
    </div>

    <!-- Model picker modal -->
    <div
      v-if="showPicker"
      style="position: fixed; inset: 0; background-color: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; z-index: 10000; padding: 24px;"
      @click.self="cancelPicker"
    >
      <div
        style="background-color: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; max-width: 520px; width: 100%; padding: 28px;"
      >
        <h2 style="font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0 0 8px 0;">
          Pick two models to compare
        </h2>
        <p style="font-size: 14px; color: var(--color-text-muted); line-height: 1.55; margin: 0 0 18px 0;">
          We'll call both selected models on this image in parallel. Expect roughly
          2× the W&amp;B Inference cost and wall-clock latency of a normal OCR run.
        </p>

        <div v-if="availableEntries.length === 0" style="padding: 12px; border-radius: 8px; font-size: 14px; background-color: rgba(239, 68, 68, 0.1); color: #f87171; margin-bottom: 18px;">
          No available models found. Make sure your W&amp;B credentials are configured.
        </div>

        <div v-else style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px;">
          <label
            v-for="[modelId, modelLabel] in availableEntries"
            :key="modelId"
            :style="{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 14px',
              border: '1px solid ' + (isSelected(modelId) ? 'var(--color-accent)' : 'var(--color-border)'),
              borderRadius: '8px',
              cursor: isDisabledForSelection(modelId) ? 'not-allowed' : 'pointer',
              opacity: isDisabledForSelection(modelId) ? '0.45' : '1',
              backgroundColor: isSelected(modelId) ? 'rgba(99, 102, 241, 0.08)' : 'transparent'
            }"
          >
            <input
              type="checkbox"
              :checked="isSelected(modelId)"
              :disabled="isDisabledForSelection(modelId)"
              @change="toggleModel(modelId)"
              style="width: 16px; height: 16px; accent-color: var(--color-accent); cursor: inherit;"
            />
            <div style="display: flex; flex-direction: column; gap: 2px;">
              <span style="font-size: 14px; font-weight: 500; color: var(--color-text-primary);">{{ modelLabel }}</span>
              <span style="font-size: 12px; color: var(--color-text-muted); font-family: ui-monospace, monospace;">{{ modelId }}</span>
            </div>
          </label>
        </div>

        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
          <p style="font-size: 12px; color: var(--color-text-muted); margin: 0;">
            {{ selectedModelIds.length }} / 2 selected
          </p>
          <div style="display: flex; gap: 10px;">
            <button
              @click="cancelPicker"
              style="padding: 10px 16px; font-size: 14px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
            >
              Cancel
            </button>
            <button
              @click="runComparison"
              :disabled="!canRun"
              :style="{
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '500',
                color: 'white',
                backgroundColor: 'var(--color-accent)',
                border: 'none',
                borderRadius: '6px',
                cursor: canRun ? 'pointer' : 'not-allowed',
                opacity: canRun ? '1' : '0.5'
              }"
            >
              Run comparison
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Result view -->
    <div v-if="hasResults" style="max-width: 1600px; margin: 0 auto; padding: 32px 24px;">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px;">
        <button
          @click="backToUpload"
          style="padding: 8px 14px; font-size: 13px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
        >
          ← Back to upload
        </button>

        <!-- Synced view-mode toggle -->
        <div style="display: inline-flex; background-color: var(--color-bg); border: 1px solid var(--color-border); border-radius: 8px; padding: 2px;">
          <button
            @click="viewMode = 'editor'"
            :style="{
              padding: '6px 16px',
              fontSize: '13px',
              fontWeight: '500',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              backgroundColor: viewMode === 'editor' ? 'var(--color-accent)' : 'transparent',
              color: viewMode === 'editor' ? 'white' : 'var(--color-text-muted)'
            }"
          >Editor</button>
          <button
            @click="viewMode = 'preview'"
            :style="{
              padding: '6px 16px',
              fontSize: '13px',
              fontWeight: '500',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              backgroundColor: viewMode === 'preview' ? 'var(--color-accent)' : 'transparent',
              color: viewMode === 'preview' ? 'white' : 'var(--color-text-muted)'
            }"
          >Preview</button>
        </div>
      </div>

      <!-- Tripartite grid: image | model A | model B -->
      <div style="display: grid; grid-template-columns: 1fr 1.4fr 1.4fr; gap: 20px; align-items: start;">
        <!-- Image (sticky) -->
        <div style="position: sticky; top: 24px;">
          <div style="background-color: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 16px;">
            <p style="font-size: 13px; color: var(--color-text-muted); margin: 0 0 10px 0;">
              {{ sourceImage?.filename }}
            </p>
            <img
              :src="sourceImage?.preview"
              :alt="sourceImage?.filename"
              @click="lightboxOpen = true"
              style="width: 100%; max-height: 75vh; object-fit: contain; border-radius: 8px; cursor: zoom-in;"
            />
          </div>
        </div>

        <!-- One pane per result -->
        <div
          v-for="(result, idx) in results"
          :key="result.model_id || idx"
          style="background-color: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; display: flex; flex-direction: column; min-height: 60vh;"
        >
          <div style="padding: 14px 18px; border-bottom: 1px solid var(--color-border);">
            <div style="font-size: 12px; color: var(--color-text-muted); letter-spacing: 0.05em; text-transform: uppercase;">
              Model {{ idx === 0 ? 'A' : 'B' }}
            </div>
            <div style="font-size: 18px; font-weight: 600; color: var(--color-text-primary); margin-top: 2px;">
              {{ result.model_label }}
            </div>
          </div>

          <div style="padding: 20px; flex: 1; overflow-y: auto; max-height: 70vh;">
            <div
              v-if="result.error"
              style="padding: 14px; border-radius: 8px; font-size: 14px; background-color: rgba(239, 68, 68, 0.1); color: #f87171; white-space: pre-wrap;"
            >
              <strong>{{ result.model_label }} failed:</strong>
              <br />
              {{ result.error }}
            </div>
            <textarea
              v-else-if="viewMode === 'editor'"
              v-model="results[idx].markdown"
              spellcheck="false"
              style="width: 100%; min-height: 60vh; padding: 12px; font-size: 14px; font-family: ui-monospace, monospace; line-height: 1.55; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 8px; resize: vertical; outline: none; box-sizing: border-box;"
            ></textarea>
            <div
              v-else
              class="markdown-preview"
              style="font-size: 15px; line-height: 1.65; color: var(--color-text-primary);"
              v-html="renderedFor(result.markdown)"
            ></div>
          </div>

          <div style="padding: 14px 18px; border-top: 1px solid var(--color-border); display: flex; justify-content: flex-end;">
            <button
              @click="useThisModel(result)"
              :disabled="!result.markdown"
              :style="{
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '500',
                color: 'white',
                backgroundColor: 'var(--color-accent)',
                border: 'none',
                borderRadius: '8px',
                cursor: result.markdown ? 'pointer' : 'not-allowed',
                opacity: result.markdown ? '1' : '0.5'
              }"
            >
              Use {{ result.model_label }} →
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="topLevelError"
        style="margin-top: 16px; padding: 12px; border-radius: 8px; font-size: 14px; background-color: rgba(239, 68, 68, 0.1); color: #f87171; white-space: pre-wrap;"
      >
        {{ topLevelError }}
      </div>
    </div>

    <!-- Lightbox overlay -->
    <div
      v-if="lightboxOpen"
      @click="lightboxOpen = false"
      style="position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; z-index: 10000; cursor: zoom-out; padding: 24px;"
    >
      <img
        :src="sourceImage?.preview"
        :alt="sourceImage?.filename"
        style="max-width: 95vw; max-height: 95vh; object-fit: contain; border-radius: 4px;"
      />
    </div>

    <!-- Pre-results error fallback (e.g. comparison API failed) -->
    <div
      v-else-if="!showPicker && !isRunning && topLevelError"
      style="max-width: 600px; margin: 80px auto; padding: 24px; text-align: center;"
    >
      <p style="padding: 12px; border-radius: 8px; font-size: 14px; background-color: rgba(239, 68, 68, 0.1); color: #f87171; white-space: pre-wrap; margin-bottom: 16px;">
        {{ topLevelError }}
      </p>
      <button
        @click="backToUpload"
        style="padding: 10px 16px; font-size: 14px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
      >
        ← Back to upload
      </button>
    </div>
  </div>
</template>

<style>
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.markdown-preview h1 { font-size: 22px; font-weight: 700; margin: 18px 0 10px; }
.markdown-preview h2 { font-size: 19px; font-weight: 700; margin: 16px 0 8px; }
.markdown-preview h3 { font-size: 17px; font-weight: 600; margin: 14px 0 8px; }
.markdown-preview p { margin: 8px 0; }
.markdown-preview ul, .markdown-preview ol { margin: 8px 0; padding-left: 22px; }
.markdown-preview li { margin: 4px 0; }
.markdown-preview code { background: var(--color-bg); padding: 2px 5px; border-radius: 4px; font-family: ui-monospace, monospace; font-size: 13px; }
.markdown-preview pre { background: var(--color-bg); padding: 12px; border-radius: 8px; overflow-x: auto; }
.markdown-preview blockquote { border-left: 3px solid var(--color-accent); padding-left: 12px; color: var(--color-text-muted); margin: 12px 0; }
</style>

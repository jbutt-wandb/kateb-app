<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useNotesStore } from '../stores/notes'
import { useConfigStore } from '../stores/config'
import { processSingleImage } from '../services/api'
import draggable from 'vuedraggable'
import DropZone from '../components/DropZone.vue'
import ImagePreview from '../components/ImagePreview.vue'

const router = useRouter()
const notesStore = useNotesStore()
const configStore = useConfigStore()
const showNoImagesMessage = ref(false)
const showCustomInstructions = ref(false)
const isDev = import.meta.env.DEV
const compareError = ref(null)

function handleCompareClick() {
  compareError.value = null
  const count = notesStore.images.length
  if (count === 0) {
    compareError.value = 'Upload an image first, then compare models.'
    return
  }
  if (count > 1) {
    compareError.value = 'Comparison only works on a single image. Remove the others or run them through the standard converter.'
    return
  }
  router.push('/compare')
}

function handleFilesSelected(files) {
  notesStore.addImages(files)
  showNoImagesMessage.value = false
}

function handleRemoveImage(id) {
  notesStore.removeImage(id)
}

async function handleSubmit() {
  if (notesStore.images.length === 0) {
    showNoImagesMessage.value = true
    return
  }

  notesStore.setProcessing(true)
  notesStore.setError(null)

  const options = {
    ...notesStore.options,
    customInstructions: notesStore.customInstructions
  }

  try {
    const promises = notesStore.images.map((image, index) =>
      processSingleImage(image, options)
        .then(response => ({ status: 'fulfilled', value: response, image, index }))
        .catch(error => ({ status: 'rejected', reason: error, image, index }))
    )

    const results = await Promise.all(promises)
    const allResults = []
    const failures = []

    results.forEach((result) => {
      if (result.status === 'fulfilled') {
        allResults.push({
          ...result.value,
          preview: result.image.preview
        })
      } else {
        const filename = result.image.filename || `Image ${result.index + 1}`
        const errMsg = result.reason?.message || 'Unknown error'
        failures.push({ filename, errMsg })
      }
    })

    if (failures.length > 0) {
      const grouped = new Map()
      for (const { filename, errMsg } of failures) {
        if (!grouped.has(errMsg)) grouped.set(errMsg, [])
        grouped.get(errMsg).push(filename)
      }
      const summary = [...grouped.entries()].map(([msg, files]) => `${files.join(', ')}: ${msg}`).join('\n')
      notesStore.setError(summary)
    }

    if (allResults.length === 0) return

    notesStore.setResults(allResults)
    router.push('/editor')
  } catch (err) {
    notesStore.setError(err.message || 'An unexpected error occurred')
  } finally {
    notesStore.setProcessing(false)
  }
}

function loadTestData() {
  notesStore.loadTestData()
  router.push('/editor')
}

const optSelected = ref({ latex: false, diagrams: false, custom: false })

function toggleOpt(key, storeKey) {
  optSelected.value[key] = !optSelected.value[key]
  if (storeKey) notesStore.options[storeKey] = optSelected.value[key]
  if (key === 'custom') showCustomInstructions.value = optSelected.value[key]
}
</script>

<template>
  <div>
    <!-- Processing Overlay -->
    <div
      v-if="notesStore.isProcessing"
      style="position: fixed; inset: 0; background: rgba(250,250,247,0.92); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 9999;"
    >
      <svg style="width: 36px; height: 36px; color: #C47A1A; animation: spin 1s linear infinite;" fill="none" viewBox="0 0 24 24">
        <circle style="opacity: 0.2;" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"></circle>
        <path style="opacity: 0.8;" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p style="margin-top: 20px; font-family: 'EB Garamond', serif; font-size: 20px; font-style: italic; color: #555;">
        Processing {{ notesStore.images.length }} image{{ notesStore.images.length > 1 ? 's' : '' }}…
      </p>
    </div>

    <!-- Main Content -->
    <div style="max-width: 720px; margin: 0 auto; padding: 36px 40px 48px;">

      <!-- Headline -->
      <div style="margin-bottom: 28px;">
        <h2 style="font-family: 'EB Garamond', serif; font-size: 27px; font-weight: 400; line-height: 1.25; color: #1a1a1a; margin: 0;">
          Your handwriting,<br><em>rendered in type.</em>
        </h2>
      </div>

      <!-- Drop Zone -->
      <div v-if="notesStore.canAddMore()" style="margin-bottom: 18px;">
        <DropZone @files-selected="handleFilesSelected" />
      </div>
      <div
        v-else
        style="margin-bottom: 18px; padding: 14px 16px; border: 0.5px solid #ddd; font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 300; color: #999; text-align: center;"
      >
        Maximum of {{ notesStore.getMaxImages() }} images reached — remove one to add more.
      </div>

      <!-- File chips / image previews -->
      <div v-if="notesStore.images.length > 0" style="margin-bottom: 22px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
          <span style="font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 300; color: #999;">
            {{ notesStore.images.length }}/{{ notesStore.getMaxImages() }} images
          </span>
          <button
            @click="notesStore.clearImages()"
            style="font-family: 'Crimson Pro', serif; font-size: 13px; font-style: italic; color: #999; background: transparent; border: none; cursor: pointer; padding: 0; transition: color 0.15s;"
            @mouseenter="$event.target.style.color='#1a1a1a'"
            @mouseleave="$event.target.style.color='#999'"
          >
            clear all
          </button>
        </div>
        <draggable
          :model-value="notesStore.images"
          @update:model-value="notesStore.setImages"
          item-key="id"
          handle=".drag-handle"
          :animation="200"
          ghost-class="drag-ghost"
          style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;"
        >
          <template #item="{ element }">
            <ImagePreview :image="element" @remove="handleRemoveImage" />
          </template>
        </draggable>
      </div>

      <!-- Options -->
      <div style="display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 8px; margin-bottom: 22px;">

        <!-- LaTeX -->
        <div
          class="opt-card"
          :class="{ selected: optSelected.latex }"
          @click="toggleOpt('latex', 'containsLatex')"
        >
          <div class="opt-bar" style="background: #A3382A;"></div>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <i class="ti ti-math-function" style="font-size: 13px;" :style="{ color: optSelected.latex ? '#A3382A' : '#666' }" aria-hidden="true"></i>
            <div :style="{ width: '10px', height: '10px', border: '0.5px solid', borderColor: optSelected.latex ? '#A3382A' : '#666', background: optSelected.latex ? '#A3382A' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
              <i v-if="optSelected.latex" class="ti ti-check" style="font-size: 7px; color: #FAFAF7;"></i>
            </div>
          </div>
          <div style="font-size: 11.5px; font-weight: 300; line-height: 1.3;" :style="{ color: optSelected.latex ? '#444' : '#555' }">LaTeX equations</div>
        </div>

        <!-- Diagrams -->
        <div
          class="opt-card"
          :class="{ selected: optSelected.diagrams }"
          @click="toggleOpt('diagrams', 'containsDiagrams')"
        >
          <div class="opt-bar" style="background: #2A6496;"></div>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <i class="ti ti-chart-dots" style="font-size: 13px;" :style="{ color: optSelected.diagrams ? '#2A6496' : '#666' }" aria-hidden="true"></i>
            <div :style="{ width: '10px', height: '10px', border: '0.5px solid', borderColor: optSelected.diagrams ? '#2A6496' : '#666', background: optSelected.diagrams ? '#2A6496' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
              <i v-if="optSelected.diagrams" class="ti ti-check" style="font-size: 7px; color: #FAFAF7;"></i>
            </div>
          </div>
          <div style="font-size: 11.5px; font-weight: 300; line-height: 1.3;" :style="{ color: optSelected.diagrams ? '#444' : '#555' }">Graphs & diagrams</div>
        </div>

        <!-- Custom instructions -->
        <div
          class="opt-card"
          :class="{ selected: optSelected.custom }"
          @click="toggleOpt('custom')"
        >
          <div class="opt-bar" style="background: #3D7A6E;"></div>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <i class="ti ti-adjustments-horizontal" style="font-size: 13px;" :style="{ color: optSelected.custom ? '#3D7A6E' : '#666' }" aria-hidden="true"></i>
            <div :style="{ width: '10px', height: '10px', border: '0.5px solid', borderColor: optSelected.custom ? '#3D7A6E' : '#666', background: optSelected.custom ? '#3D7A6E' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
              <i v-if="optSelected.custom" class="ti ti-check" style="font-size: 7px; color: #FAFAF7;"></i>
            </div>
          </div>
          <div style="font-size: 11.5px; font-weight: 300; line-height: 1.3;" :style="{ color: optSelected.custom ? '#444' : '#555' }">Custom instructions</div>
        </div>
      </div>

      <!-- Custom instructions textarea -->
      <div v-show="showCustomInstructions" style="margin-bottom: 22px;">
        <textarea
          v-model="notesStore.customInstructions"
          placeholder="e.g., Focus on mathematical equations, preserve table formatting…"
          style="width: 100%; min-height: 72px; padding: 10px 12px; font-size: 14px; font-family: 'Crimson Pro', serif; line-height: 1.5; background: #FAFAF7; color: #1a1a1a; border: 0.5px solid #ccc; resize: vertical; outline: none;"
        ></textarea>
      </div>

      <!-- Action row -->
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <button
          class="btn-likho-primary"
          @click="handleSubmit"
          :disabled="notesStore.isProcessing || !configStore.inferenceReady"
        >
          <i class="ti ti-wand" aria-hidden="true"></i>
          Convert to markdown
        </button>
        <button
          class="btn-likho-ghost"
          @click="handleCompareClick"
          :disabled="!configStore.inferenceReady"
          :title="!configStore.inferenceReady ? 'Configure W&B credentials first' : 'Pick two models and compare their OCR on a single image'"
          style="justify-content: center;"
        >
          <i class="ti ti-scale" aria-hidden="true"></i>
          Compare models
        </button>
      </div>

      <!-- Credential hint -->
      <div v-if="!configStore.inferenceReady" style="margin-top: 10px; font-size: 13px; font-style: italic; color: #bbb;">
        Add your W&amp;B API key via the
        <button
          type="button"
          @click="configStore.openModal('edit')"
          style="background: transparent; border: none; padding: 0; color: #888; cursor: pointer; font-size: 13px; font-style: italic; text-decoration: underline; font-family: 'Crimson Pro', serif;"
        >settings</button>
        to enable conversion.
      </div>

      <!-- Validation messages -->
      <div
        v-if="showNoImagesMessage"
        style="margin-top: 14px; padding: 10px 14px; border-left: 2px solid #A3382A; font-size: 14px; font-style: italic; color: #A3382A; background: rgba(163,56,42,0.05);"
      >
        Upload at least one image before converting.
      </div>

      <div
        v-if="compareError"
        style="margin-top: 14px; padding: 10px 14px; border-left: 2px solid #A3382A; font-size: 14px; font-style: italic; color: #A3382A; background: rgba(163,56,42,0.05);"
      >
        {{ compareError }}
      </div>

      <div
        v-if="notesStore.error"
        style="margin-top: 14px; padding: 10px 14px; border-left: 2px solid #A3382A; font-size: 14px; font-style: italic; color: #A3382A; background: rgba(163,56,42,0.05); white-space: pre-wrap;"
      >
        {{ notesStore.error }}
      </div>

      <!-- Dev Mode -->
      <div v-if="isDev" style="margin-top: 32px; padding-top: 20px; border-top: 0.5px dashed #ccc;">
        <button
          @click="loadTestData"
          style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 300; padding: 8px 16px; background: transparent; border: 0.5px solid #C47A1A; color: #C47A1A; cursor: pointer;"
        >
          preview
        </button>
      </div>

    </div>
  </div>
</template>

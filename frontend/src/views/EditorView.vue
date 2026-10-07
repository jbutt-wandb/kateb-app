<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useNotesStore } from '../stores/notes'
import { marked } from 'marked'
import katex from 'katex'
import DropZone from '../components/DropZone.vue'
import CropModal from '../components/CropModal.vue'
import DownloadModal from '../components/DownloadModal.vue'
import { processSingleImage, captureDatasetRows } from '../services/api'

const router = useRouter()
const notesStore = useNotesStore()
const viewMode = ref('editor')
const documentTitle = ref('Untitled Document')
const scrollRef = ref(null)
const sectionRefs = []
const lightboxIndex = ref(null)
const originalOcrSnapshot = ref([])
const imageHeights = ref({})
let imageObserver = null

function recordImageHeight(img) {
  if (!img) return
  const i = parseInt(img.dataset.sectionImage, 10)
  if (Number.isNaN(i)) return
  const h = img.clientHeight
  if (h > 0) imageHeights.value[i] = h
}

function onImageLoad(i, e) {
  recordImageHeight(e.target)
  if (imageObserver) imageObserver.observe(e.target)
}

function remeasureImages() {
  document.querySelectorAll('img[data-section-image]').forEach((img) => {
    if (img.complete) recordImageHeight(img)
  })
}

function setSectionRef(i, el) {
  if (el) sectionRefs[i] = el
}

function autosize(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

function scrollRatio(el) {
  const range = el.scrollHeight - el.clientHeight
  return range > 0 ? el.scrollTop / range : 0
}

function applyScrollRatio(el, ratio) {
  const range = el.scrollHeight - el.clientHeight
  el.scrollTop = Math.max(0, Math.min(1, ratio)) * range
}

function setViewMode(mode) {
  if (mode === viewMode.value) return
  const ratio = scrollRef.value ? scrollRatio(scrollRef.value) : 0
  viewMode.value = mode
  nextTick(() => {
    if (scrollRef.value) applyScrollRatio(scrollRef.value, ratio)
    if (mode === 'editor') {
      sectionRefs.forEach(autosize)
    }
  })
}

// Crop Modal state
const showCropModal = ref(false)
const cursorState = ref({ index: 0, position: 0 })

// Download Modal state
const showDownloadModal = ref(false)

function onTextareaSelect(i, e) {
  cursorState.value = { index: i, position: e.target.selectionStart }
}

function openCropModal() {
  // Default cursor to end of first textarea if nothing tracked yet
  const ta = sectionRefs[0]
  if (ta && cursorState.value.position === 0 && cursorState.value.index === 0) {
    cursorState.value = { index: 0, position: ta.value.length }
  }
  showCropModal.value = true
}

function handleInsertAtCursor({ refMarkdown }) {
  const { index, position } = cursorState.value
  const current = notesStore.results[index]?.markdown ?? ''
  const safePos = Math.min(Math.max(0, position), current.length)
  const before = current.slice(0, safePos)
  const after = current.slice(safePos)
  // Pad with newlines if not already on a blank line, so the image renders as a block.
  const needsLeadingNl = before.length > 0 && !before.endsWith('\n')
  const prefix = needsLeadingNl ? '\n\n' : ''
  const suffix = after.startsWith('\n') ? '' : '\n'
  const inserted = prefix + refMarkdown + suffix
  notesStore.updateMarkdown(index, before + inserted + after)
  cursorState.value = { index, position: safePos + inserted.length }
  nextTick(() => {
    const ta = sectionRefs[index]
    if (ta) {
      autosize(ta)
    }
  })
}

// Add Image Modal state
const showAddModal = ref(false)
const addImages = ref([])
const addOptions = ref({
  containsLatex: false,
  containsDiagrams: false,
  customInstructions: ''
})
const isAddProcessing = ref(false)
const addError = ref(null)

function onGlobalKeydown(e) {
  if (e.key === 'Escape' && lightboxIndex.value !== null) {
    lightboxIndex.value = null
  }
}

onMounted(() => {
  if (notesStore.results.length === 0) {
    router.push('/')
    return
  }
  originalOcrSnapshot.value = notesStore.results.map(r => r.markdown)
  document.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('resize', remeasureImages)

  if (typeof ResizeObserver !== 'undefined') {
    imageObserver = new ResizeObserver((entries) => {
      for (const entry of entries) recordImageHeight(entry.target)
    })
  }

  nextTick(() => {
    document.querySelectorAll('img[data-section-image]').forEach((img) => {
      if (imageObserver) imageObserver.observe(img)
      if (img.complete) recordImageHeight(img)
    })
    sectionRefs.forEach(autosize)
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('resize', remeasureImages)
  if (imageObserver) {
    imageObserver.disconnect()
    imageObserver = null
  }
})

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

function renderedSection(i) {
  const md = notesStore.results[i]?.markdown || ''
  if (!md) return ''
  return marked.parse(renderLatex(notesStore.resolveCropsForPreview(md)))
}

function onSectionInput(i, e) {
  notesStore.updateMarkdown(i, e.target.value)
  autosize(e.target)
}

function onSectionKeydown(i, e) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const textarea = e.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = textarea.value
    const newValue = value.substring(0, start) + '  ' + value.substring(end)
    notesStore.updateMarkdown(i, newValue)
    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = start + 2
      autosize(textarea)
    })
    return
  }

  if (e.key === 'ArrowDown') {
    const textarea = e.target
    const cursor = textarea.selectionStart
    if (textarea.value.indexOf('\n', cursor) === -1) {
      const next = sectionRefs[i + 1]
      if (next) {
        e.preventDefault()
        next.focus()
        next.selectionStart = next.selectionEnd = 0
        next.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    }
  } else if (e.key === 'ArrowUp') {
    const textarea = e.target
    const cursor = textarea.selectionStart
    if (textarea.value.lastIndexOf('\n', cursor - 1) === -1) {
      const prev = sectionRefs[i - 1]
      if (prev) {
        e.preventDefault()
        prev.focus()
        prev.selectionStart = prev.selectionEnd = prev.value.length
        prev.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    }
  }
}

function openLightbox(i) {
  lightboxIndex.value = i
}

function openDownloadModal() {
  showDownloadModal.value = true
}

function onDownloadConfirm({ sendToDataset }) {
  showDownloadModal.value = false
  performDownload(sendToDataset)
}

function performDownload(sendToDataset) {
  if (sendToDataset) {
    // Dataset rows use the stripped markdown — no image tags reach the fine-tune set.
    const rows = notesStore.results.map((r, i) => ({
      row_id: crypto.randomUUID(),
      image_filename: r.filename,
      image_base64: (r.preview || '').split(',')[1] || '',
      markdown: notesStore.stripImageTagsForDataset(r.markdown),
      original_ocr: originalOcrSnapshot.value[i] ?? '',
      options: {
        contains_latex: notesStore.options.containsLatex,
        contains_diagrams: notesStore.options.containsDiagrams,
        custom_instructions: notesStore.customInstructions || ''
      },
      document_title: documentTitle.value
    }))
    captureDatasetRows(rows)
  }

  const combined = notesStore.results.map(r => notesStore.resolveCropsForDownload(r.markdown)).join('\n\n')
  const blob = new Blob([combined], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)

  const filename = documentTitle.value.trim().replace(/[^a-zA-Z0-9-_ ]/g, '').replace(/\s+/g, '_') || 'notes'

  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.md`
  link.click()

  URL.revokeObjectURL(url)
}

function goBack() {
  router.push('/')
}

// Add Image Modal functions
const ADD_MAX_IMAGES = 5

async function handleAddFiles(files) {
  const remaining = ADD_MAX_IMAGES - addImages.value.length
  if (remaining <= 0) {
    addError.value = `You can only upload ${ADD_MAX_IMAGES} images at a time. Process this batch, then add more.`
    return
  }
  const toAdd = files.slice(0, remaining)
  const dropped = files.length - toAdd.length

  const entries = await Promise.all(
    toAdd.map(file => new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => resolve({
        id: crypto.randomUUID(),
        file,
        preview: e.target.result,
        filename: file.name
      })
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(file)
    }))
  )
  addImages.value.push(...entries)

  if (dropped > 0) {
    addError.value = `Limit is ${ADD_MAX_IMAGES} per batch — skipped ${dropped} ${dropped === 1 ? 'file' : 'files'}.`
  } else {
    addError.value = null
  }
}

function removeAddImage(id) {
  addImages.value = addImages.value.filter(img => img.id !== id)
}

async function processAddImages() {
  if (addImages.value.length === 0) return

  isAddProcessing.value = true
  addError.value = null

  try {
    for (const image of addImages.value) {
      const response = await processSingleImage(image, {
        containsLatex: addOptions.value.containsLatex,
        containsDiagrams: addOptions.value.containsDiagrams,
        customInstructions: addOptions.value.customInstructions
      })

      const newResult = {
        ...response,
        preview: image.preview
      }
      notesStore.results.push(newResult)
      originalOcrSnapshot.value.push(newResult.markdown)
    }

    showAddModal.value = false
    addImages.value = []
    addOptions.value = { containsLatex: false, containsDiagrams: false, customInstructions: '' }

    await nextTick()
    document.querySelectorAll('img[data-section-image]').forEach((img) => {
      if (imageObserver) imageObserver.observe(img)
      if (img.complete) recordImageHeight(img)
    })
    sectionRefs.forEach(autosize)
  } catch (err) {
    addError.value = err.message
  } finally {
    isAddProcessing.value = false
  }
}

function closeAddModal() {
  showAddModal.value = false
  addImages.value = []
  addError.value = null
}
</script>

<template>
  <div style="height: calc(100vh - 61px); display: flex; flex-direction: column;">
    <!-- Toolbar -->
    <div style="padding: 12px 24px; background-color: var(--color-surface); border-bottom: 1px solid var(--color-border); display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; gap: 8px;">
        <button
          @click="goBack"
          style="padding: 8px 16px; font-size: 14px; border-radius: 6px; background: transparent; border: 1px solid var(--color-border); cursor: pointer; color: var(--color-text-primary);"
          @mouseenter="$event.target.style.backgroundColor = 'var(--color-surface-hover)'"
          @mouseleave="$event.target.style.backgroundColor = 'transparent'"
        >
          Back
        </button>
        <button
          @click="showAddModal = true"
          style="padding: 8px 16px; font-size: 14px; border-radius: 6px; background: transparent; border: 1px solid var(--color-border); cursor: pointer; color: var(--color-text-primary);"
          @mouseenter="$event.target.style.backgroundColor = 'var(--color-surface-hover)'"
          @mouseleave="$event.target.style.backgroundColor = 'transparent'"
        >
          Add Image
        </button>
        <button
          v-if="notesStore.results.length >= 1"
          @click="openCropModal"
          style="padding: 8px 16px; font-size: 14px; border-radius: 6px; background: transparent; border: 1px solid var(--color-border); cursor: pointer; color: var(--color-text-primary); display: flex; align-items: center; gap: 6px;"
          @mouseenter="$event.target.style.backgroundColor = 'var(--color-surface-hover)'"
          @mouseleave="$event.target.style.backgroundColor = 'transparent'"
          title="Crop diagrams from the source image and embed them in the markdown"
        >
          <svg style="width: 16px; height: 16px;" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 2v14a2 2 0 002 2h14M2 6h14a2 2 0 012 2v14" />
          </svg>
          Add Diagrams
        </button>
      </div>

      <div style="display: flex; align-items: center; gap: 4px; background-color: var(--color-bg); border-radius: 8px; padding: 4px;">
        <button
          @click="setViewMode('editor')"
          :style="{
            padding: '8px 16px',
            fontSize: '14px',
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            backgroundColor: viewMode === 'editor' ? 'var(--color-accent)' : 'transparent',
            color: viewMode === 'editor' ? 'white' : 'var(--color-text-muted)'
          }"
        >
          Editor
        </button>
        <button
          @click="setViewMode('preview')"
          :style="{
            padding: '8px 16px',
            fontSize: '14px',
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            backgroundColor: viewMode === 'preview' ? 'var(--color-accent)' : 'transparent',
            color: viewMode === 'preview' ? 'white' : 'var(--color-text-muted)'
          }"
        >
          Preview
        </button>
      </div>
    </div>

    <!-- Main scrollable content -->
    <div ref="scrollRef" style="flex: 1; overflow-y: auto;">
      <div style="max-width: 1700px; margin: 0 auto; padding: 16px 24px 96px;">
        <!-- Document Title -->
        <div style="margin-bottom: 20px;">
          <label style="display: block; font-size: 12px; font-weight: 500; color: var(--color-text-muted); margin-bottom: 6px;">
            Document Title
          </label>
          <input
            v-model="documentTitle"
            type="text"
            placeholder="Enter document title..."
            style="width: 100%; padding: 10px 14px; font-size: 16px; font-weight: 500; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 8px; outline: none; box-sizing: border-box;"
          />
        </div>

        <!-- Sections (one per image) -->
        <section
          v-for="(result, i) in notesStore.results"
          :key="result.filename + '-' + i"
          style="display: flex; gap: 20px; margin-bottom: 16px; align-items: stretch;"
        >
          <!-- Gutter: sticky thumbnail -->
          <div style="width: 560px; flex-shrink: 0;">
            <div style="position: sticky; top: 16px;">
              <img
                :src="result.preview"
                :alt="result.filename"
                :title="result.filename"
                :data-section-image="i"
                @click="openLightbox(i)"
                @load="onImageLoad(i, $event)"
                style="width: 100%; height: auto; max-height: 85vh; object-fit: contain; cursor: zoom-in; border-radius: 6px; border: 1px solid var(--color-border); display: block; transition: opacity 150ms;"
              />
            </div>
          </div>

          <!-- Body: textarea (editor) or rendered HTML (preview) -->
          <div style="flex: 1; min-width: 0;">
            <textarea
              v-show="viewMode === 'editor'"
              :ref="(el) => setSectionRef(i, el)"
              :value="result.markdown"
              @input="onSectionInput(i, $event)"
              @keydown="onSectionKeydown(i, $event)"
              @select="onTextareaSelect(i, $event)"
              @click="onTextareaSelect(i, $event)"
              @keyup="onTextareaSelect(i, $event)"
              spellcheck="false"
              placeholder="Edit OCR text..."
              :style="{ minHeight: imageHeights[i] ? imageHeights[i] + 'px' : '75vh' }"
              style="width: 100%; padding: 12px 14px; font-family: ui-monospace, monospace; font-size: 14px; line-height: 1.6; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 8px; resize: none; outline: none; box-sizing: border-box; overflow: hidden;"
            ></textarea>
            <div
              v-show="viewMode === 'preview'"
              class="markdown-preview"
              v-html="renderedSection(i)"
              :style="{ minHeight: imageHeights[i] ? imageHeights[i] + 'px' : '75vh' }"
              style="padding: 12px 16px; background-color: var(--color-bg); border: 1px solid var(--color-border); border-radius: 8px; color: var(--color-text-primary); line-height: 1.65;"
            ></div>
          </div>
        </section>
      </div>
    </div>

    <!-- Download button (bottom right) -->
    <button
      @click="openDownloadModal"
      style="position: fixed; bottom: 24px; right: 24px; padding: 12px 24px; font-size: 15px; font-weight: 500; color: white; background-color: var(--color-accent); border: none; border-radius: 24px; cursor: pointer; display: flex; align-items: center; gap: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
      @mouseenter="$event.target.style.backgroundColor = 'var(--color-accent-hover)'"
      @mouseleave="$event.target.style.backgroundColor = 'var(--color-accent)'"
    >
      <svg style="width: 18px; height: 18px;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      Download
    </button>

    <!-- Crop Modal -->
    <CropModal
      v-if="showCropModal && notesStore.results.length > 0"
      :pages="notesStore.results"
      :initial-index="cursorState.index"
      @close="showCropModal = false"
      @insert-at-cursor="handleInsertAtCursor"
    />

    <!-- Download Modal -->
    <DownloadModal
      :show="showDownloadModal"
      @confirm="onDownloadConfirm"
      @close="showDownloadModal = false"
    />

    <!-- Lightbox overlay -->
    <Teleport to="body">
      <div
        v-if="lightboxIndex !== null"
        @click="lightboxIndex = null"
        style="position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; z-index: 10000; cursor: zoom-out; padding: 24px;"
      >
        <img
          :src="notesStore.results[lightboxIndex].preview"
          :alt="notesStore.results[lightboxIndex].filename"
          style="max-width: 95vw; max-height: 95vh; object-fit: contain; border-radius: 4px;"
        />
      </div>
    </Teleport>

    <!-- Add Image Modal -->
    <Teleport to="body">
    <div
      v-if="showAddModal"
      style="position: fixed; inset: 0; background: rgba(0,0,0,0.75); display: flex; align-items: center; justify-content: center; z-index: 9999;"
    >
      <div style="background: var(--color-surface); border-radius: 12px; padding: 24px; width: 500px; max-height: 80vh; overflow-y: auto;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
          <h3 style="margin: 0; font-size: 18px; font-weight: 600; color: var(--color-text-primary);">Add More Images</h3>
          <button
            @click="closeAddModal"
            style="background: none; border: none; cursor: pointer; color: var(--color-text-muted); font-size: 20px;"
          >&times;</button>
        </div>

        <!-- Drop Zone (hidden at capacity) -->
        <div v-if="addImages.length < 5" style="margin-bottom: 16px;">
          <DropZone @files-selected="handleAddFiles" />
        </div>
        <div
          v-else
          style="margin-bottom: 16px; padding: 12px; border-radius: 8px; text-align: center; background-color: var(--color-bg); border: 1px solid var(--color-border);"
        >
          <p style="margin: 0; font-size: 13px; color: var(--color-text-muted);">
            Maximum of 5 images reached. Remove one to add more.
          </p>
        </div>

        <!-- Preview added images -->
        <div v-if="addImages.length > 0" style="margin-bottom: 16px;">
          <p style="font-size: 14px; color: var(--color-text-muted); margin-bottom: 8px;">
            {{ addImages.length }}/5 selected
          </p>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            <div
              v-for="img in addImages"
              :key="img.id"
              style="position: relative; width: 80px; height: 80px; border-radius: 6px; overflow: hidden; border: 1px solid var(--color-border);"
            >
              <img :src="img.preview" style="width: 100%; height: 100%; object-fit: cover;" />
              <button
                @click="removeAddImage(img.id)"
                style="position: absolute; top: 2px; right: 2px; width: 20px; height: 20px; border-radius: 50%; background: rgba(0,0,0,0.6); border: none; color: white; cursor: pointer; font-size: 12px;"
              >&times;</button>
            </div>
          </div>
        </div>

        <!-- Options -->
        <div style="margin-bottom: 16px;">
          <div style="display: flex; gap: 16px; margin-bottom: 12px;">
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" v-model="addOptions.containsLatex" style="width: 16px; height: 16px; accent-color: #8b5cf6;" />
              <span style="font-size: 14px; color: var(--color-text-primary);">LaTeX equations</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" v-model="addOptions.containsDiagrams" style="width: 16px; height: 16px; accent-color: #8b5cf6;" />
              <span style="font-size: 14px; color: var(--color-text-primary);">Diagrams</span>
            </label>
          </div>
          <textarea
            v-model="addOptions.customInstructions"
            placeholder="Custom instructions (optional)..."
            style="width: 100%; min-height: 60px; padding: 10px; font-size: 14px; font-family: inherit; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 6px; resize: vertical; outline: none;"
          ></textarea>
        </div>

        <!-- Error -->
        <div
          v-if="addError"
          style="margin-bottom: 16px; padding: 10px; border-radius: 6px; background-color: rgba(239, 68, 68, 0.1); color: #f87171; font-size: 14px;"
        >
          {{ addError }}
        </div>

        <!-- Buttons -->
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <button
            @click="closeAddModal"
            style="padding: 8px 16px; font-size: 14px; border-radius: 6px; background: transparent; border: 1px solid var(--color-border); cursor: pointer; color: var(--color-text-primary);"
          >
            Cancel
          </button>
          <button
            @click="processAddImages"
            :disabled="isAddProcessing || addImages.length === 0"
            :style="{
              padding: '8px 16px',
              fontSize: '14px',
              borderRadius: '6px',
              border: 'none',
              cursor: isAddProcessing || addImages.length === 0 ? 'not-allowed' : 'pointer',
              backgroundColor: 'var(--color-accent)',
              color: 'white',
              opacity: isAddProcessing || addImages.length === 0 ? '0.5' : '1'
            }"
          >
            {{ isAddProcessing ? 'Processing...' : 'Process' }}
          </button>
        </div>
      </div>
    </div>
    </Teleport>
  </div>
</template>

<style>
.markdown-preview h1,
.markdown-preview h2,
.markdown-preview h3,
.markdown-preview h4,
.markdown-preview h5,
.markdown-preview h6 {
  color: var(--color-text-primary);
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-weight: 600;
}
.markdown-preview h1 { font-size: 2em; font-weight: 700; border-bottom: 1px solid var(--color-border); padding-bottom: 0.3em; }
.markdown-preview h2 { font-size: 1.5em; border-bottom: 1px solid var(--color-border); padding-bottom: 0.2em; }
.markdown-preview h3 { font-size: 1.25em; }
.markdown-preview h4 { font-size: 1.05em; }
.markdown-preview p { margin: 0.75em 0; }
.markdown-preview ul,
.markdown-preview ol { margin: 0.75em 0; padding-left: 1.5em; }
.markdown-preview li { margin: 0.25em 0; }
.markdown-preview li > ul,
.markdown-preview li > ol { margin: 0.25em 0; }
.markdown-preview a { color: var(--color-accent); text-decoration: underline; }
.markdown-preview a:hover { color: var(--color-accent-hover); }
.markdown-preview strong { color: var(--color-text-primary); font-weight: 700; }
.markdown-preview em { font-style: italic; }
.markdown-preview code {
  background-color: var(--color-surface);
  color: var(--color-text-primary);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.markdown-preview pre {
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 1em 0;
}
.markdown-preview pre code {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 0.875em;
}
.markdown-preview blockquote {
  margin: 1em 0;
  padding: 0.25em 1em;
  color: var(--color-text-secondary);
  border-left: 3px solid var(--color-accent);
  background-color: var(--color-surface);
  border-radius: 0 6px 6px 0;
}
.markdown-preview hr {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 2em 0;
}
.markdown-preview table {
  border-collapse: collapse;
  margin: 1em 0;
  width: 100%;
  font-size: 0.95em;
  display: block;
  overflow-x: auto;
}
.markdown-preview th,
.markdown-preview td {
  border: 1px solid var(--color-border);
  padding: 8px 12px;
  text-align: left;
  vertical-align: top;
}
.markdown-preview th {
  background-color: var(--color-surface);
  font-weight: 600;
  color: var(--color-text-primary);
}
.markdown-preview tr:nth-child(even) td {
  background-color: rgba(255, 255, 255, 0.02);
}
.light .markdown-preview tr:nth-child(even) td {
  background-color: rgba(0, 0, 0, 0.02);
}
.markdown-preview img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
}
</style>

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sampleMarkdown, sampleImage, sampleFilename } from '../fixtures/testData'

const MAX_IMAGES = 5

export const useNotesStore = defineStore('notes', () => {
  const images = ref([])
  const options = ref({
    containsLatex: false,
    containsDiagrams: false
  })
  const customInstructions = ref('')
  const results = ref([])
  const isProcessing = ref(false)
  const currentImageIndex = ref(0)
  const error = ref(null)
  const crops = ref({})

  const combinedMarkdown = computed(() => {
    return results.value
      .map(r => r.markdown)
      .join('\n\n---\n\n')
  })

  async function addImages(files) {
    const remainingSlots = MAX_IMAGES - images.value.length
    const filesToAdd = files.slice(0, remainingSlots)

    const entries = await Promise.all(
      filesToAdd.map(file => new Promise((resolve, reject) => {
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

    const available = MAX_IMAGES - images.value.length
    images.value.push(...entries.slice(0, available))

    return files.length > remainingSlots
  }

  function setImages(newOrder) {
    images.value = newOrder
  }

  function canAddMore() {
    return images.value.length < MAX_IMAGES
  }

  function getMaxImages() {
    return MAX_IMAGES
  }

  function removeImage(id) {
    images.value = images.value.filter(img => img.id !== id)
  }

  function clearImages() {
    images.value = []
  }

  function updateMarkdown(index, markdown) {
    if (results.value[index]) {
      results.value[index].markdown = markdown
    }
  }

  function setResults(newResults) {
    results.value = newResults
  }

  function setProcessing(value) {
    isProcessing.value = value
    if (!value) {
      currentImageIndex.value = 0
    }
  }

  function setCurrentImageIndex(index) {
    currentImageIndex.value = index
  }

  function setError(value) {
    error.value = value
  }

  function reset() {
    images.value = []
    results.value = []
    error.value = null
    options.value = {
      containsLatex: false,
      containsDiagrams: false
    }
    customInstructions.value = ''
    crops.value = {}
  }

  function addCrop({ label, dataUrl, sourceIndex, bbox, width, height, aspectLock }) {
    const id = 'c_' + Math.random().toString(36).slice(2, 8)
    crops.value[id] = { id, label, dataUrl, sourceIndex, bbox, width, height, aspectLock }
    return id
  }

  function removeCrop(id) {
    delete crops.value[id]
    // Scrub any orphan ![…](crop:<id>) refs from every result's markdown so the editor doesn't show a broken ref.
    const re = new RegExp(`!\\[[^\\]]*\\]\\(crop:${id}\\)`, 'g')
    results.value.forEach((r, i) => {
      if (!r.markdown) return
      const stripped = r.markdown
        .replace(re, '')
        .replace(/[ \t]+$/gm, '')
        .replace(/\n{3,}/g, '\n\n')
      if (stripped !== r.markdown) updateMarkdown(i, stripped)
    })
  }

  function countCropRefs(id) {
    const re = new RegExp(`!\\[[^\\]]*\\]\\(crop:${id}\\)`, 'g')
    let total = 0
    for (const r of results.value) {
      total += (r.markdown || '').match(re)?.length ?? 0
    }
    return total
  }

  function renameCrop(id, label) {
    if (crops.value[id]) crops.value[id].label = label
  }

  // Matches ![alt](crop:<id>) with optional |W or |WxH size hint embedded in alt.
  // Alt may not contain '|'. Capture groups: alt, width, height, id.
  const CROP_REF_RE = /!\[([^\]|]*)(?:\|(\d+)(?:x(\d+))?)?\]\(crop:([a-zA-Z0-9_]+)\)/g

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
  }

  // Preview: missing refs pass through unchanged; sized refs emit raw HTML <img> so width/height stick.
  function resolveCropsForPreview(md) {
    if (!md) return md
    return md.replace(CROP_REF_RE, (match, alt, wStr, hStr, id) => {
      const crop = crops.value[id]
      if (!crop) return match
      const w = parseInt(wStr, 10)
      const h = parseInt(hStr, 10)
      if (w > 0) {
        const heightStyle = h > 0 ? `height:${h}px` : 'height:auto'
        return `<img src="${crop.dataUrl}" alt="${escapeHtml(alt)}" style="width:${w}px;${heightStyle};max-width:100%;" />`
      }
      return `![${alt}](${crop.dataUrl})`
    })
  }

  // Download: preserve |W or |WxH inside alt so Obsidian-style viewers still respect sizing; inline the data URL.
  function resolveCropsForDownload(md) {
    if (!md) return md
    return md.replace(CROP_REF_RE, (match, alt, wStr, hStr, id) => {
      const crop = crops.value[id]
      if (!crop) return match
      const sizeSuffix = wStr ? (hStr ? `|${wStr}x${hStr}` : `|${wStr}`) : ''
      return `![${alt}${sizeSuffix}](${crop.dataUrl})`
    })
  }

  // Dataset capture must be pure text — strip all inline image tags and tidy blank lines.
  function stripImageTagsForDataset(md) {
    if (!md) return md
    return md
      .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
      .replace(/[ \t]+$/gm, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  }

  function loadTestData() {
    results.value = [{
      filename: sampleFilename,
      markdown: sampleMarkdown,
      preview: sampleImage
    }]
  }

  return {
    images,
    options,
    customInstructions,
    results,
    isProcessing,
    currentImageIndex,
    error,
    crops,
    combinedMarkdown,
    addImages,
    setImages,
    removeImage,
    clearImages,
    updateMarkdown,
    setResults,
    setProcessing,
    setCurrentImageIndex,
    setError,
    reset,
    canAddMore,
    getMaxImages,
    loadTestData,
    addCrop,
    removeCrop,
    renameCrop,
    countCropRefs,
    resolveCropsForPreview,
    resolveCropsForDownload,
    stripImageTagsForDataset
  }
})

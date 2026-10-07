<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useNotesStore } from '../stores/notes'

const props = defineProps({
  pages: { type: Array, required: true },
  initialIndex: { type: Number, default: 0 }
})

const emit = defineEmits(['close', 'insert-at-cursor'])

const notesStore = useNotesStore()

const canvasRef = ref(null)
const sourceImgEl = ref(null)
const drawing = ref(false)
const startPoint = ref(null)
const currentBox = ref(null)
const selectedCropId = ref(null)
const imageReady = ref(false)
const currentIndex = ref(Math.min(Math.max(props.initialIndex || 0, 0), Math.max(props.pages.length - 1, 0)))

const sourceCrops = computed(() =>
  Object.values(notesStore.crops).filter(c => c.sourceIndex === currentIndex.value)
)

function getCanvasCoords(e) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY
  }
}

function normalizeBox(box) {
  return {
    x: Math.min(box.x, box.x + box.w),
    y: Math.min(box.y, box.y + box.h),
    w: Math.abs(box.w),
    h: Math.abs(box.h)
  }
}

function redraw() {
  const canvas = canvasRef.value
  const img = sourceImgEl.value
  if (!canvas || !img || !imageReady.value) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(img, 0, 0)

  for (const c of sourceCrops.value) {
    const isSelected = c.id === selectedCropId.value
    ctx.strokeStyle = isSelected ? '#f59e0b' : '#16a34a'
    ctx.lineWidth = Math.max(2, canvas.width / 400)
    ctx.strokeRect(c.bbox.x, c.bbox.y, c.bbox.w, c.bbox.h)

    const fontSize = Math.max(14, canvas.width / 60)
    ctx.font = `bold ${fontSize}px sans-serif`
    const labelText = c.label
    const padding = fontSize * 0.3
    const textWidth = ctx.measureText(labelText).width
    ctx.fillStyle = isSelected ? '#f59e0b' : '#16a34a'
    ctx.fillRect(c.bbox.x, c.bbox.y, textWidth + padding * 2, fontSize + padding * 2)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(labelText, c.bbox.x + padding, c.bbox.y + fontSize + padding * 0.6)
  }

  if (drawing.value && currentBox.value) {
    const b = normalizeBox(currentBox.value)
    ctx.strokeStyle = '#2563eb'
    ctx.setLineDash([8, 6])
    ctx.lineWidth = Math.max(2, canvas.width / 400)
    ctx.strokeRect(b.x, b.y, b.w, b.h)
    ctx.setLineDash([])
  }
}

function commitBox(rawBox) {
  const box = normalizeBox(rawBox)
  if (box.w < 8 || box.h < 8) return

  const img = sourceImgEl.value
  const off = document.createElement('canvas')
  off.width = Math.round(box.w)
  off.height = Math.round(box.h)
  const octx = off.getContext('2d')
  octx.drawImage(img, box.x, box.y, box.w, box.h, 0, 0, off.width, off.height)
  const dataUrl = off.toDataURL('image/png')

  const label = `diagram-${sourceCrops.value.length + 1}`
  const defaultW = Math.min(Math.round(box.w), 480)
  const defaultH = Math.round(defaultW * box.h / box.w)
  const id = notesStore.addCrop({
    label,
    dataUrl,
    sourceIndex: currentIndex.value,
    bbox: { x: box.x, y: box.y, w: box.w, h: box.h },
    width: defaultW,
    height: defaultH,
    aspectLock: true
  })
  emit('insert-at-cursor', { refMarkdown: `![${label}|${defaultW}](crop:${id})` })
}

function onMouseDown(e) {
  if (e.button !== 0) return
  const c = getCanvasCoords(e)
  drawing.value = true
  startPoint.value = c
  currentBox.value = { x: c.x, y: c.y, w: 0, h: 0 }
  selectedCropId.value = null
  redraw()
}

function onMouseMove(e) {
  if (!drawing.value) return
  const c = getCanvasCoords(e)
  currentBox.value = {
    x: startPoint.value.x,
    y: startPoint.value.y,
    w: c.x - startPoint.value.x,
    h: c.y - startPoint.value.y
  }
  redraw()
}

function onMouseUp() {
  if (!drawing.value) return
  drawing.value = false
  if (currentBox.value) commitBox(currentBox.value)
  currentBox.value = null
  redraw()
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (drawing.value) {
      drawing.value = false
      currentBox.value = null
      redraw()
    } else {
      emit('close')
    }
  }
}

function selectCrop(id) {
  selectedCropId.value = selectedCropId.value === id ? null : id
  redraw()
}

function deleteCrop(id) {
  const refs = notesStore.countCropRefs(id)
  if (refs > 0) {
    const label = notesStore.crops[id]?.label || 'this crop'
    const where = refs === 1 ? 'one place' : `${refs} places`
    if (!window.confirm(`"${label}" is referenced in ${where} in your notes. Delete the crop and remove those references?`)) return
  }
  notesStore.removeCrop(id)
  if (selectedCropId.value === id) selectedCropId.value = null
  redraw()
}

function insertCrop(crop) {
  const w = crop.width
  const h = crop.height
  let sizeSuffix = ''
  if (w > 0) {
    sizeSuffix = crop.aspectLock ? `|${w}` : `|${w}x${h}`
  }
  emit('insert-at-cursor', { refMarkdown: `![${crop.label}${sizeSuffix}](crop:${crop.id})` })
}

function onLabelInput(crop, e) {
  notesStore.renameCrop(crop.id, e.target.value)
  redraw()
}

function onWidthInput(crop, e) {
  const w = parseInt(e.target.value, 10)
  if (!Number.isFinite(w) || w < 1) return
  crop.width = w
  if (crop.aspectLock && crop.bbox.w > 0) {
    crop.height = Math.max(1, Math.round(w * crop.bbox.h / crop.bbox.w))
  }
}

function onHeightInput(crop, e) {
  const h = parseInt(e.target.value, 10)
  if (!Number.isFinite(h) || h < 1) return
  crop.height = h
}

function toggleAspectLock(crop) {
  crop.aspectLock = !crop.aspectLock
  if (crop.aspectLock && crop.bbox.w > 0) {
    crop.height = Math.max(1, Math.round(crop.width * crop.bbox.h / crop.bbox.w))
  }
}

function loadPage(idx) {
  const page = props.pages[idx]
  if (!page) return
  imageReady.value = false
  const img = new Image()
  img.onload = () => {
    const canvas = canvasRef.value
    if (!canvas) return
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    sourceImgEl.value = img
    imageReady.value = true
    nextTick(redraw)
  }
  img.src = page.preview
}

function switchPage(idx) {
  if (idx === currentIndex.value) return
  // Cancel any in-flight draw so it can't span pages.
  if (drawing.value) {
    drawing.value = false
    currentBox.value = null
    startPoint.value = null
  }
  selectedCropId.value = null
  currentIndex.value = idx
}

watch(sourceCrops, () => nextTick(redraw), { deep: true })
watch(currentIndex, (idx) => loadPage(idx))

onMounted(() => {
  loadPage(currentIndex.value)
  window.addEventListener('mouseup', onMouseUp)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('mouseup', onMouseUp)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
  <div
    @click.self="emit('close')"
    style="position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 10001; padding: 24px;"
  >
    <div style="background: var(--color-surface); border-radius: 12px; width: min(1400px, 95vw); height: min(900px, 92vh); display: flex; overflow: hidden; border: 1px solid var(--color-border);">
      <!-- Left: canvas pane -->
      <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--color-bg);">
        <div style="padding: 14px 18px; border-bottom: 1px solid var(--color-border); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: var(--color-text-primary);">Crop diagrams</h3>
            <p style="margin: 4px 0 0; font-size: 12px; color: var(--color-text-muted);">Click and drag to draw a rectangle around each diagram you want to embed.</p>
          </div>
          <button
            @click="emit('close')"
            style="background: none; border: none; cursor: pointer; color: var(--color-text-muted); font-size: 22px; line-height: 1; padding: 4px 10px; border-radius: 6px;"
            @mouseenter="$event.target.style.backgroundColor = 'var(--color-surface-hover)'"
            @mouseleave="$event.target.style.backgroundColor = 'transparent'"
          >&times;</button>
        </div>
        <div
          v-if="pages.length > 1"
          style="display: flex; gap: 6px; padding: 10px 18px; border-bottom: 1px solid var(--color-border); background: var(--color-surface);"
        >
          <button
            v-for="(p, i) in pages"
            :key="i"
            @click="switchPage(i)"
            :style="{
              padding: '6px 14px',
              fontSize: '13px',
              fontWeight: i === currentIndex ? 600 : 500,
              borderRadius: '6px',
              cursor: 'pointer',
              border: '1px solid ' + (i === currentIndex ? 'var(--color-accent)' : 'var(--color-border)'),
              background: i === currentIndex ? 'var(--color-accent)' : 'var(--color-surface)',
              color: i === currentIndex ? 'white' : 'var(--color-text-primary)'
            }"
          >
            Page {{ i + 1 }}
          </button>
        </div>
        <div style="flex: 1; overflow: auto; padding: 18px; display: flex; align-items: flex-start; justify-content: center;">
          <canvas
            ref="canvasRef"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            style="max-width: 100%; height: auto; cursor: crosshair; border-radius: 6px; border: 1px solid var(--color-border); background: white; display: block;"
          ></canvas>
        </div>
      </div>

      <!-- Right: sidebar -->
      <div style="width: 320px; flex-shrink: 0; border-left: 1px solid var(--color-border); display: flex; flex-direction: column; background: var(--color-surface);">
        <div style="padding: 14px 18px; border-bottom: 1px solid var(--color-border);">
          <h4 style="margin: 0; font-size: 14px; font-weight: 600; color: var(--color-text-primary);">
            Crops <span style="color: var(--color-text-muted); font-weight: 400;">({{ sourceCrops.length }})</span>
          </h4>
          <p style="margin: 4px 0 0; font-size: 12px; color: var(--color-text-muted); line-height: 1.4;">
            Each crop is inserted at your cursor in the editor.
          </p>
        </div>
        <div style="flex: 1; overflow-y: auto; padding: 12px;">
          <div v-if="sourceCrops.length === 0" style="padding: 24px 12px; text-align: center; color: var(--color-text-muted); font-size: 13px;">
            No crops yet. Draw a rectangle on the image to create one.
          </div>
          <div
            v-for="crop in sourceCrops"
            :key="crop.id"
            @click="selectCrop(crop.id)"
            :style="{
              padding: '10px',
              marginBottom: '8px',
              borderRadius: '8px',
              border: '1px solid ' + (selectedCropId === crop.id ? 'var(--color-accent)' : 'var(--color-border)'),
              background: 'var(--color-bg)',
              cursor: 'pointer'
            }"
          >
            <div style="display: flex; gap: 10px; align-items: flex-start;">
              <img :src="crop.dataUrl" :alt="crop.label" style="width: 64px; height: 64px; object-fit: contain; background: white; border-radius: 4px; border: 1px solid var(--color-border); flex-shrink: 0;" />
              <div style="flex: 1; min-width: 0;">
                <input
                  :value="crop.label"
                  @input="onLabelInput(crop, $event)"
                  @click.stop
                  style="width: 100%; padding: 4px 6px; font-size: 13px; font-weight: 500; background: var(--color-surface); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 4px; outline: none; box-sizing: border-box;"
                />
                <div style="display: flex; gap: 4px; margin-top: 6px; align-items: center;">
                  <span style="font-size: 11px; color: var(--color-text-muted); width: 12px;">W</span>
                  <input
                    type="number"
                    min="1"
                    :value="crop.width"
                    @input="onWidthInput(crop, $event)"
                    @click.stop
                    style="width: 100%; min-width: 0; padding: 3px 5px; font-size: 12px; background: var(--color-surface); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 4px; outline: none; box-sizing: border-box;"
                  />
                  <button
                    @click.stop="toggleAspectLock(crop)"
                    :title="crop.aspectLock ? 'Aspect ratio locked — click to unlock' : 'Aspect ratio unlocked — click to lock'"
                    :style="{
                      padding: '3px 6px',
                      borderRadius: '4px',
                      border: '1px solid var(--color-border)',
                      background: crop.aspectLock ? 'var(--color-accent)' : 'var(--color-surface)',
                      color: crop.aspectLock ? 'white' : 'var(--color-text-muted)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      lineHeight: 1
                    }"
                  >
                    <i :class="crop.aspectLock ? 'ti ti-link' : 'ti ti-unlink'" style="font-size: 13px;"></i>
                  </button>
                  <span style="font-size: 11px; color: var(--color-text-muted); width: 12px;">H</span>
                  <input
                    type="number"
                    min="1"
                    :value="crop.height"
                    @input="onHeightInput(crop, $event)"
                    @click.stop
                    :disabled="crop.aspectLock"
                    :style="{
                      width: '100%',
                      minWidth: 0,
                      padding: '3px 5px',
                      fontSize: '12px',
                      background: 'var(--color-surface)',
                      color: 'var(--color-text-primary)',
                      border: '1px solid var(--color-border)',
                      borderRadius: '4px',
                      outline: 'none',
                      boxSizing: 'border-box',
                      opacity: crop.aspectLock ? 0.55 : 1
                    }"
                  />
                </div>
                <div style="display: flex; gap: 6px; margin-top: 6px;">
                  <button
                    @click.stop="insertCrop(crop)"
                    style="flex: 1; padding: 5px 8px; font-size: 12px; border-radius: 4px; background: var(--color-accent); color: white; border: none; cursor: pointer;"
                  >Insert</button>
                  <button
                    @click.stop="deleteCrop(crop.id)"
                    style="padding: 5px 8px; font-size: 12px; border-radius: 4px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); cursor: pointer;"
                  >Delete</button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div style="padding: 14px 18px; border-top: 1px solid var(--color-border); display: flex; justify-content: flex-end;">
          <button
            @click="emit('close')"
            style="padding: 8px 18px; font-size: 14px; border-radius: 6px; background: var(--color-accent); color: white; border: none; cursor: pointer; font-weight: 500;"
          >Done</button>
        </div>
      </div>
    </div>
  </div>
  </Teleport>
</template>

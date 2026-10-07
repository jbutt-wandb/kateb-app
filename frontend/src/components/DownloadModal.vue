<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  show: { type: Boolean, required: true }
})

const emit = defineEmits(['confirm', 'close'])

const sendToDataset = ref(true)

watch(() => props.show, (open) => {
  if (open) sendToDataset.value = true
})

function onKeydown(e) {
  if (props.show && e.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

function confirm() {
  emit('confirm', { sendToDataset: sendToDataset.value })
}
</script>

<template>
  <Teleport to="body">
  <div
    v-if="show"
    style="position: fixed; inset: 0; background-color: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; z-index: 10000; padding: 24px;"
    @click.self="emit('close')"
  >
    <div
      style="background-color: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; max-width: 480px; width: 100%; padding: 28px;"
    >
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
        <h2 style="font-family: 'EB Garamond', serif; font-size: 24px; font-weight: 600; color: var(--color-text-primary); margin: 0;">
          Download notes
        </h2>
        <button
          @click="emit('close')"
          aria-label="Close"
          style="background: transparent; border: none; color: var(--color-text-muted); font-size: 22px; cursor: pointer; line-height: 1;"
        >
          ×
        </button>
      </div>

      <p style="font-size: 14px; color: var(--color-text-muted); margin: 0 0 20px 0; line-height: 1.55;">
        Also send a copy of this document to your Weave fine-tuning dataset? Embedded diagrams will be stripped from the dataset entry so the text stays clean for training.
      </p>

      <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 24px;">
        <label
          :style="{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            padding: '12px 14px',
            border: '1px solid ' + (sendToDataset ? 'var(--color-accent)' : 'var(--color-border)'),
            borderRadius: '8px',
            cursor: 'pointer',
            backgroundColor: sendToDataset ? 'rgba(0, 0, 0, 0.02)' : 'transparent'
          }"
        >
          <input type="radio" :value="true" v-model="sendToDataset" style="margin-top: 3px; accent-color: var(--color-accent);" />
          <span>
            <span style="display: block; font-size: 14px; font-weight: 600; color: var(--color-text-primary);">Yes — also save to Weave dataset</span>
            <span style="display: block; font-size: 13px; color: var(--color-text-muted); margin-top: 2px;">Helps improve the model. Image tags will be stripped from the captured text.</span>
          </span>
        </label>

        <label
          :style="{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            padding: '12px 14px',
            border: '1px solid ' + (!sendToDataset ? 'var(--color-accent)' : 'var(--color-border)'),
            borderRadius: '8px',
            cursor: 'pointer',
            backgroundColor: !sendToDataset ? 'rgba(0, 0, 0, 0.02)' : 'transparent'
          }"
        >
          <input type="radio" :value="false" v-model="sendToDataset" style="margin-top: 3px; accent-color: var(--color-accent);" />
          <span>
            <span style="display: block; font-size: 14px; font-weight: 600; color: var(--color-text-primary);">No — download locally only</span>
            <span style="display: block; font-size: 13px; color: var(--color-text-muted); margin-top: 2px;">Nothing is sent to W&amp;B.</span>
          </span>
        </label>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 10px;">
        <button
          @click="emit('close')"
          style="padding: 10px 16px; font-size: 14px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
        >
          Cancel
        </button>
        <button
          @click="confirm"
          style="padding: 10px 20px; font-size: 14px; font-weight: 500; color: white; background-color: var(--color-accent); border: none; border-radius: 6px; cursor: pointer;"
        >
          Download
        </button>
      </div>
    </div>
  </div>
  </Teleport>
</template>

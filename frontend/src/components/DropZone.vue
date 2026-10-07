<script setup>
import { ref } from 'vue'

const emit = defineEmits(['files-selected'])

const isDragging = ref(false)
const fileInput = ref(null)

const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

function handleDragOver(e) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(e) {
  e.preventDefault()
  isDragging.value = false
  const files = Array.from(e.dataTransfer.files).filter(f => allowedTypes.includes(f.type))
  if (files.length > 0) emit('files-selected', files)
}

function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  if (files.length > 0) emit('files-selected', files)
  e.target.value = ''
}

function openFilePicker() {
  fileInput.value?.click()
}
</script>

<template>
  <div style="position: relative;">
    <!-- Corner brackets -->
    <svg style="position:absolute;top:-1px;left:-1px;width:16px;height:16px;z-index:3" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M1 8 L1 1 L8 1" stroke="#C47A1A" stroke-width="1.4"/></svg>
    <svg style="position:absolute;top:-1px;right:-1px;width:16px;height:16px;z-index:3" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M15 8 L15 1 L8 1" stroke="#C47A1A" stroke-width="1.4"/></svg>
    <svg style="position:absolute;bottom:-1px;left:-1px;width:16px;height:16px;z-index:3" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M1 8 L1 15 L8 15" stroke="#C47A1A" stroke-width="1.4"/></svg>
    <svg style="position:absolute;bottom:-1px;right:-1px;width:16px;height:16px;z-index:3" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M15 8 L15 15 L8 15" stroke="#C47A1A" stroke-width="1.4"/></svg>

    <div
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="openFilePicker"
      :style="{
        border: '0.75px solid ' + (isDragging ? '#C47A1A' : '#ccc'),
        background: isDragging ? '#F5F3EE' : '#FAFAF7',
        padding: '36px 20px',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'background 0.2s, border-color 0.2s',
      }"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        accept="image/jpeg,image/png,image/gif,image/webp"
        style="display: none;"
        @change="handleFileSelect"
      />

      <div style="font-size: 20px; color: #bbb; margin-bottom: 10px;">
        <i class="ti ti-file-upload"></i>
      </div>
      <div style="font-family: 'EB Garamond', Georgia, serif; font-size: 16px; font-style: italic; color: #777;">
        Drop images here, or click to browse
      </div>
      <div style="margin-top: 6px; font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 300; color: #bbb; letter-spacing: 0.04em;">
        JPG · PNG · GIF · WEBP
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  results: {
    type: Array,
    required: true
  }
})
</script>

<template>
  <div class="h-full overflow-y-auto p-3 space-y-3">
    <div
      v-for="(result, index) in results"
      :key="index"
      class="rounded-md overflow-hidden border border-dark-border"
    >
      <!-- Image label -->
      <div class="px-3 py-1.5 bg-dark-surface border-b border-dark-border">
        <span class="text-xs text-dark-text-muted">
          {{ result.filename || `Image ${index + 1}` }}
        </span>
      </div>

      <!-- Image -->
      <div class="bg-dark-bg">
        <img
          :src="result.preview"
          :alt="result.filename"
          class="w-full"
        />
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="results.length === 0"
      class="h-full flex items-center justify-center text-dark-text-muted"
    >
      <p class="text-sm">No images</p>
    </div>
  </div>
</template>

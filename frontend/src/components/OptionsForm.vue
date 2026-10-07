<script setup>
import { useNotesStore } from '../stores/notes'

const notesStore = useNotesStore()
</script>

<template>
  <div class="bg-light-surface dark:bg-dark-surface rounded-lg border border-light-border dark:border-dark-border overflow-hidden">
    <!-- LaTeX toggle -->
    <label class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors">
      <div class="flex-1 min-w-0 pr-4">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-light-text-secondary dark:text-dark-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
          <span class="text-sm font-medium text-light-text-primary dark:text-dark-text-primary">
            LaTeX equations
          </span>
        </div>
        <p class="mt-0.5 text-xs text-light-text-secondary dark:text-dark-text-muted pl-6">
          Convert mathematical notation to LaTeX syntax
        </p>
      </div>

      <!-- Toggle switch -->
      <div class="relative flex-shrink-0">
        <input
          type="checkbox"
          v-model="notesStore.options.containsLatex"
          class="peer sr-only"
        />
        <div class="w-11 h-6 bg-light-border dark:bg-dark-border rounded-full peer-checked:bg-accent transition-colors"></div>
        <div class="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform peer-checked:translate-x-5"></div>
      </div>
    </label>

    <!-- Divider -->
    <div class="border-t border-light-border dark:border-dark-border"></div>

    <!-- Diagrams toggle -->
    <label class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors">
      <div class="flex-1 min-w-0 pr-4">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-light-text-secondary dark:text-dark-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
          </svg>
          <span class="text-sm font-medium text-light-text-primary dark:text-dark-text-primary">
            Graphs & diagrams
          </span>
        </div>
        <p class="mt-0.5 text-xs text-light-text-secondary dark:text-dark-text-muted pl-6">
          Detect and describe visual elements in your notes
        </p>
      </div>

      <!-- Toggle switch -->
      <div class="relative flex-shrink-0">
        <input
          type="checkbox"
          v-model="notesStore.options.containsDiagrams"
          class="peer sr-only"
        />
        <div class="w-11 h-6 bg-light-border dark:bg-dark-border rounded-full peer-checked:bg-accent transition-colors"></div>
        <div class="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform peer-checked:translate-x-5"></div>
      </div>
    </label>
  </div>
</template>

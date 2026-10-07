<script setup>
import { onMounted } from 'vue'
import { useConfigStore } from './stores/config'
import CredentialsModal from './components/CredentialsModal.vue'

const configStore = useConfigStore()

onMounted(async () => {
  try {
    await configStore.fetchStatus()
    if (!configStore.inferenceReady) {
      configStore.openModal('firstRun')
    }
  } catch (err) {
    console.error('Could not fetch config status:', err)
  }
})
</script>

<template>
  <div style="min-height: 100vh; background: #FAFAF7; font-family: 'Crimson Pro', Georgia, serif;">

    <!-- Corner bracket decorations -->
    <svg style="position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:0" viewBox="0 0 1200 900" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <line x1="20" y1="20" x2="56" y2="20" stroke="#1a1a1a" stroke-width="1.4"/>
      <line x1="20" y1="20" x2="20" y2="56" stroke="#1a1a1a" stroke-width="1.4"/>
      <circle cx="20" cy="20" r="2" fill="#C47A1A"/>
      <line x1="1180" y1="20" x2="1144" y2="20" stroke="#1a1a1a" stroke-width="1.4"/>
      <line x1="1180" y1="20" x2="1180" y2="56" stroke="#1a1a1a" stroke-width="1.4"/>
      <circle cx="1180" cy="20" r="2" fill="#C47A1A"/>
      <line x1="20" y1="880" x2="56" y2="880" stroke="#1a1a1a" stroke-width="1.4"/>
      <line x1="20" y1="880" x2="20" y2="844" stroke="#1a1a1a" stroke-width="1.4"/>
      <circle cx="20" cy="880" r="2" fill="#C47A1A"/>
      <line x1="1180" y1="880" x2="1144" y2="880" stroke="#1a1a1a" stroke-width="1.4"/>
      <line x1="1180" y1="880" x2="1180" y2="844" stroke="#1a1a1a" stroke-width="1.4"/>
      <circle cx="1180" cy="880" r="2" fill="#C47A1A"/>
    </svg>

    <header style="position: relative; z-index: 5;">
      <div style="padding: 28px 40px 20px; display: flex; align-items: flex-end; justify-content: space-between;">
        <div style="display: flex; align-items: flex-end; gap: 14px;">
          <div style="font-family: 'EB Garamond', Georgia, serif; font-size: 32px; font-weight: 400; letter-spacing: 8px; color: #1a1a1a; line-height: 1;">LIKHO</div>
          <div lang="ur" style="font-family: serif; font-size: 24px; color: #1a1a1a; direction: rtl; opacity: 0.55; line-height: 1; padding-bottom: 2px;">لکھو</div>
        </div>
        <div style="display: flex; align-items: center; gap: 16px;">
          <button
            @click="configStore.openModal('edit')"
            aria-label="Settings"
            title="Credentials"
            style="background: transparent; border: 0.5px solid #888; color: #555; width: 42px; height: 42px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: border-color 0.15s, color 0.15s;"
            @mouseenter="$event.currentTarget.style.borderColor='#333'; $event.currentTarget.style.color='#1a1a1a'"
            @mouseleave="$event.currentTarget.style.borderColor='#888'; $event.currentTarget.style.color='#555'"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
        </div>
      </div>

      <!-- Rule block -->
      <div style="margin: 0 40px;">
        <div style="height: 2px; background: #1a1a1a;"></div>
        <div style="margin-top: 3px; height: 3px; display: flex;">
          <div style="width: 36px; background: #A3382A; height: 100%;"></div>
          <div style="width: 18px; background: #C47A1A; height: 100%;"></div>
          <div style="width: 10px; background: #2A6496; height: 100%;"></div>
          <div style="width: 6px; background: #3D7A6E; height: 100%;"></div>
          <div style="flex: 1;"></div>
        </div>
        <div style="margin-top: 3px; height: 0.5px; background: #1a1a1a; opacity: 0.15;"></div>
      </div>
    </header>

    <main style="position: relative; z-index: 1;">
      <router-view />
    </main>

    <footer style="position: relative; z-index: 1; margin: 0 40px; padding-bottom: 32px;">
      <div style="height: 0.5px; background: #1a1a1a; opacity: 0.12;"></div>
      <div style="margin-top: 8px; font-size: 11px; font-style: italic; color: #bbb;">¹ Likho (لکھو) — to write.</div>
    </footer>

    <CredentialsModal />
  </div>
</template>

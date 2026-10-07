<script setup>
import { ref, computed, watch } from 'vue'
import { useConfigStore } from '../stores/config'

const configStore = useConfigStore()

const wandbKey = ref('')
const entity = ref('')
const project = ref('')
const selectedModel = ref('')
const tracingEnabled = ref(false)
const showWandb = ref(false)
const localError = ref(null)

const isFirstRun = computed(() => configStore.modalMode === 'firstRun')
const status = computed(() => configStore.status)

watch(
  () => configStore.isModalOpen,
  (open) => {
    if (open) {
      wandbKey.value = ''
      entity.value = status.value?.weave_entity || ''
      project.value = status.value?.weave_project || ''
      selectedModel.value = status.value?.model || ''
      tracingEnabled.value = !!status.value?.weave_tracing_enabled
      showWandb.value = false
      localError.value = null
    }
  }
)

const wandbPlaceholder = computed(() =>
  status.value?.wandb_preview ? `current: ${status.value.wandb_preview}` : 'WANDB_API_KEY'
)

async function handleSave() {
  localError.value = null

  const haveKey = !!wandbKey.value.trim() || !!status.value?.wandb_configured
  if (!haveKey) {
    localError.value = 'W&B API key is required.'
    return
  }

  if (tracingEnabled.value) {
    const haveEntity = !!entity.value.trim()
    const haveProject = !!project.value.trim()
    if (!haveEntity || !haveProject) {
      localError.value = 'Entity and project are required when tracing is enabled.'
      return
    }
  }

  const payload = {
    weave_tracing_enabled: tracingEnabled.value,
  }
  if (wandbKey.value.trim()) payload.wandb_api_key = wandbKey.value.trim()
  if (tracingEnabled.value) {
    if (entity.value.trim()) payload.weave_entity = entity.value.trim()
    if (project.value.trim()) payload.weave_project = project.value.trim()
  }
  if (selectedModel.value && selectedModel.value !== status.value?.model) {
    payload.model = selectedModel.value
  }

  try {
    await configStore.save(payload)
    configStore.closeModal()
  } catch (err) {
    localError.value = configStore.lastError || err.message
  }
}

function handleSkip() {
  configStore.closeModal({ skip: true })
}

function handleCancel() {
  configStore.closeModal()
}
</script>

<template>
  <div
    v-if="configStore.isModalOpen"
    style="position: fixed; inset: 0; background-color: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; z-index: 10000; padding: 24px;"
    @click.self="!isFirstRun && handleCancel()"
  >
    <div
      style="background-color: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; max-width: 520px; width: 100%; max-height: 90vh; overflow-y: auto; padding: 28px;"
    >
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
        <h2 style="font-size: 22px; font-weight: 700; color: var(--color-text-primary); margin: 0;">
          {{ isFirstRun ? 'Welcome to Likho' : 'Credentials' }}
        </h2>
        <button
          v-if="!isFirstRun"
          @click="handleCancel"
          aria-label="Close"
          style="background: transparent; border: none; color: var(--color-text-muted); font-size: 22px; cursor: pointer; line-height: 1;"
        >
          ×
        </button>
      </div>
      <p style="font-size: 14px; color: var(--color-text-muted); margin: 0 0 20px 0; line-height: 1.5;">
        Likho uses W&amp;B Inference for OCR. Your W&amp;B API key authenticates the model call. Turn on Weave tracing to record every call to your W&amp;B project. Values are written to your local <code style="font-family: ui-monospace, monospace;">.env</code> file (gitignored).
      </p>

      <!-- Tracing toggle -->
      <div style="margin-bottom: 18px; padding: 12px 14px; background-color: var(--color-bg); border: 1px solid var(--color-border); border-radius: 8px;">
        <label style="display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; color: var(--color-text-primary); cursor: pointer;">
          <input
            type="checkbox"
            v-model="tracingEnabled"
            style="width: 16px; height: 16px; cursor: pointer; accent-color: var(--color-accent);"
          />
          Enable Weave tracing
        </label>
        <p style="font-size: 12px; color: var(--color-text-muted); margin: 6px 0 0 26px; line-height: 1.45;">
          When off, OCR still works but no traces are sent to W&amp;B. Entity and project are only needed when this is on.
        </p>
      </div>

      <!-- Model selector -->
      <div style="margin-bottom: 18px;">
        <label style="display: block; font-size: 13px; font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
          Vision Model
          <span v-if="status?.model_source && status.model_source !== 'none'" style="font-weight: 400; color: var(--color-text-muted); margin-left: 6px;">
            (from {{ status.model_source }})
          </span>
        </label>
        <select
          v-model="selectedModel"
          style="width: 100%; padding: 10px 12px; font-size: 14px; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 6px; outline: none; box-sizing: border-box; cursor: pointer;"
        >
          <option
            v-for="(label, id) in (status?.available_models || {})"
            :key="id"
            :value="id"
          >
            {{ label }}
          </option>
        </select>
        <p style="font-size: 12px; color: var(--color-text-muted); margin: 6px 0 0 0;">
          Kimi and GLM Flash are fastest. Gemma and Qwen may be more accurate on dense pages.
        </p>
      </div>

      <!-- W&B section -->
      <div>
        <label style="display: block; font-size: 13px; font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
          W&amp;B API Key <span style="color: #f87171;">*</span>
          <span v-if="status?.wandb_configured" style="font-weight: 400; color: var(--color-text-muted); margin-left: 6px;">
            ({{ status.wandb_preview }} from {{ status.wandb_source }})
          </span>
        </label>
        <div style="display: flex; gap: 8px; margin-bottom: 12px;">
          <input
            :type="showWandb ? 'text' : 'password'"
            v-model="wandbKey"
            :placeholder="wandbPlaceholder"
            autocomplete="off"
            spellcheck="false"
            style="flex: 1; padding: 10px 12px; font-size: 14px; font-family: ui-monospace, monospace; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 6px; outline: none;"
          />
          <button
            type="button"
            @click="showWandb = !showWandb"
            style="padding: 0 12px; font-size: 12px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
          >
            {{ showWandb ? 'Hide' : 'Show' }}
          </button>
        </div>

        <template v-if="tracingEnabled">
          <label style="display: block; font-size: 13px; color: var(--color-text-primary); margin-bottom: 6px;">
            Entity <span style="color: #f87171;">*</span>
          </label>
          <input
            v-model="entity"
            placeholder="your-wandb-entity"
            autocomplete="off"
            style="width: 100%; padding: 10px 12px; margin-bottom: 12px; font-size: 14px; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 6px; outline: none; box-sizing: border-box;"
          />

          <label style="display: block; font-size: 13px; color: var(--color-text-primary); margin-bottom: 6px;">
            Project <span style="color: #f87171;">*</span>
          </label>
          <input
            v-model="project"
            placeholder="likho"
            autocomplete="off"
            style="width: 100%; padding: 10px 12px; font-size: 14px; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 6px; outline: none; box-sizing: border-box;"
          />
        </template>
      </div>

      <!-- Errors / warnings -->
      <div v-if="localError" style="margin-top: 16px; padding: 10px 12px; border-radius: 6px; font-size: 13px; background-color: rgba(239, 68, 68, 0.1); color: #f87171;">
        {{ localError }}
      </div>
      <div v-else-if="configStore.lastWeaveWarning" style="margin-top: 16px; padding: 10px 12px; border-radius: 6px; font-size: 13px; background-color: rgba(245, 158, 11, 0.12); color: #fbbf24;">
        Saved, but Weave init warning: {{ configStore.lastWeaveWarning }}
      </div>

      <!-- Footer buttons -->
      <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px;">
        <button
          v-if="isFirstRun"
          @click="handleSkip"
          :disabled="configStore.isLoading"
          style="padding: 10px 16px; font-size: 14px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
        >
          Skip for now
        </button>
        <button
          v-else
          @click="handleCancel"
          :disabled="configStore.isLoading"
          style="padding: 10px 16px; font-size: 14px; background: transparent; color: var(--color-text-muted); border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;"
        >
          Cancel
        </button>
        <button
          @click="handleSave"
          :disabled="configStore.isLoading"
          :style="{
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: '500',
            color: 'white',
            backgroundColor: 'var(--color-accent)',
            border: 'none',
            borderRadius: '6px',
            cursor: configStore.isLoading ? 'not-allowed' : 'pointer',
            opacity: configStore.isLoading ? '0.6' : '1'
          }"
        >
          {{ configStore.isLoading ? 'Saving…' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>

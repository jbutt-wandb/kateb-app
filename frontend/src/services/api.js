const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

function throwApiError(response, data, fallback) {
  const detail = data?.detail
  const err = new Error(
    typeof detail === 'string'
      ? detail
      : detail?.message || `${fallback} (${response.status})`
  )
  err.code = typeof detail === 'object' ? detail?.code : undefined
  err.status = response.status
  throw err
}

export async function processSingleImage(image, options) {
  const formData = new FormData()
  formData.append('image', image.file)
  formData.append('contains_latex', options.containsLatex)
  formData.append('contains_diagrams', options.containsDiagrams)
  formData.append('custom_instructions', options.customInstructions || '')

  const response = await fetch(`${API_BASE}/ocr/process`, {
    method: 'POST',
    body: formData
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) throwApiError(response, data, 'Processing failed')
  return data
}

export async function processCompare(image, options) {
  const formData = new FormData()
  formData.append('image', image.file)
  formData.append('contains_latex', options.containsLatex)
  formData.append('contains_diagrams', options.containsDiagrams)
  formData.append('custom_instructions', options.customInstructions || '')
  ;(options.modelIds || []).forEach(id => formData.append('model_ids', id))

  const response = await fetch(`${API_BASE}/ocr/compare`, {
    method: 'POST',
    body: formData
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) throwApiError(response, data, 'Comparison failed')
  return data
}

export async function captureDatasetRows(rows) {
  // Fire-and-forget: errors are silently swallowed so the user's download is unaffected.
  return fetch(`${API_BASE}/dataset/capture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows })
  }).catch(() => null)
}

export async function healthCheck() {
  const response = await fetch(`${API_BASE}/health`)
  return response.json()
}

export async function getConfigStatus() {
  const response = await fetch(`${API_BASE}/config/status`, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Failed to load config status (${response.status})`)
  }
  return response.json()
}

export async function saveConfig(payload) {
  const response = await fetch(`${API_BASE}/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data?.detail
    const err = new Error(
      typeof detail === 'string'
        ? detail
        : detail?.message || `Failed to save credentials (${response.status})`
    )
    err.code = typeof detail === 'object' ? detail?.code : undefined
    err.status = response.status
    throw err
  }
  return data
}

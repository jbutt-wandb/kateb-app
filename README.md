# Kateb

**Turn photos of handwritten notes into clean, editable Markdown.**

![Kateb editor — a photo of handwritten notes on the left, rendered as clean Markdown on the right](docs/screenshots/hero-editor.jpg)

*Kateb (كاتب) is Arabic for "writer."* Snap a picture of your notebook, drop it in, and Kateb hands you back Markdown — equations, diagrams, and all — ready to paste into your tool of choice.

Built with Vue 3 + FastAPI, powered by [Forge Inference](https://docs.coreweave.com/products/inference/serverless) for vision OCR, with [Forge Weave](https://docs.coreweave.com/products/wandb/weave) ready to trace every call (toggle on from the gear icon when you want it) so you can see exactly what the model did.

## Features

- Drag and drop up to 5 images at once — they process in parallel
- Optional LaTeX equations and diagram descriptions
- **Per-image editor with sticky-thumbnail gutter** — each image owns its own section, edits stay scoped to the image you're working on
- **Embed diagrams from your source images** — open the crop modal, draw a rectangle on any page, get a `![diagram-1|480](crop:c_xxxx)` reference inserted at your cursor. Per-reference resize via Obsidian-style `|W` / `|WxH` syntax, multi-page browsing in the modal, and the downloaded `.md` carries inline data-URL images so the file is self-contained
- Live Markdown editor with KaTeX math preview, click-to-zoom thumbnails, arrow-key navigation across sections
- **Compare any two of the available vision models on a single image** — pick the pair from a modal, see both OCR outputs side-by-side in a tripartite layout (image + two panes), click the image for a full-screen lightbox, then promote either model to active and continue editing — `/compare` route
- **Opt-in Forge Weave tracing** — toggle from the gear icon. When on, every OCR / comparison / prompt-injection call is traced as a versioned `weave.Model` in your Forge project, and downloads can capture per-image rows to a Forge Weave Dataset. When off (the default), Kateb works as a pure local OCR tool with no Forge traffic beyond the inference call itself
- **Opt-in dataset capture on download** — when tracing is on, a small modal asks whether to also send the page rows to your Forge Weave Dataset (`kateb-ocr-captures`). Yes → per-image `(image, edited_markdown, original_ocr)` rows ship in the background, with all markdown image tags stripped from the text so the dataset stays clean for fine-tuning. No → local download only, zero network calls
- Pick your vision model from the gear icon — Kimi (default, fastest), Gemma, or Qwen
- First-run credentials modal — no manual `.env` editing required

## Prerequisites

- Python 3.11+ (we use [uv](https://docs.astral.sh/uv/) to manage it)
- Node.js 18+
- A Forge API key with Inference access — grab one at <https://forge.coreweave.com/wandb/settings>

## Quick start

```bash
# Terminal 1 — backend
# Ensure venv is activated
uv sync
uv run uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. On first launch a modal asks for your Forge API key and (optionally) the entity + project if you want Forge Weave tracing on right away. Paste in what you need, hit Save, and Kateb writes everything to a local `.env` file (gitignored, created if missing). You're ready to drop in an image.

## Configuration

Kateb reads everything from a single `.env` file at the repo root. The in-app credentials modal (gear icon, top right) reads from and writes to this file — no restart needed.

```env
WANDB_API_KEY=             # required — authenticates Forge Inference (+ Forge Weave when tracing is on)
ENTITY=                    # required ONLY when WEAVE_TRACING_ENABLED=true
PROJECT=                   # required ONLY when WEAVE_TRACING_ENABLED=true
WEAVE_TRACING_ENABLED=     # optional, default false. Master toggle for traces + dataset capture.
MODEL=                     # optional — defaults to moonshotai/Kimi-K2.6
KATEB_DATASET_NAME=        # optional — overrides the default kateb-ocr-captures
```

The gear-icon modal has a single "Enable Forge Weave tracing" checkbox. When off (default), the entity + project fields are hidden and no traces are sent to Forge regardless of what's in `.env`. When on, those fields appear, prefill from `.env`, and `weave.init` runs.

Prefer to set things up by hand? Copy `.env.example` to `.env` and fill it in.

## Vision models

Pick whichever fits your page. Switch any time from the gear icon.

| Model | Notes |
| --- | --- |
| `moonshotai/Kimi-K2.6` *(default)* | Fast, general-purpose. Great on clean, well-lit pages. |
| `zai-org/GLM-5.3-Flash` | Lightweight flash tier — quickest option for simple pages. |
| `google/gemma-4-31B-it` | More careful on dense or messy handwriting; slower. |
| `Qwen/Qwen3.8-27B` | Dense multimodal model; strong on structured layouts (tables, multi-column). |
| `MiniMaxAI/MiniMax-M3` | General multimodal MoE — a different family worth comparing. |

All three are served by Forge Inference — see the [model catalog](https://docs.coreweave.com/products/inference/serverless) for the latest list.

## How it works

> **Want the full picture?** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) is a concise engineer's tour of the app — a workflow diagram of the request pipeline plus `file:line` pointers to where each feature lives.

Kateb calls Forge Inference's [OpenAI-compatible API](https://docs.coreweave.com/products/inference/serverless/api-reference) using the `openai` Python SDK. Images are downscaled to ≤1600px before sending (the API rejects very large base64 payloads), and structured output is enforced via `response_format={"type":"json_schema", ...}` so the model returns clean Markdown instead of prose-with-code-fences. Every OCR call is wrapped with `@weave.op`, so you'll find a full trace at `https://forge.coreweave.com/wandb/<entity>/<project>/weave` after each run.

## How Kateb uses Forge

A single Forge API key powers four integrations. **Forge Inference always runs; the other three are gated by the tracing toggle.**

### 1. Forge Inference — the model serving the OCR (always on)

The vision LLM call goes to `https://api.inference.wandb.ai/v1` via the standard `openai` Python SDK with `base_url` overridden. No OpenAI account needed; the Forge key authenticates everything. Five vision models are exposed (Kimi K2.6, GLM 5.3 Flash, Gemma 4 31B, Qwen 3.8 27B, MiniMax M3) and selected at runtime from the credentials modal.

→ Code: `backend/services/models.py` — `OCRModel(weave.Model)` builds an `AsyncOpenAI` client in its `PrivateAttr` and calls Forge Inference inside `@weave.op async def predict(...)`. The client construction and the OCR helpers live in `backend/services/inference_service.py` (`build_ocr_model`, `OCR_RESPONSE_FORMAT`, `maybe_downscale`, `clean_markdown`).
→ Docs: [Forge Inference](https://docs.coreweave.com/products/inference/serverless)

### 2. Forge Weave tracing — observability for every model call (opt-in)

Tracing is **off by default**. Flip the "Enable Forge Weave tracing" toggle in the gear-icon modal to turn it on; the modal then asks for entity + project. Under the hood:

- **On** → `weave.init(f"{entity}/{project}")` runs and `os.environ["WEAVE_DISABLED"]` is unset.
- **Off** → `os.environ["WEAVE_DISABLED"] = "true"` is set. The `weave` SDK reads this env var on every op call, so `@weave.op` methods cleanly no-op — no exceptions, no measurable overhead. Toggling mid-session is a hard stop with no restart required.

When tracing is on, every model call lands as a structured trace at `https://forge.coreweave.com/wandb/<entity>/<project>/weave`. Each call ties to a **versioned `weave.Model`** in the Forge Weave UI's Models tab: changing `OCRModel.model_id` from Kimi to Gemma produces a new version automatically, and the trace UI shows the model's config (`model_id`, `max_image_dimension`, `max_output_tokens`) in the sidebar.

The trace tree for a `/process` request looks like:

```
GuardrailModel.predict       [only if customInstructions is non-empty]
OCRModel.predict             [the actual Forge Inference call]
```

For `/compare` (one image, two user-selected models in parallel):

```
GuardrailModel.predict       [only if customInstructions is non-empty]
ComparisonModel.predict      [parent op; postprocess strips to four user inputs]
├── OCRModel.predict         [child #1, e.g. Kimi]
└── OCRModel.predict         [child #2, e.g. Gemma; asyncio.gather under the hood]
```

The two routes don't have an outer wrapper op — they're plain FastAPI handlers that `Depends`-inject the Models and call `await model.predict(...)`. Both `OCRModel.predict` and `ComparisonModel.predict` record the same four inputs via `postprocess_inputs`: `image_base64`, `contains_latex`, `contains_diagrams`, `custom_instructions`. `GuardrailModel.predict` records only `custom_instructions`. Credentials, `self`, raw `UploadFile` blobs, and MIME types are all stripped.

`weave.attributes({...})` blocks (sidecar metadata for the filter panel) are currently commented out at every call site with a developer note. Wrap any future per-call metadata in `with weave.attributes({...}):` to bring them back.

→ Code:
- `backend/services/models.py` — all three `weave.Model` subclasses + their `postprocess_*` callbacks
- `backend/services/credentials.py` — `apply_tracing_setting()` reconciles the toggle with `WEAVE_DISABLED` and `weave.init`
- `backend/routers/ocr.py` — `Depends`-injected handlers calling `model.predict(...)`

→ Docs: [Forge Weave](https://docs.coreweave.com/products/wandb/weave), [`weave.Model`](https://docs.coreweave.com/products/wandb/weave/guides/core-types/models)

### 3. Forge Weave Datasets — capture (image, edited-markdown) pairs on download (gated)

When tracing is on, **Download** opens a small modal asking whether to also send the rows to your Forge Weave Dataset. Default is Yes. If you opt in, per-image rows POST to `/api/v1/dataset/capture`; the endpoint returns `202 Accepted` immediately and writes the rows to a Forge Weave Dataset (`kateb-ocr-captures` — override via `KATEB_DATASET_NAME`) in a FastAPI `BackgroundTask`. The frontend doesn't `await` the POST — your `.md` file arrives the same instant either way.

When tracing is off, `/dataset/capture` returns `{accepted: 0}` immediately and nothing is written.

Before each row is sent, the client strips **all** markdown image tags (`![…](…)`) from the `markdown` field — both the `crop:` refs this app generates and any external images the user typed in. The dataset is meant to fine-tune a text OCR model, and image tags are noise at best in that context. The local `.md` you download is unaffected: it still inlines crops as data URLs so it's a self-contained, portable note.

Each captured row carries:

| Field | Purpose |
| --- | --- |
| `image_base64`, `image_filename` | the source image |
| `markdown` | the user's edited final text for that image |
| `original_ocr` | the model's pre-edit OCR (snapshotted at editor mount) — diff vs. `markdown` is the strongest "did the user need to fix this?" signal |
| `options` | LaTeX / diagram / custom-instructions flags at OCR time |
| `model_id` | which vision model produced the original OCR |
| `document_title`, `row_id`, `created_at` | metadata |

The dataset is versioned automatically — `add_rows` creates a new version on every download. Filter `image_sha256 == max(created_at)` at training time if you want latest-only.

→ Code: `backend/routers/dataset.py`, `frontend/src/services/api.js:captureDatasetRows`, `frontend/src/views/EditorView.vue:downloadMarkdown`

### 4. Forge Weave Guardrails — prompt-injection protection

The `customInstructions` textarea is a free-form input that gets concatenated into the OCR prompt. It's a textbook prompt-injection vector. Kateb wraps [LLM Guard](https://github.com/protectai/llm-guard)'s `PromptInjection` scanner (a fine-tuned DeBERTa classifier, runs locally, ~280MB model) as a `GuardrailModel(weave.Model)` subclass. The router calls `guardrail.predict(custom_instructions)` and reads the `{passed, risk_score}` dict directly.

What that means in practice:
- `GuardrailModel`'s public Pydantic attributes (`threshold`, `match_type`) are its version identity — tuning the threshold creates a new version automatically in the Forge Weave UI's Models tab.
- The model is `weave.publish`'d on first construction so the Models tab shows it even before the first call.
- Rejected requests **never reach the Forge Inference call** — the route raises HTTP 400 immediately. When tracing is on, the trace shows a `GuardrailModel.predict` call with `passed: false` and no downstream `OCRModel.predict`.
- The whole pre-flight runs locally (DeBERTa is a local model, no Forge network call), so it works the same way whether or not tracing is enabled — the only difference is whether the call appears in the Forge Weave UI.

→ Code:
- `backend/services/models.py` — `GuardrailModel(weave.Model)` + `get_guardrail_model()` factory + `weave.publish` on first init
- `backend/routers/ocr.py` — `_enforce_guardrail()` runs `guardrail.predict(...)` and raises HTTP 400 on rejection

→ Docs: [Forge Weave Guardrails & Monitors](https://docs.coreweave.com/products/wandb/weave/guides/evaluation/monitors)

## Project layout

```
backend/
  main.py                 FastAPI app + apply_tracing_setting() on startup
  routers/
    ocr.py                POST /api/v1/ocr/process, POST /api/v1/ocr/compare
    config.py             GET/POST /api/v1/config — credentials + tracing toggle
    dataset.py            POST /api/v1/dataset/capture — Forge Weave Dataset writes (gated)
  services/
    models.py             OCRModel / ComparisonModel / GuardrailModel — three
                          weave.Model subclasses; postprocess callbacks;
                          Depends factories (get_ocr_model_dep, get_guardrail_model)
    inference_service.py  Constants + helpers: AVAILABLE_MODELS, resolve_model,
                          OCR_RESPONSE_FORMAT, maybe_downscale, clean_markdown
    credentials.py        Reads/writes .env via python-dotenv; apply_tracing_setting()
                          reconciles the toggle with WEAVE_DISABLED and weave.init
  prompts/
    ocr_prompts.py        Prompt builder (LaTeX/diagram toggles)

frontend/src/
  views/
    UploadView.vue        Upload + options + Convert / Compare buttons
    EditorView.vue        Per-image editor sections, gutter thumbnails, Download
    CompareView.vue       Single-image comparison across two user-selected models —
                          picker modal, tripartite layout, image lightbox
  components/
    CredentialsModal.vue  Gear icon — Forge key, entity, project, active model
    DropZone.vue, ImagePreview.vue, OptionsForm.vue, ...
  stores/
    notes.js              images, results, options, customInstructions, etc.
    config.js             status (Forge credentials), available_models
    theme.js              dark/light toggle
  services/api.js         processSingleImage, processCompare,
                          captureDatasetRows, saveConfig, getConfigStatus
```

## Troubleshooting

- **`wandb_not_configured` when uploading** — open the gear icon and fill in your Forge API key. If the tracing toggle is on, entity + project are also required.
- **Empty or truncated output** — some pages confuse one model and not another. Switch models from the gear icon and retry.
- **"Image too large" errors** — Kateb already downscales to 1600px before sending. If you're hitting this on a smaller image, file an issue with the original.
- **Forge Weave traces not showing up** — first confirm the "Enable Forge Weave tracing" toggle is on in the gear-icon modal. Then confirm `ENTITY` and `PROJECT` match a Forge project you have access to; the modal surfaces any init warnings.
- **Toggled tracing off but still seeing new traces?** Refresh the credentials modal and save again — `apply_tracing_setting()` sets `WEAVE_DISABLED=true` on save. Existing traces in the UI are historical and won't disappear; only new calls are silenced.

## Learn more

- [Forge Inference docs](https://docs.coreweave.com/products/inference/serverless)
- [Forge Inference API reference](https://docs.coreweave.com/products/inference/serverless/api-reference)
- [Forge Weave (LLM observability)](https://docs.coreweave.com/products/wandb/weave)
- [Forge Weave Guardrails & Monitors](https://docs.coreweave.com/products/wandb/weave/guides/evaluation/monitors)
- [LLM Guard (ProtectAI)](https://github.com/protectai/llm-guard)

## License

MIT — see `LICENSE` if added.

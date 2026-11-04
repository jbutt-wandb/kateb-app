"""Constants and helpers used by the Weave Models in ``backend.services.models``.

This file used to host the ``InferenceService`` class. That class is gone — the
OCR/comparison/guardrail surfaces are now ``weave.Model`` instances. Everything
left here is stateless: model registries, schemas, image helpers.
"""
from __future__ import annotations

import base64
import io
import re
from typing import Optional

from PIL import Image
from pydantic import BaseModel

WANDB_INFERENCE_BASE_URL = "https://api.inference.wandb.ai/v1"

# Vision-capable models on Forge Inference. Mapping is `model_id -> friendly label`
# and is sent verbatim to the frontend so the credentials modal can render the
# dropdown without hardcoding labels. The block below is regenerated weekly from
# the public inference catalog by scripts/update_model_catalog.py (CI opens a PR).
# --- BEGIN AUTOGEN: model catalog (edited by scripts/update_model_catalog.py; do not hand-edit) ---
AVAILABLE_MODELS: dict[str, str] = {
    "moonshotai/Kimi-K2.6": "Moonshot AI Kimi K2.6",
    "MiniMaxAI/MiniMax-M3": "MiniMax M3",
    "Qwen/Qwen3.6-35B-A3B": "Qwen3.6 35B A3B",
    "Qwen/Qwen3.8-27B": "Qwen3.8 27B",
    "deepseek-ai/DeepSeek-V4.1-Flash": "DeepSeek V4.1-Flash",
    "google/gemma-4-26B-A4B-it": "Google Gemma 4 26B A4B Instruct",
    "google/gemma-4-31B-it": "Google Gemma 4 31B",
    "moonshotai/Kimi-K2.7-Code": "Moonshot AI Kimi K2.7 Code",
    "nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B": "NVIDIA Nemotron 3.5 Super VL",
    "zai-org/GLM-5.3-Flash": "Z.AI GLM 5.3 Flash",
}
DEFAULT_MODEL = "moonshotai/Kimi-K2.6"
# --- END AUTOGEN: model catalog ---

# Forge Inference rejects very large base64-encoded image payloads ("ext_proc failed").
# Resize images so the longest edge is at most this many pixels before sending.
MAX_IMAGE_DIMENSION = 1600

# Several catalog models (e.g. Gemma 4, Qwen) emit long reasoning traces before
# producing the final content. The OpenAI client surfaces only `message.content`,
# but reasoning still consumes token budget, so we set a generous ceiling here.
MAX_OUTPUT_TOKENS = 32768


def resolve_model(requested: Optional[str]) -> str:
    """Return a valid model id, falling back to the default if missing/invalid."""
    if requested and requested in AVAILABLE_MODELS:
        return requested
    return DEFAULT_MODEL


class OCROutput(BaseModel):
    """Structured output for OCR results."""
    markdown: str


# Manually-authored schema for json_schema strict mode (avoids `title` and other
# Pydantic-generated keys that strict-mode validators reject).
OCR_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "OCROutput",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"},
            },
            "required": ["markdown"],
            "additionalProperties": False,
        },
    },
}


def maybe_downscale(image_base64: str, mime_type: str) -> tuple[str, str]:
    """Decode, resize-if-needed, and re-encode as JPEG. Returns (base64, mime)."""
    raw = base64.b64decode(image_base64)
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception:
        return image_base64, mime_type

    if max(img.size) <= MAX_IMAGE_DIMENSION:
        return image_base64, mime_type

    img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


def clean_markdown(text: str) -> str:
    """Remove any markdown code fences that wrap the entire content."""
    text = re.sub(r'^```(?:markdown)?\s*\n?', '', text.strip())
    text = re.sub(r'\n?```\s*$', '', text.strip())
    return text.strip()

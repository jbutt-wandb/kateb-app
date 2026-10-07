import base64
import logging
from typing import Annotated, Optional

import weave
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel

from backend.config import settings
from backend.services.credentials import store as credential_store
from backend.services.inference_service import AVAILABLE_MODELS
from backend.services.models import (
    ComparisonModel,
    ComparisonResponse,
    GuardrailModel,
    OCRModel,
    build_comparison_model,
    get_guardrail_model,
    get_ocr_model_dep,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["OCR"])


class OCRResult(BaseModel):
    filename: str
    markdown: str


MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _enforce_guardrail(guardrail: GuardrailModel, custom_instructions: str) -> None:
    """Run the prompt-injection check; raise 400 if it fails."""
    if not custom_instructions or not custom_instructions.strip():
        return
    verdict = guardrail.predict(custom_instructions)
    if not verdict.get("passed", True):
        logger.warning(
            "Prompt injection detected (risk=%.3f) — rejecting request",
            verdict.get("risk_score", 0.0),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "prompt_injection_detected",
                "message": (
                    "Custom instructions appear to contain a prompt-injection "
                    "attempt. Edit and retry."
                ),
                "risk_score": verdict.get("risk_score", 0.0),
            },
        )


def _resolve_mime_type(image: UploadFile) -> str:
    ext = image.filename.split(".")[-1].lower() if image.filename else ""
    if ext not in settings.allowed_extensions:
        logger.error(f"Invalid file type: {ext}")
        raise HTTPException(status_code=400, detail=f"Invalid file type: {ext}")
    return MIME_TYPES.get(ext, "image/jpeg")


@router.post("/process", response_model=OCRResult)
async def process_image(
    image: Annotated[UploadFile, File()],
    contains_latex: Annotated[bool, Form()] = False,
    contains_diagrams: Annotated[bool, Form()] = False,
    custom_instructions: Annotated[str, Form()] = "",
    ocr_model: OCRModel = Depends(get_ocr_model_dep),
    guardrail: GuardrailModel = Depends(get_guardrail_model),
):
    logger.info(f"=== Starting OCR processing for {image.filename} ===")
    logger.info(f"Options - LaTeX: {contains_latex}, Diagrams: {contains_diagrams}")
    if custom_instructions:
        logger.info(f"Custom instructions: {custom_instructions[:100]}...")

    # weave.attributes(...): attaches per-call metadata that ISN'T a method
    # argument (e.g. route name, environment, request id, A/B flag). It
    # propagates to all nested ops and is filterable in the Weave UI.
    # Disabled for now — to re-enable, wrap the block below in:
    #     with weave.attributes({...}):
    # {
    #     "endpoint": "ocr.process",
    #     "contains_latex": contains_latex,
    #     "contains_diagrams": contains_diagrams,
    #     "custom_instructions_present": bool(
    #         custom_instructions and custom_instructions.strip()
    #     ),
    # }
    _enforce_guardrail(guardrail, custom_instructions)

    mime_type = _resolve_mime_type(image)
    image_bytes = await image.read()
    logger.info(f"Image size: {len(image_bytes) / 1024:.1f} KB")
    if len(image_bytes) > settings.max_file_size_mb * 1024 * 1024:
        logger.error(f"File {image.filename} exceeds size limit")
        raise HTTPException(
            status_code=400,
            detail=f"File {image.filename} exceeds {settings.max_file_size_mb}MB limit",
        )

    try:
        logger.info("Sending image to W&B Inference...")
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        markdown = await ocr_model.predict(
            image_base64,
            mime_type,
            contains_latex,
            contains_diagrams,
            custom_instructions,
        )
        logger.info(f"Received response ({len(markdown)} chars)")
        logger.info("=== OCR processing complete ===")
        return OCRResult(filename=image.filename or "image", markdown=markdown)
    except APIStatusError as e:
        msg = getattr(e, "message", None) or str(e)
        logger.error(f"W&B Inference returned {e.status_code}: {msg}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": "inference_error", "message": msg},
        )
    except APITimeoutError as e:
        logger.error(f"W&B Inference timeout: {e}")
        raise HTTPException(
            status_code=504,
            detail={"code": "inference_timeout", "message": f"W&B Inference timed out: {e}"},
        )
    except APIConnectionError as e:
        logger.error(f"W&B Inference unreachable: {e}")
        raise HTTPException(
            status_code=502,
            detail={"code": "inference_unreachable", "message": f"Could not reach W&B Inference: {e}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"code": "ocr_failed", "message": str(e)},
        )


# ---------------------------------------------------------------------------
# Comparison endpoint — runs two selected vision models on a single image so
# the user can pick which one fits their handwriting best.
# ---------------------------------------------------------------------------


@router.post("/compare", response_model=ComparisonResponse)
async def compare_models(
    image: Annotated[UploadFile, File()],
    model_ids: Annotated[list[str], Form()],
    contains_latex: Annotated[bool, Form()] = False,
    contains_diagrams: Annotated[bool, Form()] = False,
    custom_instructions: Annotated[str, Form()] = "",
    guardrail: GuardrailModel = Depends(get_guardrail_model),
):
    """Run exactly two selected W&B vision models on a single image in parallel."""
    unique_ids = list(dict.fromkeys(model_ids))
    if len(unique_ids) != 2:
        raise HTTPException(
            status_code=400,
            detail="Comparison requires exactly two distinct model_ids.",
        )
    unknown = [mid for mid in unique_ids if mid not in AVAILABLE_MODELS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model_id(s): {', '.join(unknown)}",
        )

    logger.info("=== Starting OCR comparison ===")
    logger.info(f"Models: {unique_ids}")
    logger.info(f"Options - LaTeX: {contains_latex}, Diagrams: {contains_diagrams}")

    mime_type = _resolve_mime_type(image)
    image_bytes = await image.read()
    if len(image_bytes) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File {image.filename} exceeds {settings.max_file_size_mb}MB limit",
        )
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    creds = credential_store.get()
    if not creds.wandb_api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "wandb_not_configured",
                "message": (
                    "W&B API key is not set. Open the credentials modal to "
                    "add your W&B API key."
                ),
            },
        )
    if creds.weave_tracing_enabled and not (creds.weave_entity and creds.weave_project):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "wandb_not_configured",
                "message": (
                    "Tracing is enabled but entity/project are missing. "
                    "Open the credentials modal to add them, or disable tracing."
                ),
            },
        )

    comparison: ComparisonModel = build_comparison_model(
        api_key=creds.wandb_api_key,
        entity=creds.weave_entity,
        project=creds.weave_project,
        model_ids=unique_ids,
    )

    # weave.attributes(...): per-call metadata that ISN'T a method argument
    # (route, environment, request id, A/B flag). Propagates to nested ops
    # and is filterable in the Weave UI. See /process above for details.
    # Disabled for now — re-enable by wrapping the block below in:
    #     with weave.attributes({...}):
    # {
    #     "endpoint": "ocr.compare",
    #     "model_count": len(unique_ids),
    #     "model_ids": unique_ids,
    #     "filename": image.filename or "image",
    #     "contains_latex": contains_latex,
    #     "contains_diagrams": contains_diagrams,
    #     "custom_instructions_present": bool(
    #         custom_instructions and custom_instructions.strip()
    #     ),
    # }
    _enforce_guardrail(guardrail, custom_instructions)

    response = await comparison.predict(
        image_base64=image_base64,
        mime_type=mime_type,
        filename=image.filename or "image",
        contains_latex=contains_latex,
        contains_diagrams=contains_diagrams,
        custom_instructions=custom_instructions,
    )

    succeeded = sum(1 for r in response.results if r.markdown)
    failed = len(response.results) - succeeded
    logger.info(f"=== OCR comparison complete. {succeeded} ok, {failed} failed ===")
    return response

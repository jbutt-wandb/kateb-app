import logging
import os
from datetime import datetime, timezone

import weave
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from backend.services.credentials import store as credential_store
from backend.services.inference_service import resolve_model

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dataset", tags=["Dataset"])

DATASET_NAME = os.getenv("LIKHO_DATASET_NAME", "likho-ocr-captures")


class CaptureOptions(BaseModel):
    contains_latex: bool = False
    contains_diagrams: bool = False
    custom_instructions: str = ""


class CaptureRow(BaseModel):
    row_id: str
    image_filename: str
    image_base64: str
    markdown: str
    original_ocr: str = ""
    options: CaptureOptions = CaptureOptions()
    document_title: str = ""


class CaptureRequest(BaseModel):
    rows: list[CaptureRow]


def _append_to_dataset(rows: list[dict]) -> None:
    """Best-effort write to the Weave dataset. Never raises."""
    if not credential_store.has_weave():
        logger.info("[dataset] skip — weave not configured")
        return
    credential_store.try_init_weave()
    try:
        try:
            ds = weave.ref(DATASET_NAME).get()
            ds.add_rows(rows)
            logger.info(f"[dataset] appended {len(rows)} row(s) to {DATASET_NAME}")
        except Exception:
            ds = weave.Dataset(name=DATASET_NAME, rows=rows)
            weave.publish(ds)
            logger.info(f"[dataset] created {DATASET_NAME} with {len(rows)} row(s)")
    except Exception as exc:
        logger.warning(f"[dataset] capture failed (non-fatal): {exc}")


@router.post("/capture", status_code=202)
async def capture(req: CaptureRequest, background: BackgroundTasks):
    creds = credential_store.get()
    if not creds.weave_tracing_enabled:
        logger.info("[dataset] skip — tracing disabled")
        return {"accepted": 0}
    model_id = resolve_model(creds.model)
    enriched = [
        {
            **r.model_dump(),
            "model_id": model_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for r in req.rows
    ]
    background.add_task(_append_to_dataset, enriched)
    return {"accepted": len(enriched)}

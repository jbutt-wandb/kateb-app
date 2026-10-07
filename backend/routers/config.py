import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from backend.services.credentials import store
from backend.services.inference_service import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    resolve_model,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["Config"])


class ConfigStatus(BaseModel):
    wandb_configured: bool
    wandb_preview: Optional[str] = None
    wandb_source: str
    weave_entity: Optional[str] = None
    weave_entity_source: str
    weave_project: Optional[str] = None
    weave_project_source: str
    weave_tracing_enabled: bool
    inference_ready: bool
    model: str
    model_source: str
    available_models: dict[str, str]


class ConfigUpdate(BaseModel):
    wandb_api_key: Optional[str] = None
    weave_entity: Optional[str] = None
    weave_project: Optional[str] = None
    model: Optional[str] = None
    weave_tracing_enabled: Optional[bool] = None


class ConfigSaveResponse(BaseModel):
    status: ConfigStatus
    weave_warning: Optional[str] = None


def _mask(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    if len(secret) <= 4:
        return "..." + secret
    return f"...{secret[-4:]}"


def _build_status() -> ConfigStatus:
    creds = store.get()
    sources = store.sources()
    return ConfigStatus(
        wandb_configured=bool(creds.wandb_api_key),
        wandb_preview=_mask(creds.wandb_api_key),
        wandb_source=sources["wandb_api_key"],
        weave_entity=creds.weave_entity,
        weave_entity_source=sources["weave_entity"],
        weave_project=creds.weave_project,
        weave_project_source=sources["weave_project"],
        weave_tracing_enabled=creds.weave_tracing_enabled,
        inference_ready=store.has_inference(),
        model=resolve_model(creds.model),
        model_source=sources["model"],
        available_models=AVAILABLE_MODELS,
    )


@router.get("/status", response_model=ConfigStatus)
async def get_status(response: Response) -> ConfigStatus:
    response.headers["Cache-Control"] = "no-store"
    return _build_status()


@router.post("", response_model=ConfigSaveResponse)
@router.post("/", response_model=ConfigSaveResponse, include_in_schema=False)
async def save_config(payload: ConfigUpdate, response: Response) -> ConfigSaveResponse:
    response.headers["Cache-Control"] = "no-store"

    if payload.model is not None and payload.model not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_model",
                "message": f"Unknown model '{payload.model}'. Allowed: {list(AVAILABLE_MODELS)}",
            },
        )

    payload_dict = payload.model_dump(exclude_none=True)
    store.save(payload_dict)

    weave_warning = store.apply_tracing_setting()

    return ConfigSaveResponse(status=_build_status(), weave_warning=weave_warning)

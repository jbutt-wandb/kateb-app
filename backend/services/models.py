"""Weave Models for OCR, comparison, and prompt-injection guarding.

Each model surface in Kateb is a ``weave.Model`` subclass:

* :class:`OCRModel` — single-image -> markdown via a chosen vision model.
* :class:`ComparisonModel` — fans out to two ``OCRModel`` instances in parallel.
* :class:`GuardrailModel` — wraps the ``llm_guard`` prompt-injection scanner.

Public Pydantic attributes are the Weave version identity (Weave hashes them
when publishing). Runtime state — HTTP clients, the scanner instance — lives
in ``PrivateAttr`` so it doesn't pollute the version hash or leak credentials.

The ``postprocess_inputs`` / ``postprocess_output`` callbacks attached to each
``@weave.op`` method control what makes it into the trace UI.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Optional

import weave
from fastapi import HTTPException
from llm_guard.input_scanners import PromptInjection
from llm_guard.input_scanners.prompt_injection import MatchType
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)
from pydantic import BaseModel, PrivateAttr

from backend.prompts.ocr_prompts import build_ocr_prompt
from backend.services.agent_runtime import Runner, build_ocr_agent, ocr_input
from backend.services.credentials import store as credential_store
from backend.services.inference_service import (
    AVAILABLE_MODELS,
    MAX_IMAGE_DIMENSION,
    MAX_OUTPUT_TOKENS,
    WANDB_INFERENCE_BASE_URL,
    clean_markdown,
    maybe_downscale,
    resolve_model,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response shapes shared with the router. Kept here so ``ComparisonModel.predict``
# can return them without an import cycle through ``routers/ocr.py``.
# ---------------------------------------------------------------------------


class ComparisonResult(BaseModel):
    model_id: str
    model_label: str
    markdown: Optional[str] = None
    error: Optional[str] = None


class ComparisonResponse(BaseModel):
    success: bool
    filename: str
    results: list[ComparisonResult] = []


# ---------------------------------------------------------------------------
# Postprocess callbacks — control what Weave records for each traced call.
# Each receives the full kwargs dict (including ``self``); returning only named
# keys implicitly strips the Model instance.
# ---------------------------------------------------------------------------


def _ocr_inputs_for_trace(inputs: dict) -> dict:
    return {
        "image_base64": inputs.get("image_base64"),
        "contains_latex": inputs.get("contains_latex"),
        "contains_diagrams": inputs.get("contains_diagrams"),
        "custom_instructions": inputs.get("custom_instructions", ""),
    }


def _compare_inputs_for_trace(inputs: dict) -> dict:
    return {
        "image_base64": inputs.get("image_base64"),
        "contains_latex": inputs.get("contains_latex"),
        "contains_diagrams": inputs.get("contains_diagrams"),
        "custom_instructions": inputs.get("custom_instructions", ""),
    }


def _compare_output_for_trace(response: Optional[ComparisonResponse]) -> list[dict]:
    if response is None:
        return []
    return [{"model_id": r.model_id, "markdown": r.markdown} for r in response.results]


def _guardrail_inputs_for_trace(inputs: dict) -> dict:
    return {"custom_instructions": inputs.get("custom_instructions", "")}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class OCRModel(weave.Model):
    model_id: str
    max_image_dimension: int = MAX_IMAGE_DIMENSION
    max_output_tokens: int = MAX_OUTPUT_TOKENS

    _client: Optional[AsyncOpenAI] = PrivateAttr(default=None)

    @weave.op(postprocess_inputs=_ocr_inputs_for_trace)
    async def predict(
        self,
        image_base64: str,
        mime_type: str,
        contains_latex: bool,
        contains_diagrams: bool,
        custom_instructions: str = "",
    ) -> str:
        if self._client is None:
            raise RuntimeError(
                "OCRModel._client not initialised — use build_ocr_model(...)."
            )

        prompt = build_ocr_prompt(contains_latex, contains_diagrams, custom_instructions)

        t0 = time.perf_counter()
        send_b64, send_mime = maybe_downscale(image_base64, mime_type)
        t_resize = time.perf_counter() - t0
        in_kb = len(image_base64) * 3 / 4 / 1024
        out_kb = len(send_b64) * 3 / 4 / 1024
        logger.info(
            f"[inference] resize {t_resize*1000:.0f}ms ({in_kb:.0f}KB -> {out_kb:.0f}KB)"
        )

        t1 = time.perf_counter()
        agent = build_ocr_agent(self.model_id, self._client, self.max_output_tokens)
        run_result = await Runner.run(
            agent,
            input=ocr_input(prompt, send_b64, send_mime),
            max_turns=1,  # single shot — parity with the previous one API call
        )

        t_llm = time.perf_counter() - t1
        usage = run_result.context_wrapper.usage
        logger.info(
            f"[inference] {self.model_id} call {t_llm:.2f}s "
            f"(prompt={usage.input_tokens} completion={usage.output_tokens})"
        )

        # final_output is OCROutput; non-JSON model output degrades to raw
        # markdown inside OCROutputSchema.validate_json.
        result = clean_markdown(run_result.final_output.markdown)
        logger.info(
            f"[inference] total {time.perf_counter()-t0:.2f}s, output {len(result)} chars"
        )
        return result


class ComparisonModel(weave.Model):
    model_ids: list[str]

    _ocr_models: dict[str, OCRModel] = PrivateAttr(default_factory=dict)

    @weave.op(
        postprocess_inputs=_compare_inputs_for_trace,
        postprocess_output=_compare_output_for_trace,
    )
    async def predict(
        self,
        image_base64: str,
        mime_type: str,
        filename: str,
        contains_latex: bool,
        contains_diagrams: bool,
        custom_instructions: str,
    ) -> ComparisonResponse:
        selected = {mid: AVAILABLE_MODELS.get(mid, mid) for mid in self.model_ids}

        async def _run_one(model_id: str, model_label: str) -> ComparisonResult:
            ocr = self._ocr_models.get(model_id)
            if ocr is None:
                return ComparisonResult(
                    model_id=model_id,
                    model_label=model_label,
                    error=f"OCRModel for {model_id} was not provisioned.",
                )
            try:
                # weave.attributes(...): per-call metadata that ISN'T a method
                # argument. See backend/routers/ocr.py for the broader explainer.
                # Disabled for now. The {"comparison_child": True} flag below
                # would be the only non-redundant attribute (distinguishes a
                # fanout OCR call from a standalone /process call); model_id is
                # already a Pydantic field on the child OCRModel.
                # {"model_id": model_id, "comparison_child": True}
                markdown = await ocr.predict(
                    image_base64,
                    mime_type,
                    contains_latex,
                    contains_diagrams,
                    custom_instructions,
                )
                return ComparisonResult(
                    model_id=model_id, model_label=model_label, markdown=markdown
                )
            except APIStatusError as e:
                msg = getattr(e, "message", None) or str(e)
                logger.error(f"[compare] {model_id} returned {e.status_code}: {msg}")
                return ComparisonResult(
                    model_id=model_id, model_label=model_label, error=msg
                )
            except APITimeoutError as e:
                logger.error(f"[compare] {model_id} timed out: {e}")
                return ComparisonResult(
                    model_id=model_id, model_label=model_label, error=f"Timed out: {e}"
                )
            except APIConnectionError as e:
                logger.error(f"[compare] {model_id} unreachable: {e}")
                return ComparisonResult(
                    model_id=model_id,
                    model_label=model_label,
                    error=f"Could not reach Forge Inference: {e}",
                )
            except Exception as e:
                logger.error(f"[compare] {model_id} failed: {e}")
                return ComparisonResult(
                    model_id=model_id, model_label=model_label, error=str(e)
                )

        results = await asyncio.gather(
            *(_run_one(mid, label) for mid, label in selected.items())
        )
        return ComparisonResponse(success=True, filename=filename, results=list(results))


class GuardrailModel(weave.Model):
    threshold: float = 0.5
    match_type: str = "FULL"

    _scanner: Optional[PromptInjection] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        self._scanner = PromptInjection(
            threshold=self.threshold,
            match_type=MatchType[self.match_type],
        )

    @weave.op(postprocess_inputs=_guardrail_inputs_for_trace)
    def predict(self, custom_instructions: str) -> dict:
        if not custom_instructions or not custom_instructions.strip():
            return {"passed": True, "risk_score": 0.0, "skipped": True}
        try:
            _sanitized, is_valid, risk_score = self._scanner.scan(custom_instructions)
        except Exception as exc:
            logger.warning("PromptInjection scanner failed, fail-open: %s", exc)
            return {
                "passed": True,
                "risk_score": 0.0,
                "fail_open": True,
                "error": str(exc),
            }
        return {"passed": bool(is_valid), "risk_score": float(risk_score)}


# ---------------------------------------------------------------------------
# Factories + FastAPI Depends helpers
# ---------------------------------------------------------------------------


def build_ocr_model(
    api_key: str,
    entity: Optional[str],
    project: Optional[str],
    model_id: Optional[str],
) -> OCRModel:
    model = OCRModel(model_id=resolve_model(model_id))
    kwargs: dict[str, Any] = {
        "base_url": WANDB_INFERENCE_BASE_URL,
        "api_key": api_key,
        "timeout": 60.0,
    }
    if entity and project:
        kwargs["project"] = f"{entity}/{project}"
    model._client = AsyncOpenAI(**kwargs)
    return model


def build_comparison_model(
    api_key: str,
    entity: Optional[str],
    project: Optional[str],
    model_ids: list[str],
) -> ComparisonModel:
    cmp = ComparisonModel(model_ids=model_ids)
    cmp._ocr_models = {
        mid: build_ocr_model(api_key, entity, project, mid) for mid in model_ids
    }
    return cmp


_guardrail_singleton: Optional[GuardrailModel] = None
_guardrail_lock = threading.Lock()


def get_guardrail_model() -> GuardrailModel:
    """Return a process-wide ``GuardrailModel``.

    The underlying ``llm_guard`` model loads weights on construction, so we keep
    one instance per process and publish it to Forge Weave on first use (so the Models
    tab shows it even before the first trace).

    The lock is load-bearing: FastAPI resolves this dependency in its threadpool,
    and the frontend sends one request per image in parallel. Concurrent
    transformers loads corrupt torch's global meta-device init state — every
    load in the process fails with "Cannot copy out of meta tensor" from then
    on — so the first construction must be serialized.
    """
    global _guardrail_singleton
    if _guardrail_singleton is None:
        with _guardrail_lock:
            if _guardrail_singleton is None:
                logger.info(
                    "Loading GuardrailModel (first use, model download may take a moment)..."
                )
                _guardrail_singleton = GuardrailModel()
                try:
                    weave.publish(_guardrail_singleton, name="guardrail-model")
                except Exception as exc:
                    logger.warning("weave.publish failed for guardrail: %s", exc)
    return _guardrail_singleton


def _require_credentials() -> Any:
    """Ensure we have what we need to call Forge Inference.

    The API key is always required. Entity + project are only required when
    Weave tracing is enabled (otherwise we never call ``weave.init`` and the
    AsyncOpenAI client doesn't need a project routing hint).
    """
    creds = credential_store.get()
    if not creds.wandb_api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "wandb_not_configured",
                "message": (
                    "Forge API key is not set. Open the credentials modal to "
                    "add your Forge API key."
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
    return creds


def get_ocr_model_dep() -> OCRModel:
    creds = _require_credentials()
    return build_ocr_model(
        creds.wandb_api_key, creds.weave_entity, creds.weave_project, creds.model
    )

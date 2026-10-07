"""OpenAI Agents SDK wiring for the OCR workflow.

All Agents SDK constructs live here so ``backend.services.models`` only deals
with ``Runner.run``. The agent is a single-shot (``max_turns=1``) vision call
against Forge Inference — behavior parity with the previous direct
``chat.completions.create`` call.
"""
from __future__ import annotations

from typing import Any

from agents import (
    Agent,
    AgentOutputSchemaBase,
    ModelSettings,
    OpenAIChatCompletionsModel,
    Runner,  # noqa: F401  (re-exported for backend.services.models)
    set_trace_processors,
)
from openai import AsyncOpenAI

from backend.services.inference_service import OCR_RESPONSE_FORMAT, OCROutput

# Drop the SDK's default trace processor (it exports to OpenAI's tracing
# backend, which we have no key for). The pipeline itself stays enabled so
# that weave.init — which runs after this module is imported (routers are
# imported before apply_tracing_setting in backend.main) — can append its
# WeaveTracingProcessor via autopatch. That processor is what populates the
# Agents view with invoke_agent/generation spans.
set_trace_processors([])


class OCROutputSchema(AgentOutputSchemaBase):
    """Strict output schema reusing the hand-authored OCR_RESPONSE_FORMAT.

    Hand-authored rather than derived from the pydantic model: strict-mode
    validators reject Pydantic-generated keys such as ``title``.
    """

    def is_plain_text(self) -> bool:
        return False

    def name(self) -> str:
        return "OCROutput"

    def is_strict_json_schema(self) -> bool:
        return True

    def json_schema(self) -> dict[str, Any]:
        return OCR_RESPONSE_FORMAT["json_schema"]["schema"]

    def validate_json(self, json_str: str) -> OCROutput:
        try:
            return OCROutput.model_validate_json(json_str)
        except Exception:
            # Some models emit raw markdown despite strict mode; degrade
            # gracefully instead of raising ModelBehaviorError.
            return OCROutput(markdown=json_str)


def build_ocr_agent(
    model_id: str, client: AsyncOpenAI, max_output_tokens: int
) -> Agent:
    return Agent(
        name="kateb-ocr",
        # The full OCR prompt travels in the user message (see ocr_input) —
        # same role/content as the pre-agents request payload.
        instructions=None,
        model=OpenAIChatCompletionsModel(model=model_id, openai_client=client),
        model_settings=ModelSettings(max_tokens=max_output_tokens),
        output_type=OCROutputSchema(),
    )


def ocr_input(prompt: str, image_base64: str, mime_type: str) -> list[dict]:
    """Single user turn: prompt text + inline image, as Agents SDK input items."""
    return [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{image_base64}",
                },
            ],
        }
    ]

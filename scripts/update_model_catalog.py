#!/usr/bin/env python3
"""Regenerate the vision-model registry from the public Forge inference catalog.

Run from the repo root (CI does this weekly; see .github/workflows/update-models.yml):

    python3 scripts/update_model_catalog.py

Fetches the catalog, filters to models Kateb can actually serve (image input,
general availability, hosted in cw-prod, structured-output support), and
rewrites the AUTOGEN block in backend/services/inference_service.py in place.
Writes a human-readable change summary to catalog_pr_body.md (used as the CI
PR body) and stdout.

Exit codes: 0 = updated or already current, 1 = fetch/parse/validation failure
(the registry file is never touched on failure).

Stdlib only — CI runs it on a bare python3 with no dependency install.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

CATALOG_URL = "https://trace.wandb.ai/inference/catalog/models"
FETCH_TIMEOUT_S = 30

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "backend" / "services" / "inference_service.py"
SUMMARY_PATH = REPO_ROOT / "catalog_pr_body.md"

BEGIN_MARKER = (
    "# --- BEGIN AUTOGEN: model catalog "
    "(edited by scripts/update_model_catalog.py; do not hand-edit) ---"
)
END_MARKER = "# --- END AUTOGEN: model catalog ---"


def fetch_catalog() -> dict:
    with urllib.request.urlopen(CATALOG_URL, timeout=FETCH_TIMEOUT_S) as resp:
        if resp.status != 200:
            raise RuntimeError(f"catalog returned HTTP {resp.status}")
        return json.load(resp)


def extract_vision_models(payload: dict) -> dict[str, str]:
    """Catalog JSON -> {idPlayground: label} for models Kateb can serve.

    Keep: image input, general availability (``status`` is "hosted" even for
    retired models — ``lifecycleStage`` is the real deprecation signal), hosted
    in cw-prod, and structured-output support (Kateb enforces a json_schema
    response format on every OCR call).
    """
    models: dict[str, str] = {}
    for entry in payload.get("models", []):
        try:
            model_id = entry["idPlayground"]
            if (
                "image" in entry["modalitiesInput"]
                and entry["lifecycleStage"] == "general-availability"
                and "cw-prod" in entry["availableIn"]
                and entry["featureStructuredOutput"]
            ):
                models[model_id] = entry.get("label") or model_id
        except (KeyError, TypeError):
            continue  # one malformed entry must not kill the batch
    return models


def read_current(source: str) -> tuple[dict[str, str], str]:
    """Parse the current AVAILABLE_MODELS dict and DEFAULT_MODEL from source."""
    block = source.split(BEGIN_MARKER)[1].split(END_MARKER)[0]
    current = dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block))
    default = re.search(r'DEFAULT_MODEL\s*=\s*"([^"]+)"', block).group(1)
    return current, default


def render_block(models: dict[str, str], default: str) -> str:
    lines = ["AVAILABLE_MODELS: dict[str, str] = {"]
    lines += [f'    "{mid}": "{label}",' for mid, label in models.items()]
    lines += ["}", f'DEFAULT_MODEL = "{default}"']
    return "\n" + "\n".join(lines) + "\n"


def main() -> int:
    source = REGISTRY_PATH.read_text()
    if BEGIN_MARKER not in source or END_MARKER not in source:
        print(f"ERROR: AUTOGEN markers not found in {REGISTRY_PATH}", file=sys.stderr)
        return 1

    try:
        catalog = fetch_catalog()
    except Exception as exc:
        print(f"ERROR: catalog fetch failed: {exc}", file=sys.stderr)
        return 1

    fresh = extract_vision_models(catalog)
    if not fresh:
        print("ERROR: catalog filter returned no models — refusing to wipe the registry", file=sys.stderr)
        return 1

    current, current_default = read_current(source)

    # Default policy: keep the current default while it is still served;
    # otherwise auto-promote the first live model (sorted order) and say so.
    default_note = ""
    if current_default in fresh:
        default = current_default
    else:
        default = sorted(fresh)[0]
        default_note = (
            f"\n> **Default model changed:** `{current_default}` is no longer served; "
            f"auto-promoted `{default}` to default.\n"
        )

    # Deterministic ordering (stable diffs + dropdown order): default first,
    # then the rest sorted by model id.
    ordered = {default: fresh[default]}
    ordered.update({mid: fresh[mid] for mid in sorted(fresh) if mid != default})

    new_source = (
        source.split(BEGIN_MARKER)[0]
        + BEGIN_MARKER
        + render_block(ordered, default)
        + END_MARKER
        + source.split(END_MARKER)[1]
    )

    added = sorted(set(ordered) - set(current))
    removed = sorted(set(current) - set(ordered))

    if new_source == source:
        print("Model catalog already current — no changes.")
        SUMMARY_PATH.write_text("Model catalog already current — no changes.\n")
        return 0

    REGISTRY_PATH.write_text(new_source)

    summary_lines = [
        "Weekly refresh of `AVAILABLE_MODELS` from the "
        f"[Forge inference catalog]({CATALOG_URL}).",
        "",
        f"Now serving **{len(ordered)}** vision models "
        "(image input + general availability + cw-prod + structured output).",
        "",
    ]
    if added:
        summary_lines.append("**Added:** " + ", ".join(f"`{m}`" for m in added))
    if removed:
        summary_lines.append("**Removed (retired):** " + ", ".join(f"`{m}`" for m in removed))
    if not added and not removed:
        summary_lines.append("Label/order changes only.")
    if default_note:
        summary_lines.append(default_note)
    summary = "\n".join(summary_lines) + "\n"

    SUMMARY_PATH.write_text(summary)
    print(summary)
    print(f"Updated {REGISTRY_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

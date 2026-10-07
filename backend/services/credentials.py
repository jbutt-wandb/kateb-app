import logging
import os
from pathlib import Path
from threading import Lock
from typing import Literal, Optional

import weave
from dotenv import set_key
from pydantic import BaseModel

from backend.config import Settings

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

# Internal field name -> env var name written into .env
ENV_KEYS: dict[str, str] = {
    "wandb_api_key": "WANDB_API_KEY",
    "weave_entity": "ENTITY",
    "weave_project": "PROJECT",
    "model": "MODEL",
}

# Boolean field stored as a string in .env (true/false).
BOOL_ENV_KEYS: dict[str, str] = {
    "weave_tracing_enabled": "WEAVE_TRACING_ENABLED",
}

Source = Literal["env", "none"]


class Credentials(BaseModel):
    wandb_api_key: Optional[str] = None
    weave_entity: Optional[str] = None
    weave_project: Optional[str] = None
    model: Optional[str] = None
    weave_tracing_enabled: bool = False


class CredentialStore:
    """Thin wrapper around `.env`. Reads via Pydantic Settings, writes via dotenv.set_key."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._weave_initialized_for: Optional[tuple[str, str, str]] = None
        self._refresh()

    def _refresh(self) -> None:
        s = Settings()
        self._creds = Credentials(
            wandb_api_key=s.wandb_api_key,
            weave_entity=s.weave_entity,
            weave_project=s.weave_project,
            model=s.model,
            weave_tracing_enabled=s.weave_tracing_enabled,
        )

    def get(self) -> Credentials:
        with self._lock:
            return self._creds.model_copy()

    def sources(self) -> dict[str, Source]:
        """Each field is either 'env' (set somewhere — .env or shell) or 'none'."""
        with self._lock:
            return {
                field: ("env" if getattr(self._creds, field) else "none")
                for field in ENV_KEYS
            }

    def has_inference(self) -> bool:
        """True when we can call W&B Inference (only the API key is strictly required)."""
        with self._lock:
            return bool(self._creds.wandb_api_key)

    def has_weave(self) -> bool:
        """True when all three creds are present (API key + entity + project) so weave.init can run."""
        with self._lock:
            c = self._creds
            return bool(c.wandb_api_key and c.weave_entity and c.weave_project)

    def save(self, payload: dict) -> Credentials:
        """Write non-empty payload fields to .env, update os.environ, refresh state."""
        with self._lock:
            ENV_PATH.touch(exist_ok=True)
            try:
                ENV_PATH.chmod(0o600)
            except OSError:
                pass

            for field, env_name in ENV_KEYS.items():
                value = payload.get(field)
                if value is None:
                    continue
                v = str(value).strip()
                if not v:
                    continue
                set_key(str(ENV_PATH), env_name, v, quote_mode="never")
                os.environ[env_name] = v

            for field, env_name in BOOL_ENV_KEYS.items():
                if field not in payload:
                    continue
                v = "true" if bool(payload[field]) else "false"
                set_key(str(ENV_PATH), env_name, v, quote_mode="never")
                os.environ[env_name] = v

            self._refresh()
            return self._creds.model_copy()

    def try_init_weave(self) -> Optional[str]:
        """Initialize Weave if all three creds present. Returns error string on failure, None on success/skip."""
        with self._lock:
            c = self._creds
            if not (c.wandb_api_key and c.weave_entity and c.weave_project):
                return None
            target = (c.wandb_api_key, c.weave_entity, c.weave_project)
            if self._weave_initialized_for == target:
                return None

        try:
            os.environ["WANDB_API_KEY"] = c.wandb_api_key
            weave.init(f"{c.weave_entity}/{c.weave_project}")
            with self._lock:
                self._weave_initialized_for = target
            return None
        except Exception as e:
            logger.warning(f"Weave init failed: {e}")
            return str(e)

    def apply_tracing_setting(self) -> Optional[str]:
        """Reconcile WEAVE_DISABLED with the toggle, and init Weave if newly enabled.

        - Toggle off: sets ``WEAVE_DISABLED=true`` so every ``@weave.op`` no-ops.
          Weave checks this env var on each call, so this hard-stops traces even if
          ``weave.init`` was already called earlier in this process.
        - Toggle on: unsets ``WEAVE_DISABLED`` and runs ``try_init_weave()`` (idempotent).

        Returns an optional warning string for the UI.
        """
        c = self.get()
        if not c.weave_tracing_enabled:
            os.environ["WEAVE_DISABLED"] = "true"
            return None
        os.environ.pop("WEAVE_DISABLED", None)
        if not (c.wandb_api_key and c.weave_entity and c.weave_project):
            return (
                "Tracing is enabled but entity/project are missing; "
                "traces will not be sent."
            )
        return self.try_init_weave()


store = CredentialStore()

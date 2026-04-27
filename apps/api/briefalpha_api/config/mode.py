from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv

from briefalpha_api.settings import REPO_ROOT

# Repo-root `.env` is the same source `Settings` uses (see `env_file`). Uvicorn
# does not load it into the process environment, so without this,
# `BRIEFALPHA_MODE=live` in `.env` was ignored and the API always defaulted to
# demo. `override=False` keeps explicit exports like `BRIEFALPHA_MODE=live make dev-api`.
load_dotenv(REPO_ROOT / ".env", override=False)

Mode = Literal["demo", "live"]


def resolve_mode() -> Mode:
    raw = os.getenv("BRIEFALPHA_MODE", "demo").strip().lower()
    if raw not in ("demo", "live"):
        raise ValueError(
            f"BRIEFALPHA_MODE must be 'demo' or 'live', got: {raw!r}"
        )
    return raw  # type: ignore[return-value]

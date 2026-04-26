from __future__ import annotations

import os
from typing import Literal

Mode = Literal["demo", "live"]


def resolve_mode() -> Mode:
    raw = os.getenv("BRIEFALPHA_MODE", "demo").strip().lower()
    if raw not in ("demo", "live"):
        raise ValueError(
            f"BRIEFALPHA_MODE must be 'demo' or 'live', got: {raw!r}"
        )
    return raw  # type: ignore[return-value]

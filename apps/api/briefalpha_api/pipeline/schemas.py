from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SystemMeta(BaseModel):
    mode: Literal["demo", "live"]
    status: Literal["ready", "generating", "stale", "error"]
    generated_at: str | None = None
    last_refreshed_at: str | None = None
    data_quality: Literal["fixture", "live", "partial", "unavailable"]


class MacroPulseItem(BaseModel):
    name: str
    value: str
    delta: str
    threshold: str
    status: Literal["ok", "watch", "alert"]

"""FastAPI entrypoint."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from briefalpha_api.cache import get_brief_cache
from briefalpha_api.routers import (
    admin,
    analytics,
    brief,
    judgement,
    portfolio,
    qa,
    research,
    source_health,
)
from briefalpha_api.scheduler.jobs import build_scheduler
from briefalpha_api.secrets_check import verify_secrets

log = logging.getLogger("briefalpha.main")
HKT = ZoneInfo("Asia/Hong_Kong")


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_secrets()

    # Warm-up: if today's brief isn't cached, kick off a background
    # generation. We DON'T await — the server must accept requests
    # immediately. The /api/brief/today route returns a stale fixture
    # until this lands.
    today = datetime.now(tz=HKT).strftime("%Y-%m-%d")
    cached = await get_brief_cache(today)
    if cached is None:
        log.info("startup warm-up: triggering background brief generation for %s", today)
        brief._spawn_generation(today)  # noqa: SLF001 — internal helper

    # Scheduler — disabled in tests via env so pytest doesn't spawn cron.
    scheduler = None
    if os.environ.get("BRIEFALPHA_DISABLE_SCHEDULER") != "1":
        try:
            scheduler = build_scheduler()
            scheduler.start()
            log.info("scheduler started with %d jobs", len(scheduler.get_jobs()))
        except Exception as exc:  # noqa: BLE001
            log.warning("scheduler failed to start: %s", exc)

    try:
        yield
    finally:
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception as exc:  # noqa: BLE001
                log.warning("scheduler shutdown error: %s", exc)


app = FastAPI(
    title="BriefAlpha API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/_docs",
    openapi_url="/api/_openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brief.router, prefix="/api")
app.include_router(judgement.router, prefix="/api")
app.include_router(qa.router, prefix="/api")
app.include_router(source_health.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

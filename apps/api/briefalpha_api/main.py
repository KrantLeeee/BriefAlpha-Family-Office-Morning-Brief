"""FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from briefalpha_api.routers import (
    analytics,
    brief,
    judgement,
    portfolio,
    qa,
    research,
    source_health,
)
from briefalpha_api.secrets_check import verify_secrets


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_secrets()
    yield


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


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

"""SQLAlchemy 2.x ORM models.

The FTS5 virtual table for `evidence_fts` is created by alembic migration,
not by SQLAlchemy DDL — it does not have a regular ORM mapping.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    weight: Mapped[float] = mapped_column(Float)
    asset_class: Mapped[str] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    ticker: Mapped[str] = mapped_column(String(32))
    asset_class: Mapped[str] = mapped_column(String(32))


class Universe(Base):
    __tablename__ = "universes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brief_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)  # { tickers: [{ticker, asset_class}] }
    bucket_summary: Mapped[dict] = mapped_column(JSON)
    coarse_bucket_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    cold_start_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Evidence(Base):
    """Master evidence row. evidence_pool_full.

    `selected_for_llm` distinguishes whether this row was sent to LLM as part
    of `selected_evidence_for_llm` (top_k=20) — see design.md §3.
    """

    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    brief_id: Mapped[str] = mapped_column(String(64), index=True)
    source_tier: Mapped[str] = mapped_column(String(32))  # market / news / official / research
    source_reliability: Mapped[float] = mapped_column(Float, default=0.5)
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    quote_span: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_tickers: Mapped[list] = mapped_column(JSON, default=list)
    chunk_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exposure_bucket: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    base_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_impact_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    selected_for_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    supplementary_sources: Mapped[list] = mapped_column(JSON, default=list)
    raw_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchChunk(Base):
    __tablename__ = "research_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(64), ForeignKey("research_jobs.file_id"))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    brief_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    page: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(32))  # text/table/caption
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    detected_tickers: Mapped[list] = mapped_column(JSON, default=list)
    embedding_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("evidence.evidence_id"), nullable=True
    )

    job: Mapped["ResearchJob"] = relationship(back_populates="chunks")


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    file_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    parse_report: Mapped[dict] = mapped_column(JSON, default=dict)
    failures: Mapped[list] = mapped_column(JSON, default=list)
    consent_state: Mapped[str] = mapped_column(String(32), default="not_granted")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    chunks: Mapped[list[ResearchChunk]] = relationship(back_populates="job")


class AliasMapMetadata(Base):
    __tablename__ = "alias_map_metadata"

    brief_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    alias_count: Mapped[int] = mapped_column(Integer, default=0)
    purged: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brief_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    request_hash: Mapped[str] = mapped_column(String(128))
    response_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scope: Mapped[str] = mapped_column(String(32))  # stage_a/stage_b/stage_c/qa_local/qa_global/vision
    cited_evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    accuracy_validation_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    call_type: Mapped[str] = mapped_column(String(32))  # text/vision/embedding
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audit_mode: Mapped[str] = mapped_column(String(32), default="demo")
    redacted_prompt_ciphertext: Mapped[bytes | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SourceHealthHistory(Base):
    __tablename__ = "source_health_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))  # ok/degraded/failed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_collected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ConsentLog(Base):
    __tablename__ = "consent_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    file_id: Mapped[str] = mapped_column(String(64), index=True)
    policy_version: Mapped[str] = mapped_column(String(32))
    consent_state: Mapped[str] = mapped_column(String(32))  # granted / revoked / not_granted
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AnalyticsEvent(Base):
    """Local frontend / backend analytics events. Never sent off-host."""

    __tablename__ = "analytics_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_name: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brief_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ReviewOverride(Base):
    """Persisted user action: "我已审阅" on a judgement.

    Single-user assumption (no user_id column). brief_id+judgement_id
    forms a logical primary key (UniqueConstraint enforces it).
    """
    __tablename__ = "review_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brief_id: Mapped[str] = mapped_column(String(64), index=True)
    judgement_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # "open" | "reviewed"
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (UniqueConstraint("brief_id", "judgement_id", name="uq_review_brief_judgement"),)

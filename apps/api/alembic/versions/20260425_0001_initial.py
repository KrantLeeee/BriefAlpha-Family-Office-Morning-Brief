"""initial schema (evidence + FTS5 + portfolio + audit + research + consent + analytics)

Revision ID: 0001
Revises:
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(64), index=True, nullable=False),
        sa.Column("ticker", sa.String(32), index=True, nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("sector", sa.String(64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(64), index=True, nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
    )

    op.create_table(
        "universes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brief_id", sa.String(64), index=True, unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), index=True, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("bucket_summary", sa.JSON(), nullable=False),
        sa.Column("coarse_bucket_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cold_start_passed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "evidence",
        sa.Column("evidence_id", sa.String(64), primary_key=True),
        sa.Column("brief_id", sa.String(64), index=True, nullable=False),
        sa.Column("source_tier", sa.String(32), nullable=False),
        sa.Column("source_reliability", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("quote_span", sa.JSON(), nullable=True),
        sa.Column("detected_tickers", sa.JSON(), nullable=False),
        sa.Column("chunk_type", sa.String(32), nullable=True),
        sa.Column("asset_class", sa.String(32), nullable=True),
        sa.Column("exposure_bucket", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("base_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_impact_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("selected_for_llm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("conflict", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supplementary_sources", sa.JSON(), nullable=False),
        sa.Column("raw_source_url", sa.Text(), nullable=True),
    )

    op.create_table(
        "research_jobs",
        sa.Column("file_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), index=True, nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("parse_report", sa.JSON(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("consent_state", sa.String(32), nullable=False, server_default="not_granted"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "research_chunks",
        sa.Column("chunk_id", sa.String(64), primary_key=True),
        sa.Column("file_id", sa.String(64), sa.ForeignKey("research_jobs.file_id"), nullable=False),
        sa.Column("user_id", sa.String(64), index=True, nullable=False),
        sa.Column("brief_id", sa.String(64), index=True, nullable=True),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("chunk_type", sa.String(32), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("detected_tickers", sa.JSON(), nullable=False),
        sa.Column("embedding_hash", sa.String(128), nullable=True),
        sa.Column("evidence_id", sa.String(64), sa.ForeignKey("evidence.evidence_id"), nullable=True),
    )

    op.create_table(
        "alias_map_metadata",
        sa.Column("brief_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("alias_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purged", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brief_id", sa.String(64), index=True, nullable=True),
        sa.Column("request_hash", sa.String(128), nullable=False),
        sa.Column("response_hash", sa.String(128), nullable=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("cited_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("accuracy_validation_passed", sa.Boolean(), nullable=True),
        sa.Column("call_type", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("template_version", sa.String(32), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("failure_state", sa.String(64), nullable=True),
        sa.Column("audit_mode", sa.String(32), nullable=False, server_default="demo"),
        sa.Column("redacted_prompt_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True, nullable=False),
    )

    op.create_table(
        "source_health_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(64), index=True, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("items_collected", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), index=True, nullable=False),
    )

    op.create_table(
        "consent_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(64), index=True, nullable=False),
        sa.Column("file_id", sa.String(64), index=True, nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("consent_state", sa.String(32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "analytics_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(64), index=True, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("brief_id", sa.String(64), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), index=True, nullable=False),
    )

    # SQLite FTS5 virtual table — indexes evidence by title, excerpt, detected_tickers.
    # External-content table linked to `evidence` so we can keep them in sync.
    op.execute(
        """
        CREATE VIRTUAL TABLE evidence_fts USING fts5(
            evidence_id UNINDEXED,
            brief_id UNINDEXED,
            title,
            excerpt,
            detected_tickers,
            chunk_type UNINDEXED,
            source_tier UNINDEXED,
            tokenize='unicode61'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evidence_fts")
    op.drop_table("analytics_event")
    op.drop_table("consent_log")
    op.drop_table("source_health_history")
    op.drop_table("audit_log")
    op.drop_table("alias_map_metadata")
    op.drop_table("research_chunks")
    op.drop_table("research_jobs")
    op.drop_table("evidence")
    op.drop_table("universes")
    op.drop_table("watchlist")
    op.drop_table("portfolio")

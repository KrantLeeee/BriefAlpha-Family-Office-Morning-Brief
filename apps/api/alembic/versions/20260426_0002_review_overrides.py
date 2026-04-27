"""Add review_overrides table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_overrides" not in inspector.get_table_names():
        op.create_table(
            "review_overrides",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("brief_id", sa.String(64), nullable=False),
            sa.Column("judgement_id", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.UniqueConstraint("brief_id", "judgement_id", name="uq_review_brief_judgement"),
        )
    index_names = {idx["name"] for idx in inspector.get_indexes("review_overrides")}
    if "ix_review_overrides_brief_id" not in index_names:
        op.create_index("ix_review_overrides_brief_id", "review_overrides", ["brief_id"])


def downgrade() -> None:
    op.drop_index("ix_review_overrides_brief_id", table_name="review_overrides")
    op.drop_table("review_overrides")

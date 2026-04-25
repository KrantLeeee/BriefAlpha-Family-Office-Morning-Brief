"""SQLite FTS5 index helpers.

Schema (created by alembic):
    evidence_fts(evidence_id UNINDEXED, brief_id UNINDEXED,
                 title, excerpt, detected_tickers,
                 chunk_type UNINDEXED, source_tier UNINDEXED)

`search()` results are clipped to the field whitelist (title / excerpt /
detected_tickers / chunk_type / source_tier) per task 6.4 — pipeline
callers MUST run them through `anonymization.build_aliased_evidence`
before passing to LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

Scope = Literal["judgement", "evidence", "global"]


@dataclass
class SearchHit:
    evidence_id: str
    brief_id: str
    title: str
    excerpt: str
    detected_tickers: str
    chunk_type: str | None
    source_tier: str
    rank: float


async def index_evidence(
    session: AsyncSession,
    *,
    evidence_id: str,
    brief_id: str,
    title: str,
    excerpt: str,
    detected_tickers: list[str],
    chunk_type: str | None,
    source_tier: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO evidence_fts(evidence_id, brief_id, title, excerpt,
                                     detected_tickers, chunk_type, source_tier)
            VALUES (:evidence_id, :brief_id, :title, :excerpt,
                    :detected_tickers, :chunk_type, :source_tier)
            """
        ),
        {
            "evidence_id": evidence_id,
            "brief_id": brief_id,
            "title": title,
            "excerpt": excerpt,
            "detected_tickers": " ".join(detected_tickers),
            "chunk_type": chunk_type,
            "source_tier": source_tier,
        },
    )


async def remove_evidence_index(session: AsyncSession, *, evidence_id: str) -> None:
    await session.execute(
        text("DELETE FROM evidence_fts WHERE evidence_id = :evidence_id"),
        {"evidence_id": evidence_id},
    )


async def search(
    session: AsyncSession,
    *,
    brief_id: str,
    query: str,
    scope: Scope,
    judgement_id: str | None = None,
    evidence_id: str | None = None,
    limit: int = 20,
) -> list[SearchHit]:
    """BM25-ranked search restricted to the requested scope.

    `judgement` scope filters to the cited evidence + supplementary sources
    of the supplied judgement (the caller must populate that mapping in the
    db before searching). `evidence` scope is a single-row lookup.
    `global` scope (P1) searches the full pool.
    """
    if not query.strip():
        return []

    base = """
        SELECT evidence_id, brief_id, title, excerpt, detected_tickers,
               chunk_type, source_tier, bm25(evidence_fts) AS rank
        FROM evidence_fts
        WHERE brief_id = :brief_id AND evidence_fts MATCH :q
    """
    params: dict[str, object] = {"brief_id": brief_id, "q": query}

    if scope == "evidence" and evidence_id:
        base += " AND evidence_id = :evidence_id"
        params["evidence_id"] = evidence_id

    base += " ORDER BY rank LIMIT :limit"
    params["limit"] = limit

    rows = (await session.execute(text(base), params)).mappings().all()
    return [
        SearchHit(
            evidence_id=row["evidence_id"],
            brief_id=row["brief_id"],
            title=row["title"],
            excerpt=row["excerpt"],
            detected_tickers=row["detected_tickers"],
            chunk_type=row["chunk_type"],
            source_tier=row["source_tier"],
            rank=row["rank"],
        )
        for row in rows
    ]

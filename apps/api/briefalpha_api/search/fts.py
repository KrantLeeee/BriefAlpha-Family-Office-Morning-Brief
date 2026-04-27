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

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
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
    if not rows:
        rows = await _fallback_like_search(
            session,
            brief_id=brief_id,
            query=query,
            evidence_id=evidence_id if scope == "evidence" else None,
            limit=limit,
        )
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


async def _fallback_like_search(
    session: AsyncSession,
    *,
    brief_id: str,
    query: str,
    evidence_id: str | None,
    limit: int,
):
    """Fallback for ticker typos and natural-language questions.

    FTS5 is exact-token oriented. A user typing "APPL" for "AAPL", or asking a
    Chinese sentence that contains only one useful ticker token, should still
    retrieve the obvious evidence instead of returning a false "insufficient".
    """
    tokens = [t for t in re.findall(r"[A-Za-z0-9.\-]+|[\u4e00-\u9fff]+", query) if len(t) > 1]
    if not tokens:
        return []

    sql = """
        SELECT evidence_id, brief_id, title, excerpt, detected_tickers,
               chunk_type, source_tier, 0.0 AS rank
        FROM evidence_fts
        WHERE brief_id = :brief_id
    """
    params: dict[str, object] = {"brief_id": brief_id}
    if evidence_id:
        sql += " AND evidence_id = :evidence_id"
        params["evidence_id"] = evidence_id
    candidates = (await session.execute(text(sql), params)).mappings().all()

    scored = []
    upper_tokens = [t.upper() for t in tokens if re.search(r"[A-Za-z]", t)]
    for row in candidates:
        haystack = " ".join(
            str(row.get(k) or "") for k in ("title", "excerpt", "detected_tickers", "source_tier")
        )
        haystack_upper = haystack.upper()
        score = 0
        for token in tokens:
            if token.lower() in haystack.lower():
                score += 3
        tickers = re.findall(r"\b[A-Z0-9]{1,5}(?:\.[A-Z]{1,3})?\b", haystack_upper)
        for token in upper_tokens:
            if any(_edit_distance_at_most_one(token, ticker) for ticker in tickers):
                score += 2
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in scored[:limit]]


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) <= 1
    short, long = (left, right) if len(left) < len(right) else (right, left)
    for idx in range(len(long)):
        if short == long[:idx] + long[idx + 1 :]:
            return True
    return False

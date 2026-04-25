"""Pipeline stage implementations.

Each stage is a pure function `list[Evidence] -> list[Evidence]` so the
runner can compose them and unit tests can assert on intermediate state.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from briefalpha_api.ingestion.base import RawItem
from briefalpha_api.portfolio.models import BucketSummary

TOP_K = 20

NEGATIVE_DIRECTION_RE = re.compile(r"下调|miss|下挫|不及预期|cut|减少", re.IGNORECASE)
POSITIVE_DIRECTION_RE = re.compile(r"上调|beat|raise|上扬|超预期|增加", re.IGNORECASE)


@dataclass
class Evidence:
    """Pipeline-internal evidence record. Mirrors db.models.Evidence but
    is a plain dataclass so the stages can run without a session."""

    evidence_id: str
    source_tier: str
    source_name: str
    source_reliability: float
    title: str
    excerpt: str
    quote_span: tuple[int, int] | None
    detected_tickers: list[str]
    chunk_type: str | None
    asset_class: str | None
    exposure_bucket: str | None
    published_at: datetime | None
    fetched_at: datetime
    base_score: float = 0.0
    final_impact_score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)
    selected_for_llm: bool = False
    conflict: bool = False
    requires_review: bool = False
    supplementary_sources: list[dict] = field(default_factory=list)
    raw_source_url: str | None = None


# ---------------------------------------------------------------------------
# Stage 1: normalize
# ---------------------------------------------------------------------------


def normalize(brief_id: str, raw_items: Iterable[RawItem]) -> list[Evidence]:
    out: list[Evidence] = []
    for raw in raw_items:
        evidence_id = hashlib.sha1(
            f"{brief_id}|{raw.source_name}|{raw.source_url}|{raw.title}".encode("utf-8")
        ).hexdigest()[:16]
        out.append(
            Evidence(
                evidence_id=evidence_id,
                source_tier=raw.source_tier,
                source_name=raw.source_name,
                source_reliability=_reliability_for(raw.source_tier),
                title=raw.title,
                excerpt=raw.excerpt,
                quote_span=raw.quote_span,
                detected_tickers=list(raw.detected_tickers),
                chunk_type=None,
                asset_class=raw.asset_class,
                exposure_bucket=None,
                published_at=raw.published_at,
                fetched_at=raw.fetched_at,
                raw_source_url=raw.source_url,
            )
        )
    return out


def _reliability_for(tier: str) -> float:
    return {"official": 0.9, "market": 0.8, "news": 0.6, "research": 0.5}.get(tier, 0.5)


# ---------------------------------------------------------------------------
# Stage 2: entity_linking (light NER + ticker dictionary match)
# ---------------------------------------------------------------------------


def entity_linking(items: list[Evidence], ticker_dict: set[str]) -> list[Evidence]:
    for ev in items:
        if ev.detected_tickers:
            continue
        found = []
        for tk in ticker_dict:
            if re.search(rf"\b{re.escape(tk)}\b", ev.title + " " + ev.excerpt):
                found.append(tk)
        ev.detected_tickers = found
    return items


# ---------------------------------------------------------------------------
# Stage 3: dedupe (content_hash, embedding deferred to section 5.3)
# ---------------------------------------------------------------------------


def dedupe(items: list[Evidence]) -> list[Evidence]:
    by_hash: dict[str, list[Evidence]] = defaultdict(list)
    for ev in items:
        h = hashlib.sha1(ev.excerpt[:400].encode("utf-8")).hexdigest()
        by_hash[h].append(ev)

    keep: list[Evidence] = []
    for group in by_hash.values():
        primary = max(
            group,
            key=lambda e: (
                _reliability_for(e.source_tier),
                e.published_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        primary.supplementary_sources = [
            {"source_name": e.source_name, "url": e.raw_source_url}
            for e in group
            if e is not primary
        ]
        keep.append(primary)
    return keep


# ---------------------------------------------------------------------------
# Stage 4: base_scoring
# ---------------------------------------------------------------------------


def base_scoring(items: list[Evidence], *, brief_freeze_at: datetime) -> list[Evidence]:
    seen_hashes: set[str] = set()
    for ev in items:
        recency = _recency_weight(ev.published_at, brief_freeze_at)
        novelty = _novelty_weight(ev, seen_hashes)
        ev.base_score = ev.source_reliability * recency * novelty
        ev.score_breakdown = {
            "source_reliability": ev.source_reliability,
            "recency_weight": recency,
            "novelty_weight": novelty,
        }
    return items


def _recency_weight(published_at: datetime | None, freeze_at: datetime) -> float:
    if published_at is None:
        return 0.4
    age_hours = (freeze_at - published_at).total_seconds() / 3600
    if age_hours < 6:
        return 1.0
    if age_hours < 24:
        return 0.8
    if age_hours < 72:
        return 0.5
    return 0.3


def _novelty_weight(ev: Evidence, seen: set[str]) -> float:
    h = hashlib.sha1(ev.title.encode("utf-8")).hexdigest()
    if h in seen:
        return 0.6
    seen.add(h)
    return 1.0


# ---------------------------------------------------------------------------
# Stage 5: portfolio_mapping (local — no LLM)
# ---------------------------------------------------------------------------


def portfolio_mapping(items: list[Evidence], buckets: BucketSummary) -> list[Evidence]:
    ticker_to_bucket: dict[str, str] = {}
    for b in buckets.buckets:
        for tk in b.members:
            ticker_to_bucket[tk] = b.name
    for ev in items:
        for tk in ev.detected_tickers:
            if tk in ticker_to_bucket:
                ev.exposure_bucket = ticker_to_bucket[tk]
                break
        else:
            ev.exposure_bucket = "other"
    return items


# ---------------------------------------------------------------------------
# Stage 6: conflict_resolve (MUST run before final_scoring)
# ---------------------------------------------------------------------------


def conflict_resolve(items: list[Evidence]) -> list[Evidence]:
    by_topic: dict[tuple[str, ...], list[Evidence]] = defaultdict(list)
    for ev in items:
        key = tuple(sorted(ev.detected_tickers))
        by_topic[key].append(ev)

    for group in by_topic.values():
        if len(group) < 2:
            continue
        directions = {_direction(ev) for ev in group}
        directions.discard(None)
        if len(directions) > 1:
            for ev in group:
                ev.conflict = True
                ev.requires_review = True
    return items


def _direction(ev: Evidence) -> str | None:
    text = ev.title + " " + ev.excerpt
    if NEGATIVE_DIRECTION_RE.search(text):
        return "negative"
    if POSITIVE_DIRECTION_RE.search(text):
        return "positive"
    return None


# ---------------------------------------------------------------------------
# Stage 7: final_scoring (BPS) — MUST be after conflict_resolve
# ---------------------------------------------------------------------------


def final_scoring(items: list[Evidence], *, no_direct_portfolio_link: bool) -> list[Evidence]:
    for ev in items:
        portfolio_linkage = 0.3 if no_direct_portfolio_link else _portfolio_factor(ev)
        materiality = _materiality(ev)
        market_confirmation = 0.5 if ev.conflict else 1.0
        ev.final_impact_score = ev.base_score * portfolio_linkage * materiality * market_confirmation
        ev.score_breakdown.update(
            {
                "portfolio_linkage": portfolio_linkage,
                "event_materiality": materiality,
                "market_confirmation": market_confirmation,
            }
        )
    return items


def _portfolio_factor(ev: Evidence) -> float:
    if not ev.exposure_bucket or ev.exposure_bucket == "other":
        return 0.4
    return 1.0


def _materiality(ev: Evidence) -> float:
    if ev.source_tier == "official":
        return 1.0
    if ev.source_tier == "research":
        return 0.85
    return 0.7


# ---------------------------------------------------------------------------
# Stage 8: evidence_selection — top_k with `selected_for_llm` flag (no double-write)
# ---------------------------------------------------------------------------


def evidence_selection(items: list[Evidence], *, top_k: int = TOP_K) -> list[Evidence]:
    sorted_items = sorted(items, key=lambda e: e.final_impact_score, reverse=True)
    for idx, ev in enumerate(sorted_items):
        ev.selected_for_llm = idx < top_k
    return sorted_items

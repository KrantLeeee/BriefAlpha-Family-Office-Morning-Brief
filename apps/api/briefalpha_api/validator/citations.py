"""validator.citations.

Rules:
- every cited_evidence_id MUST exist in the supplied aliased_evidence pool,
- ai_judgement_summary (stage_a) MUST cite ≥ 2 distinct evidence_ids,
- each judgement (stage_b) MUST cite ≥ 2 distinct evidence_ids.
"""
from __future__ import annotations

from typing import Any


def validate_citations(
    *,
    structured: dict[str, Any],
    pool_ids: set[str],
    scope: str,
) -> tuple[bool, str | None]:
    if scope == "stage_a":
        cited = structured.get("cited_evidence_ids", [])
        if not _all_in_pool(cited, pool_ids):
            return False, "stage_a:cited_evidence_id_not_in_pool"
        if len(set(cited)) < 2:
            return False, "stage_a:fewer_than_2_citations"
        return True, None

    if scope == "stage_b":
        for j in structured.get("judgements", []):
            cited = j.get("cited_evidence_ids", [])
            if not _all_in_pool(cited, pool_ids):
                return False, f"stage_b:judgement_{j.get('rank')}:cited_not_in_pool"
            if len(set(cited)) < 2:
                return False, f"stage_b:judgement_{j.get('rank')}:fewer_than_2_citations"
        return True, None

    if scope.startswith("qa"):
        cited = structured.get("cited_evidence_ids", [])
        # QA may answer with `insufficient_evidence=true` and zero citations.
        if structured.get("insufficient_evidence"):
            return True, None
        if not _all_in_pool(cited, pool_ids):
            return False, "qa:cited_not_in_pool"
        if len(set(cited)) < 1:
            return False, "qa:no_citation"
        return True, None

    return True, None


def _all_in_pool(ids: list[str], pool: set[str]) -> bool:
    return all(i in pool for i in ids)

"""Golden-set runner — drives the BriefAlpha pipeline against synthetic
cases and emits an aggregate metrics report.

CI invocation (from repo root):

    python -m tests.golden.runner

For each case in `cases.json`:
  1. Materialize a list of `RawItem` from `evidence_pool_input`.
  2. Run stages 1–8 directly (skipping ingestion since the pool is provided).
  3. Build aliased evidence + call Stage A/B/C through `call_text_llm`.
     With no real keys provisioned, this hits the deterministic stub
     provider that returns fixed JSON (≥2 citations from the pool).
  4. Run `validate_response` on each LLM output to compute per-rule rates.

Outputs:
  - `tests/golden/golden_metrics.json` — aggregated metrics + per-case rows.
  - stdout — a tabular summary.

Metrics (PRD §6.1 / §6.4):
  - citation_locatable_rate
  - numbers_consistent_rate
  - polarity_consistent_rate
  - time_window_consistent_rate (placeholder; full impl needs trade calendar)
  - sensitive_output_pass_rate
  - unsafe_generated_alias_count
  - conservative_brief_triggered_rate
  - no_direct_portfolio_link_rate
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make the repo importable + steer the runtime at a hermetic env so we can
# run from a fresh checkout without secrets provisioning.
# ---------------------------------------------------------------------------

CASES_PATH = Path(__file__).parent / "cases.json"
OUTPUT_PATH = Path(__file__).parent / "golden_metrics.json"

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_API = REPO_ROOT / "apps" / "api"
if str(APPS_API) not in sys.path:
    sys.path.insert(0, str(APPS_API))

os.environ.setdefault("BRIEFALPHA_SKIP_SECRETS_CHECK", "1")

# Ensure the alias_key + LLM stub keys exist in the real `data/.secrets`
# location so `encrypt_alias_map` doesn't fail. We treat any pre-existing
# files as authoritative (CI may have already provisioned real secrets).
DATA_DIR = REPO_ROOT / "data"
SECRETS_DIR = DATA_DIR / ".secrets"
ALIAS_MAPS_DIR = DATA_DIR / "alias_maps"
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
ALIAS_MAPS_DIR.mkdir(parents=True, exist_ok=True)
_ALIAS_KEY = SECRETS_DIR / "alias_key"
if not _ALIAS_KEY.exists():
    _ALIAS_KEY.write_bytes(os.urandom(32))
    _ALIAS_KEY.chmod(0o600)
_KEYS = SECRETS_DIR / "llm_api_keys.json"
if not _KEYS.exists():
    _KEYS.write_text(
        '{"anthropic":"replace-me","openai":"replace-me"}',
        encoding="utf-8",
    )
    _KEYS.chmod(0o600)

# Steer DB at a tmp-ish file so any incidental session imports don't try to
# touch a real DB. The runner itself doesn't query the DB.
_DB = DATA_DIR / "briefalpha_golden.db"
os.environ.setdefault("BRIEFALPHA_DB_URL", f"sqlite+aiosqlite:///{_DB}")


# ---------------------------------------------------------------------------
# Imports below this line require the env tweaks above to be applied first.
# ---------------------------------------------------------------------------

from briefalpha_api.anonymization import (  # noqa: E402
    build_aliased_evidence,
    make_alias_context,
)
from briefalpha_api.anonymization.sensitive_entity_dictionary import (  # noqa: E402
    build_sensitive_entity_dictionary,
)
from briefalpha_api.ingestion.base import RawItem  # noqa: E402
from briefalpha_api.llm import call_text_llm  # noqa: E402
from briefalpha_api.llm.prompt_builder import build_request  # noqa: E402
from briefalpha_api.llm.sensitive_scan import (  # noqa: E402
    scan_output_for_sensitive_terms,
)
from briefalpha_api.pipeline import stages  # noqa: E402
from briefalpha_api.portfolio.models import (  # noqa: E402
    BucketSummary,
    ExposureBucket,
)
from briefalpha_api.validator.runner import validate_response  # noqa: E402

_ALIAS_TOKEN_RE = __import__("re").compile(r"E_[0-9a-fA-F]{4}")


# ---------------------------------------------------------------------------
# Per-case driver
# ---------------------------------------------------------------------------


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Drive one golden case end-to-end and return its per-rule metrics."""
    case_id = case["id"]
    pool_input: list[dict[str, Any]] = case.get("evidence_pool_input") or []

    # 1. Build RawItems from synthetic input.
    raw_items: list[RawItem] = []
    for entry in pool_input:
        # Coerce ISO datetime strings into datetime objects if present.
        published_at = entry.get("published_at")
        fetched_at = entry.get("fetched_at")
        if isinstance(published_at, str):
            entry["published_at"] = datetime.fromisoformat(published_at)
        if isinstance(fetched_at, str):
            entry["fetched_at"] = datetime.fromisoformat(fetched_at)
        else:
            entry.setdefault("fetched_at", datetime.now(timezone.utc))
        raw_items.append(RawItem(**entry))

    # 2. Run the offline stages directly.
    freeze_at = datetime.now(timezone.utc)
    ev = stages.normalize(case_id, raw_items)
    universe_tickers: set[str] = set()
    for item in raw_items:
        for tk in item.detected_tickers:
            universe_tickers.add(tk)
    ev = stages.entity_linking(ev, universe_tickers)
    ev = stages.dedupe(ev)
    ev = stages.base_scoring(ev, brief_freeze_at=freeze_at)

    # Synthetic bucket summary: one bucket per detected asset_class so the
    # `portfolio_mapping` stage doesn't trip over an empty BucketSummary.
    buckets = BucketSummary(
        buckets=[
            ExposureBucket(
                name=ac or "other",
                members=[t for it in raw_items if it.asset_class == ac for t in it.detected_tickers],
                weight_band="0-5%",
            )
            for ac in {it.asset_class for it in raw_items}
            if ac
        ],
        coarse_bucket_mode=False,
        cold_start_passed=True,
    )
    ev = stages.portfolio_mapping(ev, buckets)
    ev = stages.conflict_resolve(ev)
    no_direct_portfolio_link = len(pool_input) <= 2
    ev = stages.final_scoring(ev, no_direct_portfolio_link=no_direct_portfolio_link)
    ev = stages.evidence_selection(ev)
    selected = [e for e in ev if e.selected_for_llm]
    pool_ids = {e.evidence_id for e in ev}

    if not selected:
        # Empty pool → conservative path; record metrics accordingly.
        return {
            "case_id": case_id,
            "pool_size": len(ev),
            "selected_size": 0,
            "no_direct_portfolio_link": no_direct_portfolio_link,
            "conservative": True,
            "citation_locatable": [],
            "numbers_pass": [],
            "polarity_pass": [],
            "sensitive_pass": [],
            "unsafe_alias_count": 0,
        }

    # 3. Anonymize + call Stage A / B / C through the wrapper.
    sensitive_dict = build_sensitive_entity_dictionary(
        universe_tickers=sorted(universe_tickers)
    )
    ctx = make_alias_context(
        brief_id=case_id,
        universe_tickers=sorted(universe_tickers),
        entity_dictionary=sensitive_dict,
    )
    aliased = []
    excerpt_by_id: dict[str, str] = {}
    for e in selected:
        ae, _segs = build_aliased_evidence(
            evidence_id=e.evidence_id,
            title=e.title,
            excerpt=e.excerpt,
            source_tier=e.source_tier,  # type: ignore[arg-type]
            asset_class=e.asset_class,
            published_at=e.published_at,
            ctx=ctx,
            quote_span_original=e.quote_span,
        )
        aliased.append(ae)
        excerpt_by_id[e.evidence_id] = e.excerpt

    audit_ctx = {"brief_id": case_id, "audit_mode": "demo"}
    aliased_payload = [a.model_dump() for a in aliased]

    responses: list[tuple[str, Any]] = []
    for scope in ("stage_a", "stage_b", "stage_c"):
        req = build_request(
            scope=scope,  # type: ignore[arg-type]
            aliased_evidence=aliased,
            extra_payload={
                "no_direct_portfolio_link": no_direct_portfolio_link,
                "aliased_evidence_json": aliased_payload,
                "judgements_json": [],
            },
        )
        try:
            resp = await call_text_llm(req, audit_ctx=audit_ctx, alias_context=ctx)
        except Exception as exc:  # noqa: BLE001
            resp = type(
                "_Err",
                (),
                {
                    "structured": None,
                    "text": f"error:{exc}",
                    "provider": "error",
                    "cited_evidence_ids": [],
                },
            )()
        responses.append((scope, resp))

    # 4. Validator + per-rule sampling.
    citation_locatable: list[bool] = []
    numbers_pass: list[bool] = []
    polarity_pass: list[bool] = []
    sensitive_pass: list[bool] = []
    unsafe_alias_count = 0
    conservative_seen = False

    for scope, resp in responses:
        if getattr(resp, "provider", "") == "conservative":
            conservative_seen = True
        structured = getattr(resp, "structured", None) or {}
        text = getattr(resp, "text", "") or ""

        # Citations locatable in pool.
        cited = list(structured.get("cited_evidence_ids", []))
        if scope == "stage_b":
            for j in structured.get("judgements", []) or []:
                cited.extend(j.get("cited_evidence_ids", []) or [])
        for cid in cited:
            citation_locatable.append(cid in pool_ids)

        # Stitch a representative excerpt for the validator. We feed the
        # union of excerpts since the stub may cite any of them.
        excerpt_text = "\n".join(excerpt_by_id.get(cid, "") for cid in cited if cid in excerpt_by_id) or "\n".join(
            excerpt_by_id.values()
        )

        result = validate_response(
            structured=structured,
            pool_ids=pool_ids,
            scope=scope,
            quote_span_segments=None,
            excerpt_text=excerpt_text,
            answer_text=text,
            quote_span_aliased=None,
            sensitive_dict=sensitive_dict,
        )
        # The validator chains rules and short-circuits — we only get a
        # single ok/reason here. Use the reason prefix to bucket pass/fail.
        reason = result.reason or ""
        if "numbers" in reason:
            numbers_pass.append(False)
        else:
            numbers_pass.append(True)
        if "polarity" in reason:
            polarity_pass.append(False)
        else:
            polarity_pass.append(True)
        if "sensitive_output" in reason:
            sensitive_pass.append(False)
        else:
            sensitive_pass.append(True)

        # Unsafe-generated-alias count: alias tokens in the response that
        # are NOT present in our alias context.
        for tok in _ALIAS_TOKEN_RE.findall(text):
            if not ctx.is_alias(tok):
                unsafe_alias_count += 1

        # Sensitive output secondary scan (independent of validator chain).
        report = scan_output_for_sensitive_terms(text, dictionary=sensitive_dict)
        if report.matched_terms:
            # Add a fail to sensitive_pass even if validator already counted.
            sensitive_pass.append(False)

    return {
        "case_id": case_id,
        "pool_size": len(ev),
        "selected_size": len(selected),
        "no_direct_portfolio_link": no_direct_portfolio_link,
        "conservative": conservative_seen,
        "citation_locatable": citation_locatable,
        "numbers_pass": numbers_pass,
        "polarity_pass": polarity_pass,
        "sensitive_pass": sensitive_pass,
        "unsafe_alias_count": unsafe_alias_count,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _rate(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return round(sum(1 for f in flags if f) / len(flags), 4)


def _aggregate(per_case: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(per_case)
    citations = [v for c in per_case for v in c["citation_locatable"]]
    numbers = [v for c in per_case for v in c["numbers_pass"]]
    polarity = [v for c in per_case for v in c["polarity_pass"]]
    sensitive = [v for c in per_case for v in c["sensitive_pass"]]
    unsafe = sum(c["unsafe_alias_count"] for c in per_case)
    conservative = sum(1 for c in per_case if c["conservative"])
    no_link = sum(1 for c in per_case if c["no_direct_portfolio_link"])

    return {
        "case_count": n,
        "citation_locatable_rate": _rate(citations),
        "numbers_consistent_rate": _rate(numbers),
        "polarity_consistent_rate": _rate(polarity),
        "time_window_consistent_rate": None,
        "sensitive_output_pass_rate": _rate(sensitive),
        "unsafe_generated_alias_count": unsafe,
        "conservative_brief_triggered_rate": round(conservative / n, 4) if n else None,
        "no_direct_portfolio_link_rate": round(no_link / n, 4) if n else None,
        "notes": {
            "time_window_consistent_rate": (
                "placeholder — full implementation requires the trade-calendar "
                "validator (validator/time_window.py) to be wired through "
                "call_text_llm's accuracy_validate hook with brief_id-scoped "
                "freeze_at; deferred to mainline D."
            ),
            "stub_provider": (
                "When llm_api_keys.json contains placeholder values, the LLM "
                "wrapper returns a deterministic stub response — these metrics "
                "exercise the *plumbing* end-to-end but do NOT measure live "
                "model quality."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _print_table(metrics: dict[str, Any], per_case: list[dict[str, Any]]) -> None:
    print()
    print("=" * 78)
    print("BriefAlpha — golden-set summary")
    print("=" * 78)
    print(f"  cases:                              {metrics['case_count']}")
    print(f"  citation_locatable_rate:            {metrics['citation_locatable_rate']}")
    print(f"  numbers_consistent_rate:            {metrics['numbers_consistent_rate']}")
    print(f"  polarity_consistent_rate:           {metrics['polarity_consistent_rate']}")
    print(f"  time_window_consistent_rate:        {metrics['time_window_consistent_rate']}")
    print(f"  sensitive_output_pass_rate:         {metrics['sensitive_output_pass_rate']}")
    print(f"  unsafe_generated_alias_count:       {metrics['unsafe_generated_alias_count']}")
    print(f"  conservative_brief_triggered_rate:  {metrics['conservative_brief_triggered_rate']}")
    print(f"  no_direct_portfolio_link_rate:      {metrics['no_direct_portfolio_link_rate']}")
    print()
    print("Per-case:")
    print(f"  {'case_id':<32} {'pool':>5} {'sel':>5} {'cons':>5} {'ndpl':>5} {'unsafe':>7}")
    for c in per_case:
        print(
            f"  {c['case_id']:<32} {c['pool_size']:>5} "
            f"{c['selected_size']:>5} "
            f"{('yes' if c['conservative'] else 'no'):>5} "
            f"{('yes' if c['no_direct_portfolio_link'] else 'no'):>5} "
            f"{c['unsafe_alias_count']:>7}"
        )
    print("=" * 78)


async def _amain() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    per_case: list[dict[str, Any]] = []
    for case in cases:
        per_case.append(await _run_case(case))

    metrics = _aggregate(per_case)
    metrics["per_case"] = [
        {
            "case_id": c["case_id"],
            "pool_size": c["pool_size"],
            "selected_size": c["selected_size"],
            "no_direct_portfolio_link": c["no_direct_portfolio_link"],
            "conservative": c["conservative"],
            "unsafe_alias_count": c["unsafe_alias_count"],
            "citation_locatable_rate": _rate(c["citation_locatable"]),
            "numbers_consistent_rate": _rate(c["numbers_pass"]),
            "polarity_consistent_rate": _rate(c["polarity_pass"]),
            "sensitive_output_pass_rate": _rate(c["sensitive_pass"]),
        }
        for c in per_case
    ]
    OUTPUT_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _print_table(metrics, per_case)
    print(f"wrote {OUTPUT_PATH}")


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()

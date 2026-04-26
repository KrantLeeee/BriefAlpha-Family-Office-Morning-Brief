# Trust Loop & 9-Issue UX Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make BriefAlpha a trustworthy interview submission: explicit `BRIEFALPHA_MODE=demo|live`, no implicit fixture fallback, and all 9 reported UX issues fixed.

**Architecture:** Two-mode (demo/live) manual switch. Default `demo` so the repo runs out-of-box without keys. `live` adds fail-fast on missing required adapters. New `Brief.system` envelope (mode/status/data_quality) is the single signal Banner / QA / SourceHealth / Refresh all read. `requires_review` becomes structured `review` with backend persistence (no localStorage). Evidence URLs get a `link_kind` enum so the frontend can route correctly. Demo mode has a keyword-keyed prebaked QA table.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite), Pydantic v2, Next.js 14 (server components), Tailwind, Zustand (memory only), Playwright, pytest, vitest.

**Source design:** `docs/plans/2026-04-26-trust-loop-and-ux-fix-design.md`

**Conventions to respect:**
- TDD: failing test → minimal impl → green → commit, every task
- DRY/YAGNI: no speculative abstractions; if a helper has one caller, inline it
- Frontend Zustand never persists to localStorage — needed-across-refresh state goes through backend
- All "demo" content must carry an explicit marker (banner, `(示例)` suffix, or `briefalpha://demo/` URL scheme)

---

## Phase 1 — Schema Foundation

Goal: Land the new contract types (Pydantic + TS) and update fixtures. **No business-logic changes.** This phase is breakable into independent tasks but they all land on `main`/feature-branch together because the next phases assume new fields exist.

### Task 1.1: Add `SystemMeta` Pydantic model + envelope

**Files:**
- Create or modify: `apps/api/briefalpha_api/pipeline/schemas.py` (look for existing Brief Pydantic schema; if it lives elsewhere, follow the import in `routers/brief.py`)
- Test: `apps/api/tests/unit/test_schemas_system_meta.py`

**Step 1: Write failing test**

```python
# tests/unit/test_schemas_system_meta.py
from briefalpha_api.pipeline.schemas import SystemMeta

def test_system_meta_required_fields():
    meta = SystemMeta(
        mode="demo",
        status="ready",
        generated_at=None,
        last_refreshed_at=None,
        data_quality="fixture",
    )
    assert meta.mode == "demo"
    assert meta.data_quality == "fixture"

def test_system_meta_rejects_invalid_mode():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        SystemMeta(mode="staging", status="ready", data_quality="live")
```

**Step 2: Run test (should fail with ImportError)**

```
pytest apps/api/tests/unit/test_schemas_system_meta.py -v
```

**Step 3: Implement minimal SystemMeta**

```python
# apps/api/briefalpha_api/pipeline/schemas.py (append)
from typing import Literal
from pydantic import BaseModel

class SystemMeta(BaseModel):
    mode: Literal["demo", "live"]
    status: Literal["ready", "generating", "stale", "error"]
    generated_at: str | None = None
    last_refreshed_at: str | None = None
    data_quality: Literal["fixture", "live", "partial", "unavailable"]
```

**Step 4: Run tests, expect pass**

**Step 5: Commit**

```
git add apps/api/briefalpha_api/pipeline/schemas.py apps/api/tests/unit/test_schemas_system_meta.py
git commit -m "feat(schemas): add SystemMeta envelope for mode/status/data_quality"
```

---

### Task 1.2: Add `MacroPulseItem` schema

**Files:**
- Modify: `apps/api/briefalpha_api/pipeline/schemas.py`
- Test: `apps/api/tests/unit/test_schemas_macro_pulse.py`

**Step 1: Failing test**

```python
def test_macro_pulse_item_shape():
    item = MacroPulseItem(name="2Y UST", value="4.61%", delta="+6bp", threshold="<4.50% benign", status="watch")
    assert item.delta.startswith("+")
```

**Step 2-3:** Implement

```python
class MacroPulseItem(BaseModel):
    name: str
    value: str
    delta: str
    threshold: str
    status: Literal["ok", "watch", "alert"]
```

**Step 4-5:** Test pass; commit `feat(schemas): add MacroPulseItem`

---

### Task 1.3: Add `ReviewMeta` + `LinkKind` enum

```python
class ReviewMeta(BaseModel):
    reason: Literal["source_conflict", "portfolio_uncertain", "threshold_breach", "data_gap"]
    note: str = ""
    status: Literal["open", "reviewed"] = "open"
    reviewed_at: str | None = None

LinkKind = Literal["external", "internal_demo", "internal_research", "unavailable"]
```

Tests: rejects invalid reason, default status is `open`. Commit `feat(schemas): add ReviewMeta and LinkKind`.

---

### Task 1.4: Sync TS types

**Files:**
- Modify: `apps/web/lib/types.ts`

**Diff:**

```ts
// add near top
export type Mode = "demo" | "live";
export type BriefStatus = "ready" | "generating" | "stale" | "error";
export type DataQuality = "fixture" | "live" | "partial" | "unavailable";
export type LinkKind = "external" | "internal_demo" | "internal_research" | "unavailable";

export interface SystemMeta {
  mode: Mode;
  status: BriefStatus;
  generated_at: string | null;
  last_refreshed_at: string | null;
  data_quality: DataQuality;
}

export interface MacroPulseItem {
  name: string;
  value: string;
  delta: string;
  threshold: string;
  status: "ok" | "watch" | "alert";
}

export interface ReviewMeta {
  reason: "source_conflict" | "portfolio_uncertain" | "threshold_breach" | "data_gap";
  note: string;
  status: "open" | "reviewed";
  reviewed_at: string | null;
}

// modify existing EvidenceCard
export interface EvidenceCard {
  evidence_id: string;
  index_label: string;
  source_label: string;
  title: string;
  quote: string;
  source_link?: string;        // now optional
  link_kind: LinkKind;          // NEW
  conflict?: boolean;
}

// modify existing SupplementarySource
export interface SupplementarySource {
  evidence_id: string;
  label: string;
  source_link?: string;
  link_kind: LinkKind;
}

// modify existing Judgement
export interface Judgement {
  // ... existing fields
  requires_review: boolean;     // keep for one release
  review: ReviewMeta | null;    // NEW preferred field
}

// modify existing PlaybookEvent
export interface PlaybookEvent {
  // ... existing fields
  related_evidence_ids: string[]; // NEW
}

// modify existing SourceHealthRow
export interface SourceHealthRow {
  name: string;
  status: StatusLevel;
  detail: string;
  is_demo: boolean;             // NEW
}

// modify existing Brief
export interface Brief {
  // ... existing fields
  system: SystemMeta;           // NEW
  macro_pulse: MacroPulseItem[];// NEW
}

// modify existing QaResponse
export interface QaResponse {
  answer: string;
  cited_evidence_ids: string[];
  citations: QaCitation[];
  insufficient_evidence: boolean;
  validation_passed: boolean;
  failure_reason?:
    | "llm_unconfigured"
    | "evidence_insufficient"
    | "out_of_scope"
    | "empty_question"
    | "demo_mode_no_match"
    | "demo_mode_prebaked";
  is_demo_response?: boolean;
}
```

**Verification step:** Run `pnpm --filter web typecheck` — expect type errors in pages/components that consume these types. Note the locations; they will be fixed in subsequent tasks.

**Commit:**

```
git add apps/web/lib/types.ts
git commit -m "feat(types): mirror new Brief/Judgement/Evidence schema fields"
```

---

### Task 1.5: Update Python fixture to populate new fields

**Files:**
- Modify: `apps/api/briefalpha_api/fixtures/brief.py`

**Changes (apply each):**

1. Top of `get_demo_brief()` dict, add:

```python
"system": {
    "mode": "demo",
    "status": "ready",
    "generated_at": "2026-04-25T08:24:00+08:00",
    "last_refreshed_at": "2026-04-25T08:24:00+08:00",
    "data_quality": "fixture",
},
"macro_pulse": [
    {"name": "2Y UST", "value": "4.61%", "delta": "+6bp", "threshold": "<4.50% benign", "status": "watch"},
    {"name": "10Y UST", "value": "4.32%", "delta": "+3bp", "threshold": "<4.20% benign", "status": "watch"},
    {"name": "DXY", "value": "104.8", "delta": "+0.3", "threshold": "<105 benign", "status": "ok"},
    {"name": "VIX", "value": "16.2", "delta": "+0.9", "threshold": "<20 benign", "status": "ok"},
    {"name": "WTI", "value": "$78.4", "delta": "+0.8%", "threshold": "<$85 benign", "status": "ok"},
    {"name": "Gold", "value": "$2,318", "delta": "+0.4%", "threshold": "narrative-only", "status": "ok"},
    {"name": "USDCNH", "value": "7.241", "delta": "+0.05", "threshold": "<7.30 benign", "status": "ok"},
    {"name": "HSI futures", "value": "17,420", "delta": "+0.6%", "threshold": "directional", "status": "ok"},
],
```

2. For each `judgement`, add `review` key:

```python
# j1
"review": {"reason": "source_conflict", "note": "路透 8% vs 彭博 10%—下调幅度分歧", "status": "open", "reviewed_at": None},
# j2
"review": None,
# j3
"review": None,
```

3. For each `evidence` and `supplementary_sources` item, change `source_link` URL and add `link_kind`. Use `briefalpha://demo/<evidence_id>` for demo:

```python
# example for ev_nvda_8k
{
    "evidence_id": "ev_nvda_8k",
    "index_label": "①",
    "source_label": "SEC EDGAR · 04-24 20:15 EDT",
    "title": "英伟达 8-K 指引更新",
    "quote": "...",
    "source_link": "briefalpha://demo/ev_nvda_8k",
    "link_kind": "internal_demo",
    "conflict": False,
}
# yfinance:// stays special
{
    "evidence_id": "ev_yfinance_quote",
    "label": "yfinance · 盘后报价",
    "source_link": "briefalpha://demo/ev_yfinance_quote",
    "link_kind": "internal_demo",
}
```

Apply to **all** evidence/supplementary entries in fixture.

4. For each `playbook_events` item, add `related_evidence_ids`:

```python
# 09:30 event (related to j2)
"related_evidence_ids": ["ev_hkex_buyback", "ev_scmp_followup"],
# 21:30 event (related to j1)
"related_evidence_ids": ["ev_nvda_8k", "ev_reuters_bbg"],
```

5. In `get_demo_source_health()`, add `is_demo: True` to every row.

**Test:**

```python
# apps/api/tests/unit/test_fixture_shape.py
from briefalpha_api.fixtures.brief import get_demo_brief, get_demo_source_health

def test_fixture_has_system_envelope():
    b = get_demo_brief()
    assert b["system"]["mode"] == "demo"
    assert b["system"]["data_quality"] == "fixture"

def test_fixture_evidence_uses_internal_demo_scheme():
    b = get_demo_brief()
    for j in b["judgements"]:
        for ev in j["evidence"]:
            assert ev["link_kind"] in {"internal_demo", "external", "internal_research", "unavailable"}
            if ev["link_kind"] == "internal_demo":
                assert ev["source_link"].startswith("briefalpha://demo/")

def test_fixture_macro_pulse_has_8_items():
    assert len(get_demo_brief()["macro_pulse"]) == 8

def test_source_health_rows_are_demo():
    sh = get_demo_source_health()
    assert all(row["is_demo"] is True for row in sh["rows"])

def test_playbook_events_have_related_evidence():
    for ev in get_demo_brief()["playbook_events"]:
        assert "related_evidence_ids" in ev
```

**Commands:**
```
pytest apps/api/tests/unit/test_fixture_shape.py -v
```

**Commit:**
```
git add apps/api/briefalpha_api/fixtures/brief.py apps/api/tests/unit/test_fixture_shape.py
git commit -m "feat(fixtures): populate new schema fields with self-consistent demo data"
```

---

### Task 1.6: Mirror fixture changes in `apps/web/lib/fixtures.ts`

**Files:** `apps/web/lib/fixtures.ts`

Apply same changes as Task 1.5 to the TS fixture (the file already has parallel structure). Add `system`, `macro_pulse`, `review`, `link_kind`, `related_evidence_ids`, `is_demo`. Keep parity.

**Verification:**

```
pnpm --filter web typecheck
```

Some downstream component errors are expected (will fix later). Confirm fixture file itself has zero type errors.

**Commit:** `feat(fixtures-web): mirror new fixture fields for SSR fallback`

---

### Task 1.7: Add `requires_review` → `review` compat helper

**Files:**
- Modify: `apps/api/briefalpha_api/pipeline/artifact.py` (around `_level_label`, line ~278)
- Test: `apps/api/tests/unit/test_review_compat.py`

**Step 1: Failing test**

```python
def test_compat_maps_requires_review_to_data_gap():
    raw = {"requires_review": True, "review": None}
    out = derive_review(raw)
    assert out == {"reason": "data_gap", "note": "", "status": "open", "reviewed_at": None}

def test_compat_prefers_explicit_review():
    raw = {"requires_review": True, "review": {"reason": "source_conflict", "note": "n", "status": "open", "reviewed_at": None}}
    assert derive_review(raw)["reason"] == "source_conflict"

def test_compat_returns_none_when_neither_set():
    assert derive_review({"requires_review": False}) is None
```

**Step 2-3: Implementation**

```python
# in artifact.py
def derive_review(raw: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(raw.get("review"), dict):
        return raw["review"]
    if raw.get("requires_review"):
        return {"reason": "data_gap", "note": "", "status": "open", "reviewed_at": None}
    return None
```

Then in the judgement builder (around line 258-274), add `"review": derive_review(raw)` to the output dict.

**Step 4-5:** Tests pass; commit `feat(artifact): derive review from requires_review for back-compat`.

---

## Phase 2 — Mode + Banner + Refresh + README

### Task 2.1: `BRIEFALPHA_MODE` config + parsing

**Files:**
- Create: `apps/api/briefalpha_api/config/mode.py`
- Test: `apps/api/tests/unit/test_mode_config.py`

**Step 1: Failing test**

```python
def test_mode_demo_default(monkeypatch):
    monkeypatch.delenv("BRIEFALPHA_MODE", raising=False)
    assert resolve_mode() == "demo"

def test_mode_live(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "live")
    assert resolve_mode() == "live"

def test_mode_invalid_raises(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "staging")
    with pytest.raises(ValueError):
        resolve_mode()
```

**Step 2-3:** Implementation

```python
# config/mode.py
import os
from typing import Literal

Mode = Literal["demo", "live"]

def resolve_mode() -> Mode:
    raw = os.getenv("BRIEFALPHA_MODE", "demo").strip().lower()
    if raw not in ("demo", "live"):
        raise ValueError(f"BRIEFALPHA_MODE must be 'demo' or 'live', got: {raw!r}")
    return raw  # type: ignore[return-value]
```

**Commit:** `feat(config): add BRIEFALPHA_MODE resolution`

---

### Task 2.2: Live mode fail-fast validator

**Files:**
- Create: `apps/api/briefalpha_api/config/live_preconditions.py`
- Test: `apps/api/tests/unit/test_live_preconditions.py`

**Step 1: Test scenarios**

```python
def test_live_passes_with_minimum_setup(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MARKET_PROVIDERS", "yfinance")
    monkeypatch.setenv("BRIEFALPHA_NEWS_PROVIDERS", "google_news_rss")
    monkeypatch.setenv("BRIEFALPHA_OFFICIAL_PROVIDERS", "sec_edgar")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    issues = check_live_preconditions()
    assert issues == []

def test_live_fails_without_market_provider(monkeypatch):
    monkeypatch.delenv("BRIEFALPHA_MARKET_PROVIDERS", raising=False)
    issues = check_live_preconditions()
    assert any("market" in i for i in issues)

def test_live_fails_without_sec_user_agent(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_OFFICIAL_PROVIDERS", "sec_edgar")
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    issues = check_live_preconditions()
    assert any("SEC_EDGAR_USER_AGENT" in i for i in issues)

def test_live_requires_finnhub_key_when_finnhub_enabled(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MARKET_PROVIDERS", "yfinance,finnhub")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    issues = check_live_preconditions()
    assert any("FINNHUB_API_KEY" in i for i in issues)
```

**Step 2-3:** Implementation per design §1.2.

**Step 5:** Commit `feat(config): add live-mode fail-fast preconditions`

---

### Task 2.3: Wire `resolve_mode()` + preconditions into app startup

**Files:**
- Modify: `apps/api/briefalpha_api/main.py`

**Diff sketch:**

```python
# in lifespan/startup
from briefalpha_api.config.mode import resolve_mode
from briefalpha_api.config.live_preconditions import check_live_preconditions

mode = resolve_mode()
log.info("BRIEFALPHA_MODE=%s", mode)
if mode == "live":
    issues = check_live_preconditions()
    if issues:
        log.error("Live mode preconditions failed:\n  - %s", "\n  - ".join(issues))
        raise SystemExit(1)
app.state.mode = mode
```

**Test:** Add integration test that starts app with bad live config and asserts SystemExit.

**Commit:** `feat(startup): fail-fast on missing live preconditions; expose mode on app.state`

---

### Task 2.4: Stamp `system` envelope on every brief response

**Files:**
- Modify: `apps/api/briefalpha_api/pipeline/artifact.py` (final assembly)
- Modify: `apps/api/briefalpha_api/routers/brief.py`

**Logic (in `brief.py`):**

```python
def _stamp_system(brief: dict, *, mode: Mode, status: BriefStatus, data_quality: DataQuality) -> dict:
    brief["system"] = {
        "mode": mode,
        "status": status,
        "generated_at": brief.get("system", {}).get("generated_at"),
        "last_refreshed_at": _now_iso_hkt(),
        "data_quality": data_quality,
    }
    return brief
```

Apply in routes per design §1.3.

**Test:** integration test asserting `system.mode` matches `app.state.mode` on response.

**Commit:** `feat(brief): stamp system envelope on every response`

---

### Task 2.5: Kill implicit fixture fallback in `live` mode

**Files:**
- Modify: `apps/api/briefalpha_api/routers/brief.py`

**Change (replace the cache-miss block, currently lines 67-73):**

```python
@router.get("/brief/today")
async def brief_today(request: Request) -> dict[str, Any]:
    brief_id = _today_hkt()
    cached = await get_brief_cache(brief_id)
    mode = request.app.state.mode

    if cached is not None:
        return _stamp_system(cached, mode=mode, status="ready",
                             data_quality="live" if mode == "live" else "fixture")

    if mode == "demo":
        _spawn_generation(brief_id)  # demo regen also keyed off; harmless
        fixture = get_demo_brief()
        fixture["brief_id"] = brief_id
        fixture["brief_date_hkt"] = brief_id
        return _stamp_system(fixture, mode="demo", status="ready", data_quality="fixture")

    # live mode: NEVER return fixture
    _spawn_generation(brief_id)
    skeleton = _empty_brief_skeleton(brief_id)
    return _stamp_system(skeleton, mode="live", status="generating", data_quality="unavailable")
```

`_empty_brief_skeleton()` returns a brief with empty arrays/None values but valid shape so the frontend doesn't crash.

**Tests:**
- demo mode cache miss returns fixture with `data_quality="fixture"`
- live mode cache miss returns `status="generating"`, no fixture content (`base_case.headline == ""`)
- live mode cache hit returns `data_quality="live"`

**Commit:** `feat(brief): live mode no longer falls back to fixture; returns generating skeleton`

---

### Task 2.6: Kill implicit fallback in `apps/web/lib/api.ts`

**Files:**
- Modify: `apps/web/lib/api.ts`

**Change `getBriefToday()`:**

```ts
export async function getBriefToday(): Promise<Brief> {
  // Real network failures bubble up — let the page render an explicit error state
  // instead of silently masquerading fixture as live data.
  return fetchJson<Brief>("/api/brief/today");
}

export async function getSourceHealth(): Promise<SourceHealth> {
  return fetchJson<SourceHealth>("/api/source-health");
}
```

The page (server component) catches the error and renders an error banner (Task 2.8 ModeBanner handles this).

**Test:** Vitest unit test asserting `getBriefToday` rejects on 500.

**Commit:** `feat(web-api): drop silent fixture fallback in API client`

---

### Task 2.7: Add `POST /api/admin/data/refresh` endpoint

**Files:**
- Modify: `apps/api/briefalpha_api/routers/admin.py` (file already exists per git status)
- Test: `apps/api/tests/integration/test_admin_refresh.py`

**Endpoint logic:**

```python
@router.post("/admin/data/refresh")
async def refresh_data(request: Request) -> dict[str, Any]:
    mode = request.app.state.mode
    brief_id = _today_hkt()

    if mode == "demo":
        # Rotate fixture timestamps so UI shows "刚刷新"
        from briefalpha_api.fixtures.brief import get_demo_brief
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(tz=ZoneInfo("Asia/Hong_Kong"))
        await invalidate_brief_cache(brief_id)
        return {
            "status": "demo_refreshed",
            "brief_id": brief_id,
            "refreshed_at_hkt": now.strftime("%H:%M"),
            "note": "示例数据，非实时采集",
        }

    # live: trigger ingestion → brief regen
    await trigger_ingestion()  # existing helper or inline
    _spawn_generation(brief_id)
    return {"status": "queued", "brief_id": brief_id}
```

**Tests:** demo path returns `demo_refreshed`; live path returns `queued` + spawns task.

**Commit:** `feat(admin): add /api/admin/data/refresh dispatching by mode`

---

### Task 2.8: `<ModeBanner>` component

**Files:**
- Create: `apps/web/components/ModeBanner.tsx`
- Test: `apps/web/tests/unit/ModeBanner.spec.ts(x)`

**Component:**

```tsx
"use client";
import type { SystemMeta } from "@/lib/types";

export function ModeBanner({ system }: { system: SystemMeta }) {
  if (system.mode === "live" && system.status === "ready") return null;

  const bg = system.mode === "demo" ? "#FFF1E6" :
             system.status === "error" ? "#FEE2E2" :
             system.status === "generating" ? "#E0F2FE" : "#F1F5F9";

  const text =
    system.mode === "demo" ? "示例数据 · 未配置真实数据源（BRIEFALPHA_MODE=demo）" :
    system.status === "generating" ? "正在生成今日 brief…" :
    system.status === "stale" ? "显示昨日数据" :
    system.status === "error" ? "数据获取失败" : "";

  return (
    <div className="w-full px-4 py-2 text-[12px]" style={{ backgroundColor: bg }}>
      {text}
      {system.mode === "demo" && <a className="ml-2 underline" href="/README#switching-modes">如何切到真实管线</a>}
    </div>
  );
}
```

**Tests:** renders nothing for live+ready; renders demo text for mode=demo; renders generating text for status=generating.

**Commit:** `feat(web): add ModeBanner component`

---

### Task 2.9: Wire `<ModeBanner>` into page layout

**Files:**
- Modify: `apps/web/app/page.tsx` (or wherever TopBar is mounted)

Place above TopBar. Hydrate from `brief.system`.

**Commit:** `feat(web): mount ModeBanner above TopBar`

---

### Task 2.10: `<RefreshButton>` component + wire into TopBar

**Files:**
- Create: `apps/web/components/RefreshButton.tsx`
- Modify: `apps/web/components/TopBar.tsx`

**Component:**

```tsx
"use client";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function RefreshButton() {
  const [pending, startTransition] = useTransition();
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);
  const router = useRouter();

  return (
    <button
      onClick={() => startTransition(async () => {
        const res = await fetch("/api/admin/data/refresh", { method: "POST" });
        if (res.ok) {
          const json = await res.json();
          if (json.refreshed_at_hkt) setLastRefresh(json.refreshed_at_hkt);
          router.refresh();  // re-fetch server components
        }
      })}
      disabled={pending}
      className="rounded-md border px-3 py-1 text-[12px] font-medium disabled:opacity-50"
    >
      {pending ? "刷新中..." : lastRefresh ? `已刷新 ${lastRefresh}` : "刷新数据"}
    </button>
  );
}
```

Wire into `TopBar.tsx` next to existing controls.

**Test:** Vitest with mocked fetch — clicking calls endpoint, sets state.

**Commit:** `feat(web): add RefreshButton in TopBar`

---

### Task 2.11: README "切换模式" section

**Files:** `README.md`

Add section explaining `BRIEFALPHA_MODE`, default behavior, fail-fast cases, minimum live config checklist (per design §7 risk 1).

**Commit:** `docs(readme): add "切换模式" section`

---

## Phase 3 — Evidence link_kind + Behavior

### Task 3.1: Backend builder classifies URLs into `link_kind`

**Files:**
- Modify: `apps/api/briefalpha_api/pipeline/artifact.py` (`_build_evidence_card`, line ~309)
- Test: `apps/api/tests/unit/test_link_kind.py`

**Tests:**

```python
@pytest.mark.parametrize("url,expected", [
    ("https://www.sec.gov/Archives/edgar/foo", "external"),
    ("briefalpha://demo/ev_x", "internal_demo"),
    ("research://abc-123", "internal_research"),
    ("yfinance://NVDA", "internal_research"),
    ("", "unavailable"),
    (None, "unavailable"),
    ("#", "unavailable"),
])
def test_classify(url, expected):
    assert classify_link_kind(url) == expected
```

**Implementation:**

```python
def classify_link_kind(url: str | None) -> str:
    if not url or url == "#":
        return "unavailable"
    if url.startswith("briefalpha://demo/"):
        return "internal_demo"
    if url.startswith(("research://", "yfinance://")):
        return "internal_research"
    if url.startswith(("http://", "https://")):
        return "external"
    return "unavailable"
```

Apply in `_build_evidence_card`:

```python
url = ev.get("raw_source_url") or ev.get("source_link")
return {
    # ...
    "source_link": url,
    "link_kind": classify_link_kind(url),
    # ...
}
```

Apply same to supplementary sources builder.

**Commit:** `feat(artifact): classify evidence URLs into link_kind`

---

### Task 3.2: `<EvidenceCard>` link dispatch

**Files:**
- Modify: `apps/web/components/EvidenceCard.tsx`

**Logic:**

```tsx
function handleClick(e: React.MouseEvent, ev: EvidenceCardType) {
  if (ev.link_kind === "unavailable") {
    e.preventDefault();
    return;
  }
  if (ev.link_kind === "internal_demo") {
    e.preventDefault();
    openDemoModal(ev);
    return;
  }
  if (ev.link_kind === "internal_research") {
    e.preventDefault();
    router.push(`/research/${parseResearchId(ev.source_link!)}`);
    return;
  }
  // external — let browser open in new tab
}
```

For `unavailable`, render with `cursor-not-allowed` styling and a tooltip "原文链接不可用".

**Test:** Vitest snapshot per kind; `internal_demo` does not navigate.

**Commit:** `feat(web): EvidenceCard dispatches by link_kind`

---

### Task 3.3: `<DemoEvidenceModal>` component

**Files:**
- Create: `apps/web/components/DemoEvidenceModal.tsx`
- Modify: `apps/web/components/DrawerHost.tsx` (mount the modal portal)

Modal shows: "示例 evidence", evidence quote in full, source label, and a footnote "本条 evidence 来自示例 brief，未连接真实数据源。"

**Commit:** `feat(web): add DemoEvidenceModal for internal_demo links`

---

## Phase 4 — QA Degradation + Demo Keyword Table

### Task 4.1: `failure_reason` enum on QA response

**Files:**
- Modify: `apps/api/briefalpha_api/qa/service.py`
- Modify: `apps/api/briefalpha_api/routers/qa.py`

Update `QaServiceResult` to allow new `failure_reason` values: `llm_unconfigured`, `evidence_insufficient`, `out_of_scope`, `empty_question`, `demo_mode_no_match`, `demo_mode_prebaked`. Map old branches accordingly.

**Test:** Each branch returns expected `failure_reason`.

**Commit:** `refactor(qa): structured failure_reason values`

---

### Task 4.2: Demo keyword response table

**Files:**
- Create: `apps/api/briefalpha_api/qa/demo_responses.py`
- Test: `apps/api/tests/unit/test_demo_responses.py`

```python
DEMO_TABLE: list[tuple[list[str], str]] = [
    (["hi", "你好", "hello"], "👋 这是 BriefAlpha 的 demo 模式。试试问：\"今天有哪些重点研判？\""),
    (["总结", "摘要", "今日"], "今日重点：(1) 英伟达 Q1 数据中心指引下调 8-10%，触发待复核；(2) 腾讯扩大回购 50% 支撑港股互联网；(3) Fed Williams 暗示年内或再加息，TLT 久期承压。"),
    (["nvda", "英伟达"], "NVDA 18% 是核心持仓。盘后指引下调拖累约 6%，路透/彭博对幅度报告分歧（8% vs 10%），所以这条研判被标为 ⚠ 待复核。"),
    (["腾讯", "0700", "tencent"], "0700.HK 15% 持仓。回购授权从 1000 亿提到 1500 亿港元，可作为港股互联网 thesis 的轻度正向信号。"),
    (["fed", "联储", "加息"], "Williams 在 NABE 会议措辞 'mildly restrictive'，市场理解为年内仍可能加息一次，对 TLT 等长久期资产形成压力。"),
    (["待复核", "复核"], "「⚠ 待复核」表示此研判触发了人工复核条件——常见原因：来源对关键数字分歧、组合关联不明、阈值穿越。点击 chip 可看具体原因，并标记为已审。"),
    (["来源", "证据"], "demo 模式下所有 evidence 链接以 'briefalpha://demo/' 开头，点击会弹窗显示完整引文，不会跳转外网。"),
]

def lookup(question: str) -> str | None:
    q = question.lower()
    for keywords, answer in DEMO_TABLE:
        if any(kw.lower() in q for kw in keywords):
            return answer
    return None
```

**Tests:** lookup hits and misses.

**Commit:** `feat(qa): add demo keyword response table`

---

### Task 4.3: QA service dispatches by mode

**Files:**
- Modify: `apps/api/briefalpha_api/qa/service.py`
- Modify: `apps/api/briefalpha_api/routers/qa.py` (pass mode in)

**Logic at top of `run_qa`:**

```python
if not question.strip():
    return QaServiceResult(answer="请输入与今日 brief 相关的问题。", failure_reason="empty_question", validation_passed=True)

if mode == "demo":
    from briefalpha_api.qa.demo_responses import lookup
    answer = lookup(question)
    if answer:
        return QaServiceResult(answer=answer, failure_reason="demo_mode_prebaked", validation_passed=True)
    return QaServiceResult(
        answer="当前为 demo 模式（未配置 LLM provider），仅支持基于示例 brief 的预设问题。试试 \"总结今日\"、\"NVDA\"、\"待复核\"。",
        failure_reason="demo_mode_no_match",
        validation_passed=True,
    )

# existing live path...
```

Also add: detect conservative provider fallback → return `failure_reason="llm_unconfigured"` with friendlier text.

**Tests:** demo "hi" → prebaked; demo "asdf" → no_match; live without LLM → llm_unconfigured.

**Commit:** `feat(qa): dispatch by mode with prebaked demo answers`

---

### Task 4.4: `<LocalQaInput>` renders friendly text per `failure_reason`

**Files:**
- Modify: `apps/web/components/LocalQaInput.tsx`

Map each `failure_reason` to user-facing copy. Add `<DemoAnswerBadge>` next to answers with `failure_reason === "demo_mode_prebaked"`.

**Tests:** snapshot per branch.

**Commit:** `feat(web): LocalQaInput renders per failure_reason with 示例回答 badge`

---

## Phase 5 — Review Structured + Popup + Persistence

### Task 5.1: SQLAlchemy `ReviewOverride` model

**Files:**
- Modify: `apps/api/briefalpha_api/db/models.py`
- Test: `apps/api/tests/unit/test_review_override_model.py`

```python
class ReviewOverride(Base):
    __tablename__ = "review_overrides"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brief_id: Mapped[str] = mapped_column(index=True)
    judgement_id: Mapped[str]
    status: Mapped[str]  # "open" | "reviewed"
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    note: Mapped[str] = mapped_column(default="")
    __table_args__ = (UniqueConstraint("brief_id", "judgement_id"),)
```

**Test:** insert + query roundtrip.

**Commit:** `feat(db): add ReviewOverride model`

---

### Task 5.2: Migration / `create_all` ensures table exists

If the project uses `Base.metadata.create_all` on startup, no migration needed. If it uses Alembic, add a migration.

Check `db/__init__.py` to confirm.

**Commit (if needed):** `feat(db): migration for review_overrides`

---

### Task 5.3: `POST /api/review/{judgement_id}` endpoint

**Files:**
- Create or modify: `apps/api/briefalpha_api/routers/review.py`
- Modify: `apps/api/briefalpha_api/main.py` (register router)
- Test: `apps/api/tests/integration/test_review_endpoint.py`

**Endpoint:**

```python
@router.post("/review/{judgement_id}")
async def mark_reviewed(
    judgement_id: str,
    body: ReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    # upsert
    existing = await session.execute(
        select(ReviewOverride).where(
            ReviewOverride.brief_id == body.brief_id,
            ReviewOverride.judgement_id == judgement_id,
        )
    )
    obj = existing.scalar_one_or_none()
    if obj is None:
        obj = ReviewOverride(brief_id=body.brief_id, judgement_id=judgement_id, status=body.status, note=body.note)
        session.add(obj)
    else:
        obj.status = body.status
        obj.note = body.note
    if body.status == "reviewed":
        obj.reviewed_at = datetime.now(tz=ZoneInfo("Asia/Hong_Kong"))
    await session.commit()
    return {"status": "ok", "judgement_id": judgement_id, "review_status": obj.status}
```

`ReviewRequest`: pydantic with `brief_id`, `status`, `note`.

**Tests:** create open → upgrade to reviewed → fetch.

**Commit:** `feat(api): POST /api/review/{judgement_id} for review status persistence`

---

### Task 5.4: Brief assembly merges review_overrides into judgements

**Files:** `apps/api/briefalpha_api/pipeline/artifact.py` (or `routers/brief.py` after artifact build)

After judgements built, fetch all `ReviewOverride` for `brief_id` and merge into each judgement's `review` field (status from override wins).

**Test:** judgement with override `status=reviewed` shows in response.

**Commit:** `feat(brief): merge review_overrides into response`

---

### Task 5.5: `<ReviewModal>` component

**Files:**
- Create: `apps/web/components/ReviewModal.tsx`
- Modify: `apps/web/components/JudgementList.tsx` or `DrawerHost.tsx` (open on chip click)

Shows: reason (mapped to human Chinese), note, "我已审阅" button. On click → POST /api/review/{id} → router.refresh().

Reason map:
- `source_conflict` → "来源对关键数字分歧"
- `portfolio_uncertain` → "组合关联不确定"
- `threshold_breach` → "数据穿越人工阈值"
- `data_gap` → "数据缺口或质量问题"

**Tests:** Vitest snapshot per reason.

**Commit:** `feat(web): add ReviewModal for review chip`

---

### Task 5.6: Make review chip clickable in JudgementList

**Files:** `apps/web/components/JudgementList.tsx`

Find where `level_label` / `⚠ 待复核` text renders. Wrap in `<button>` that opens `<ReviewModal>` for the judgement.

**Commit:** `feat(web): review chip clickable opens ReviewModal`

---

## Phase 6 — Macro Pulse + Playbook Evidence + Evidence Trail Drawer

### Task 6.1: `<MacroPulseExpanded>` component

**Files:**
- Create: `apps/web/components/MacroPulseExpanded.tsx`

Renders 8 `MacroPulseItem` rows. Each row: name (left), value/delta (mid), threshold (right), small status dot.

**Commit:** `feat(web): add MacroPulseExpanded`

---

### Task 6.2: Wire collapse/expand toggle

**Files:**
- Modify: `apps/web/components/MacroPulseCollapsed.tsx`

Replace empty `onClick` with state toggle. When expanded, render `<MacroPulseExpanded items={items} />`; pass `items` from parent.

**Test:** Click toggles expanded state; renders 8 rows.

**Commit:** `feat(web): macro pulse expand/collapse`

---

### Task 6.3: TodayPlaybook renders related evidence on event expand

**Files:**
- Modify: `apps/web/components/TodayPlaybook.tsx`

Add expand state per event. When expanded, find evidence by `related_evidence_ids` from the brief's flat evidence pool, render in a compact list under the event.

Helper to resolve: walk `brief.judgements[*].evidence` once at top, build `Map<evidence_id, EvidenceCard>`.

**Test:** Snapshot with mocked brief showing event expansion.

**Commit:** `feat(web): TodayPlaybook expands events with evidence citations`

---

### Task 6.4: `<EvidenceTrailDrawer>` component

**Files:**
- Create: `apps/web/components/EvidenceTrailDrawer.tsx`
- Modify: `apps/web/components/DeepRead.tsx`

Drawer lists all `evidence_trail` entries. Filter by `source_tier` (chips top of drawer).

In `DeepRead.tsx`, find "查看全部" button (currently no handler) — wire to open drawer.

**Test:** Click opens drawer; filter narrows list.

**Commit:** `feat(web): EvidenceTrailDrawer + wire 查看全部`

---

### Task 6.5: Backend `GET /api/evidence/trail?brief_id=...` (live mode)

**Files:** Modify or create `apps/api/briefalpha_api/routers/evidence.py`

Live mode: query DB for all evidence rows for the brief; return ordered by `published_at DESC`. Demo mode: read from fixture's `deep_read.evidence_trail` (already fixture-provided).

**Tests:** Both modes.

**Commit:** `feat(api): GET /api/evidence/trail`

---

## Phase 7 — Source Health Real/Demo Split

### Task 7.1: SourceHealth aggregator real-mode wiring

**Files:**
- Modify: `apps/api/briefalpha_api/audit/source_health_aggregator.py`

Live mode: read ingestion runner status (already exists per git status: `audit/source_health_aggregator.py`), count actual research uploads from DB.

Demo mode: return `get_demo_source_health()` with `is_demo=True` on every row.

**Tests:** Mock ingestion adapter status → asserts row counts.

**Commit:** `feat(audit): source health respects mode`

---

### Task 7.2: SourceHealth UI renders `(示例)` suffix

**Files:**
- Modify: `apps/web/components/Footer.tsx` or wherever source health renders

Append " (示例)" to `detail` when `row.is_demo === true`.

**Commit:** `feat(web): source health rows display 示例 suffix in demo`

---

## Phase 8 — Watchlist Copy + Tooltip

### Task 8.1: Update fixture watchlist text + tooltip component

**Files:**
- Modify: `apps/api/briefalpha_api/fixtures/brief.py` and `apps/web/lib/fixtures.ts`
- Modify: `apps/web/components/PortfolioTreemap.tsx`

Change `watchlist_summary` to: `"市场参照（非持仓）：AMD · GOOGL · 1810.HK"`.

Add small `(?)` icon next to "市场参照" with tooltip: `"非组合持仓但持续关注的标的，用作市场背景参考。点击编辑（即将上线）。"`

**Commit:** `feat(web): clarify watchlist copy with tooltip`

---

## Phase 9 — Verification + E2E + Wrap

### Task 9.1: Playwright happy-path E2E

**Files:**
- Create or modify: `apps/web/tests/e2e/trust_loop.spec.ts`

Steps in test:
1. Start API + web in demo mode
2. Visit `/`
3. Assert ModeBanner contains "示例数据"
4. Click RefreshButton → assert "已刷新" or rotation timestamp visible
5. Click `⚠ 待复核` chip → assert ReviewModal visible → click "我已审阅" → modal closes, chip status updates
6. Click DeepRead "查看全部" → assert EvidenceTrailDrawer visible
7. Type "hi" in QA → assert response contains "👋" + "示例回答" badge

**Commit:** `test(e2e): trust loop happy path`

---

### Task 9.2: Manual verification checklist (per design §8)

Run through, screenshot, and stash in `docs/screenshots/2026-04-26/`:
- `BRIEFALPHA_MODE=demo` clone-and-run
- `BRIEFALPHA_MODE=live` with full keys
- All 9 issues per design table

**Commit:** `docs: verification screenshots for trust-loop release`

---

### Task 9.3: PR / submission summary

Open a PR (or compose interview submission writeup) referencing both design and implementation docs. Use the verification checklist as PR description.

---

## Plan Hygiene

- Each Task's tests should be **specific** to the contract being added — don't write one giant test file
- Commit after each task; don't batch
- After each phase, run full suite: `pnpm test && pytest`. Fix regressions before moving to the next phase
- If a task expands beyond 5 minutes' actual work, **stop and split it** (it's no longer bite-sized)

## Worktree Note

The project's git status currently shows ~25 modified files and many untracked. Recommend creating a worktree to isolate this work:

```
git worktree add ../briefalpha-trust-loop -b feature/trust-loop
cd ../briefalpha-trust-loop
```

(Or skip if the modified files belong to the same in-flight stream and you'd rather rebase later.)

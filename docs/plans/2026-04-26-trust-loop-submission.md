# Trust Loop & 9-Issue UX Fix — Submission Summary

**Branch:** `main` (commits `0167c5e..HEAD`)
**Design:** `docs/plans/2026-04-26-trust-loop-and-ux-fix-design.md`
**Implementation plan:** `docs/plans/2026-04-26-trust-loop-and-ux-fix-implementation.md`
**Verification checklist:** `docs/plans/2026-04-26-trust-loop-verification.md`

---

## 1. Problem statement

The MVP looked complete on the surface but **lied about the data being shown**:

- `/api/brief/today` cache miss → silently returned a hand-curated demo fixture stamped with `stale=true`.
- The web client `getBriefToday()` failure path → silently imported the fixture again.
- This made fixture content indistinguishable from live pipeline output, except for a small chip — fatal for an evidence-grounded family-office brief whose entire value proposition is auditability.

User feedback uncovered nine concrete UX issues, but they were all symptoms of the same root cause: **the implicit fixture fallback masquerading as real data**. Behind that sat eight smaller gaps (no refresh, dead links, ambiguous "待复核" chip, blanket QA error, non-expandable macro pulse, unsourced events, broken "查看全部", masquerading source health, cryptic watchlist copy).

## 2. Solution — explicit two-mode architecture

| | Before | After |
|---|---|---|
| **Mode signaling** | implicit, single `stale: bool` | explicit `BRIEFALPHA_MODE = demo \| live` (manual switch, default demo) + `Brief.system.{mode, status, generated_at, last_refreshed_at, data_quality}` envelope on every response |
| **Cache miss (live)** | returns fixture + stale=true | returns empty skeleton + `status: "generating"` + `data_quality: "unavailable"` — never fixture |
| **Cache miss (demo)** | returns fixture + stale=true | returns fixture + `system.{mode: "demo", data_quality: "fixture"}` — explicitly labeled |
| **Web client failures** | silent fallback to fixture | error propagates; page can render explicit error state |
| **Live startup** | no preconditions check | fail-fast on missing LLM key / SEC user agent — exit 1 with explicit log |

A persistent `<ModeBanner>` reads `Brief.system` and shows the user which mode is active and what the data status is. There is no path where the user sees fixture data without an explicit, persistent label.

## 3. The 9 reported issues — fix matrix

| # | Issue | Fix | Where |
|---|---|---|---|
| 1 | No way to refresh data | TopBar `<RefreshButton>` + `POST /api/admin/data/refresh` mode-dispatched | Tasks 2.7, 2.10 |
| 2 | Watchlist copy 不知所云 | Section renamed to "市场参照（非持仓）" + `(?)` tooltip | Task 8.1 |
| 3 | Evidence links 404 | `link_kind: external \| internal_demo \| internal_research \| unavailable` enum on every evidence/supplementary; `<EvidenceCard>` dispatches by kind; `<DemoEvidenceModal>` for in-app links | Tasks 3.1, 3.2, 3.3 |
| 4 | "⚠ 待复核" 含义不明 | `requires_review: bool` upgraded to structured `review: {reason, note, status, reviewed_at} \| null`; chip is clickable → `<ReviewModal>` with reason translated to Chinese; "我已审阅" persists via `POST /api/review/{id}` to SQLite | Tasks 1.7, 5.1-5.6 |
| 5 | QA always returns "无法生成可信回答" | `failure_reason` enum (`empty_question / evidence_insufficient / out_of_scope / demo_mode_no_match / demo_mode_prebaked / llm_unconfigured / brief_expired`); demo-mode keyword response table for prebaked answers; `<DemoAnswerBadge>` "示例回答" surfaces in UI | Tasks 4.1-4.4 |
| 6 | 宏观脉搏 不能展开 | New `<MacroPulseExpanded>` component; `Brief.macro_pulse: MacroPulseItem[]` on the wire; toggle wired into `<MacroPulseCollapsed>` | Tasks 6.1, 6.2 |
| 7 | 观察事件 无来源 | `PlaybookEvent.related_evidence_ids: string[]` added; events expand inline to show their related EvidenceCard items | Task 6.3 |
| 8 | 证据轨迹 "查看全部" 无反应 | New `<EvidenceTrailDrawer>` + `GET /api/evidence/trail?brief_id=...` endpoint with source_tier filter chips | Tasks 6.4, 6.5 |
| 9 | source health "1 个上传" 假数据 | `SourceHealthRow.is_demo: boolean` flag; aggregator stamps `is_demo: false`, fixture stamps `is_demo: true`; UI appends "(示例)" suffix when `is_demo === true`; live mode + empty DB returns `overall: "failed"` instead of falling back to fixture | Tasks 7.1, 7.2 |

## 4. Engineering principles applied

- **No silent fallbacks.** Every degradation is explicit and labeled. Two layers of fixture fallback (backend cache miss + web client catch) both removed in their non-demo paths.
- **Single signal for mode/status.** Banner / QA / SourceHealth / RefreshButton all read from `Brief.system.data_quality` (one of `fixture | live | partial | unavailable`). No component infers mode independently.
- **Backwards-compatible deltas.** `requires_review` boolean and `stale` boolean are kept on the wire for one release; the artifact builder derives `review` from `requires_review` so legacy LLM output still works.
- **TDD per task.** 130 backend tests (was 41 baseline → +89), 9 web SSR specs.
- **No localStorage.** Review state persists via `POST /api/review/{id}` → SQLite, respecting the project's no-Zustand-persist rule.
- **YAGNI on auth.** Refresh + review endpoints unprotected for MVP, matching the existing `/admin/brief/regenerate` precedent. Multi-user hardening explicitly deferred.

## 5. Test summary

| Suite | Count | Status |
|---|---|---|
| API unit + integration | 130 | green |
| Web SSR unit (vitest-style via `tsx + node:assert`) | 9 spec files | green |
| Web typecheck | — | 0 errors |
| Web E2E (`trust_loop.spec.ts`) | 6 cases | requires running stack to validate |

## 6. Commit timeline (high level)

```
0167c5e docs(plans): design
eef7dd3 docs(plans): implementation plan
60f72f9 chore: snapshot in-flight platform work pre trust-loop  (baseline)

Phase 1 — Schema foundation
  d40e6b6 feat(schemas): add SystemMeta envelope
  9467398 refactor(pipeline): un-eager pipeline package init
  2376016 feat(schemas): add MacroPulseItem
  20390e9 feat(schemas): add ReviewMeta and LinkKind
  2fa10d9 style(tests): hoist typing.get_args import
  51f56c8 feat(types): mirror new Brief/Judgement/Evidence schema
  98c0451 feat(fixtures): populate new schema fields self-consistently
  e8c6e6e feat(fixtures-web): mirror new fixture fields
  d35f31d feat(artifact): derive review from requires_review for back-compat
  bf44bfb style(tests): drop unused pytest import

Phase 2 — Mode + Banner + Refresh + README
  d1fa4d7 feat(config): BRIEFALPHA_MODE resolution
  4292bae feat(config): live-mode fail-fast preconditions
  f36a282 fix(config): anchor live preconditions to SECRETS_DIR
  928e3ca feat(startup): fail-fast + expose mode on app.state
  5ef362f feat(brief): mode-aware response with system envelope
  f427ebb fix(brief): live skeleton audit_mode follows settings
  fc1540c feat(web-api): drop silent fixture fallback in client
  cce06a4 chore(web): wire api.spec into test:unit
  bd303fd feat(admin): /api/admin/data/refresh dispatching by mode
  71c97d7 feat(web): ModeBanner + RefreshButton trust-loop UI
  a7ddaf1 docs(readme): add 切换模式 section

Phase 3 — Evidence link_kind + behavior
  2b00978 feat(artifact): classify evidence URLs into link_kind
  0aa3f53 feat(web): EvidenceCard dispatches by link_kind; DemoEvidenceModal

Phase 4 — QA degradation
  33cf354 feat(qa): mode-aware dispatch with demo prebaked answers
  5587674 feat(web): LocalQaInput per-failure_reason rendering + 示例回答 badge
  7db015a fix(types): add brief_expired to QaResponse.failure_reason

Phase 5 — Review structured + popup + persistence
  b928fec feat(review): persistence model + endpoint + brief merge
  42015ff feat(web): clickable review chip + ReviewModal with persistence

Phase 6 — Macro Pulse + Playbook + Evidence Trail
  d5d2fc5 feat(web): MacroPulse expand + TodayPlaybook event evidence
  6e0672a feat(evidence): trail drawer + GET /api/evidence/trail

Phase 7 — Source Health real/demo split
  6eae316 feat(source-health): mode-aware response + 示例 suffix

Phase 8 — Watchlist clarity
  c8a6428 feat(web): clarify watchlist as 市场参照 with tooltip
```

## 7. Reviewer onboarding (5-minute path)

```bash
git clone <repo>
cd Family-Office-Morning-Brief
pnpm install
cd apps/api && uv sync && cd ../..
make init-secrets
make db-migrate

# Three terminals:
make dev-redis    # optional; or set BRIEFALPHA_DISABLE_REDIS=1
make dev-api      # default BRIEFALPHA_MODE=demo
make dev-web

# Visit http://localhost:3000
```

That's it. No keys configured = orange demo banner + "(示例)" labels on all data. Click around per `docs/plans/2026-04-26-trust-loop-verification.md` §B.

To run live: `export BRIEFALPHA_MODE=live ANTHROPIC_API_KEY=sk-ant-... SEC_EDGAR_USER_AGENT="App/1.0 you@example.com"` and re-`make dev-api`. README has details.

## 8. What's deliberately deferred

- Multi-user auth on review/refresh endpoints (single-user MVP).
- Macro pulse indicator configuration UI (spec only the read path).
- Watchlist editing UI (spec only the read path; tooltip says "即将上线").
- Replacing `level_label` string-replace hack with backend-emitted base label + chip-rendered status badge.
- Migrating `requires_review` and `stale` legacy fields away after one release.

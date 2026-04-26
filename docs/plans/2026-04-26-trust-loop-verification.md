# Trust Loop & 9-Issue UX Fix — Verification Checklist

> Companion to `2026-04-26-trust-loop-and-ux-fix-design.md` and
> `2026-04-26-trust-loop-and-ux-fix-implementation.md`. Run through this
> end-to-end before submitting / merging.

---

## A. Test suites

| Suite | Command | Expected |
|---|---|---|
| API unit + integration | `cd apps/api && uv run pytest -x` | **130 passed** (or higher if you added more after 2026-04-26) |
| Web unit (SSR) | `cd apps/web && pnpm test:unit` | 9 spec files all OK (analytics, api, mode-banner, refresh-button, evidence-card-dispatch, local-qa-input, review-modal, macro-playbook, evidence-trail-drawer) |
| Web typecheck | `cd apps/web && pnpm typecheck` | 0 errors |
| Web E2E (trust loop) | `cd apps/web && pnpm test:e2e -- trust_loop.spec.ts` | All 6 cases pass; requires API + web servers running, demo mode |
| Web E2E (full) | `cd apps/web && pnpm test:e2e` | Existing `main.spec.ts` + new `trust_loop.spec.ts` all green |

---

## B. Demo mode end-to-end (clone-and-run)

> Goal: prove the interview reviewer can `git clone` and run with **zero
> API key configuration**.

### Setup (one-time)

```bash
pnpm install
cd apps/api && uv sync && cd ../..
make init-secrets        # generates placeholder secrets, OK to leave
make db-migrate
```

### Run

In three terminals:

```bash
make dev-redis           # optional; can also export BRIEFALPHA_DISABLE_REDIS=1
make dev-api             # starts in BRIEFALPHA_MODE=demo by default
make dev-web
```

Open http://localhost:3000 .

### Verify each fix

| # | Original issue | Verification |
|---|---|---|
| 1 | "数据不可用，没地方刷新" | TopBar has a "刷新数据" button. Click it → button label changes to "已刷新 HH:MM". |
| 2 | watchlist text 不知所云 | Section reads "市场参照（非持仓）" with a `(?)` tooltip. Hover the (?) to see the explanation. |
| 3 | drawer evidence 链接全部 404 | In a judgement drawer, click any evidence card. It opens a modal with the quote + footer "示例 evidence · 来自 fixture，不连接外网" — never a browser tab. |
| 4 | "⚠ 待复核" 含义不明 | Click the "⚠ 待复核" chip on the j1 (NVDA) row. ReviewModal shows reason "来源对关键数字分歧", note "路透 8% vs 彭博 10%—下调幅度分歧", and a "我已审阅" button. Click it → chip becomes "✓ 已审"; refresh page → status persists. |
| 5 | QA 一刀切错误 | In a judgement drawer, type "hi" → demo prebaked greeting + 示例回答 badge. Type "asdfqwerty" → friendly "no match" message, no error. |
| 6 | 宏观脉搏不能展开 | Click "宏观脉搏 · 8 项指标" row → 8 indicator rows expand below with status dots. |
| 7 | 观察事件无来源 | In "今日观察事件" section, click "查看 N 条依据" under any event → expands to show the related EvidenceCard items inline. |
| 8 | 证据轨迹查看全部无反应 | In DeepRead section, click "查看全部 N 条原文" → right-side drawer opens listing all trail items, with source_tier filter chips. |
| 9 | source health 假数据 | DeepRead's 数据源健康 panel shows each row's detail with an orange "(示例)" suffix. |

### Trust loop signals (the meta-fix)

- [ ] Orange ModeBanner with text "示例数据 · 未配置真实数据源（BRIEFALPHA_MODE=demo）" sits above the TopBar.
- [ ] Banner has a working link "如何切到真实管线" pointing to README's #switching-modes anchor.
- [ ] No real-looking number contradicts the demo nature anywhere.

---

## C. Live mode end-to-end (real pipeline)

> Goal: prove `BRIEFALPHA_MODE=live` works for daily personal use.

### Setup

```bash
export BRIEFALPHA_MODE=live
export ANTHROPIC_API_KEY=sk-ant-...     # OR OPENAI_API_KEY
export SEC_EDGAR_USER_AGENT="BriefAlpha/dev your.email@example.com"
```

### Fail-fast verification (do this first)

Without setting any of the above:

```bash
BRIEFALPHA_MODE=live make dev-api
```

Expected: API exits within ~1 second with an ERROR log listing each
missing precondition. Specifically:

```
ERROR: Live mode preconditions failed:
  - No LLM provider key configured. ...
  - SEC_EDGAR_USER_AGENT must be set in live mode ...
```

### Live operation verification

After exporting the env vars and starting the API:

- [ ] Banner is **gone** (live + ready hides ModeBanner).
- [ ] First request to `/api/brief/today` returns `system.status="generating"` with empty `judgements`/`base_case` (skeleton). The orange "正在生成今日 brief…" banner is visible.
- [ ] After ~30-60 seconds the brief generation completes; the next page load shows real data with `system.status="ready"` and `system.data_quality="live"`.
- [ ] Clicking "刷新数据" returns `{status: "queued", brief_id}`; banner shows generating; another ~30-60s and live data appears.
- [ ] DeepRead's 数据源健康 panel does NOT show "(示例)" on any row.
- [ ] Evidence card source_link values are real (`https://www.sec.gov/...`, `https://www1.hkexnews.hk/...`) and click → new tab → real article.
- [ ] QA box: typing a real question returns LLM-generated answer with cited evidence, no 示例回答 badge.

---

## D. Screenshots to capture (for submission)

Save into `docs/screenshots/2026-04-26/`:

1. `01-demo-banner.png` — full-page screenshot of demo mode home, ModeBanner visible.
2. `02-refresh-receipt.png` — TopBar after clicking RefreshButton, label "已刷新 HH:MM" visible.
3. `03-review-modal-open.png` — ReviewModal open showing reason/note/button.
4. `04-review-chip-resolved.png` — j1 row chip showing "✓ 已审" after acknowledgement.
5. `05-evidence-modal.png` — DemoEvidenceModal open from clicking an evidence card.
6. `06-macro-pulse-expanded.png` — Macro pulse 8-item grid expanded.
7. `07-playbook-event-evidence.png` — TodayPlaybook event expanded to show its related EvidenceCard.
8. `08-evidence-trail-drawer.png` — EvidenceTrailDrawer open with filter chips.
9. `09-qa-prebaked.png` — LocalQaInput with "示例回答" badge after typing "hi".
10. `10-source-health-suffix.png` — DeepRead source-health panel showing "(示例)" suffixes.
11. `11-live-fail-fast.png` — terminal screenshot of `BRIEFALPHA_MODE=live` API exiting on missing preconditions.
12. `12-live-success.png` — full-page screenshot of live mode home with no banner, real data, real source-health.

---

## E. Final sanity (before tagging)

- [ ] `git log --oneline main..HEAD` reads as a clean narrative (design → impl plan → baseline → 9 phases of feat/fix commits).
- [ ] No commit on the trust-loop range touches `data/.secrets/*` or `dump.rdb`.
- [ ] Both design + implementation plan markdown files committed under `docs/plans/`.
- [ ] README "切换模式" section renders correctly on GitHub (preview the markdown).
- [ ] `BRIEFALPHA_MODE` is documented in `.env.example` (verify or add).

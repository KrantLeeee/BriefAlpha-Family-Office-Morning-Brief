# BriefAlpha admin runbook

## 1. Universe maintenance

- The privacy-safe universe rebuild fires at 06:50 HKT on weekdays. To
  inspect the current universe, hit `GET /api/portfolio` (admin token
  required) and check `bucket_summary`.
- If `cold_start_passed` is `false`, `pipeline.no_direct_portfolio_link_fallback`
  takes over: brief is generated but `portfolio_linkage = 0.3` for every
  judgement. Cause is almost always: too few holdings (< k=3) and no
  decoy bucket viable.
- To temporarily widen coverage, edit `packages/config/ticker_sector_overrides.yml`
  and add the ticker with the desired `sector` / `asset_class`.

## 2. company_alias_zh maintenance

- Edit `packages/config/company_alias_zh.yml`. Each ticker may carry any
  number of Chinese / English / abbreviated name variants — every variant
  shares the same alias once the next brief is generated.
- After editing, restart the API process so the cached YAML reload picks
  up changes.
- Admin diagnostics page surfaces tickers with `< 1` Chinese alias as a
  warning; aim to keep that count at 0.

## 3. audit_mode switching

`audit_mode` defaults to `demo`. Switching to `compliance`:

```bash
curl -X POST http://localhost:8000/api/admin/audit_mode \
  -H "Authorization: Bearer $(cat data/.secrets/admin_token)" \
  -d '{"mode": "compliance", "reason": "regulatory request 2026-Q2"}'
```

- Existing `demo` records keep their `audit_mode = demo` tag — the change
  is **not retroactive**.
- The switch endpoint requires confirmation + reason (logged to
  `audit_log`).

## 4. conservative_brief triggers — debug path

If `/admin/diagnostics` reports `conservative_brief_triggered_rate > 10%`:

1. Check `/api/source-health` — is news / official tier `failed`?
   If yes, fix that source first; conservative will recover next day.
2. Open `audit_log` filtered to `failure_state LIKE 'accuracy:%'`. If the
   reasons cluster around `quote_span:not_locatable`, recent prompt or
   anonymization changes likely shifted segment offsets.
3. Run `python -m tests.golden.runner` to re-baseline. A regression on
   `citation_locatable_rate` or `numbers_consistent_rate` is the most
   common cause.

## 5. PDF lifecycle

- `research_pdfs/{user_id}/{file_id}.pdf` is encrypted at rest.
- Default retention: 7 days. Cron (`scheduler.jobs._cleanup_pdf`) sweeps
  expired files and writes a `partial_failure` entry on the corresponding
  research_job so the user sees `原 PDF 已删除` in the drawer.
- `DELETE /api/research/{file_id}` purges the file + chunks immediately;
  it does **not** auto re-run the pipeline.

## 6. alias_map daily purge

- Cron at 16:00 HKT: `scheduler.jobs._purge_alias_maps`. If purge fails
  (file permissions / disk full), `audit_log.failure_state` records the
  reason and an admin alert fires.
- Recovery: free disk space, run `python -c "from briefalpha_api.anonymization import delete_alias_map; delete_alias_map('YYYY-MM-DD')"`
  manually.

# BriefAlpha

Family-office morning brief MVP — produces an evidence-grounded, citation-traceable, minimum-disclosure morning brief by 08:30 HKT.

> Source of truth for visual design: `docs/Designs/BriefAlpha.pen` (Chinese frames `fFOSV`, `uOtTm`, `I4Qnp`, `Nh2S4`).
> Source of truth for behavior: `openspec/changes/build-briefalpha-mvp/`.

## Structure

```
apps/
  api/        FastAPI + APScheduler + SQLAlchemy + SQLite (FTS5) + Redis
  web/        Next.js 14 App Router + TS + Tailwind + react-pdf + Zustand
packages/
  prompts/    JSON LLM prompt templates with template_version
  config/     Shared YAML configs (sector overrides, alias_zh, data sources)
data/         Runtime data (gitignored: SQLite DB, encrypted alias_maps, PDFs)
scripts/      Dev / ops scripts (init_secrets, backups)
tests/        Cross-repo integration + golden tests
openspec/     Spec-driven workflow (proposals, designs, capabilities, tasks)
docs/         Designs (.pen) and reference docs
```

## Prerequisites

- Python 3.11
- Node.js 20+ (with [pnpm](https://pnpm.io/))
- Redis 7+ (`brew install redis` or Docker)
- [uv](https://github.com/astral-sh/uv) (recommended for Python)

## First-time setup

```bash
# 1. Install JS dependencies
pnpm install

# 2. Install Python dependencies
cd apps/api && uv sync && cd ../..

# 3. Generate local secrets (alias_key, admin_token, llm_api_keys.json placeholder)
make init-secrets

# 4. Apply database migrations
make db-migrate

# 5. (optional but recommended) Seed a demo portfolio so /api/brief/today
#    has something to anonymize over the privacy-safe universe.
python scripts/seed_demo_portfolio.py
```

After step 3, edit `data/.secrets/llm_api_keys.json` and replace the
`replace-me` strings with real provider keys. Without real keys, the
backend keeps running but every LLM call returns a deterministic stub
response (the rest of the pipeline + validators + audit log still
exercise correctly — useful for debugging).

For PDF/image captioning, set `vision_openai` to an OpenAI API key. If
`vision_openai` is omitted, the backend falls back to the regular `openai`
key. `vision_anthropic` may remain `replace-me` unless you re-enable the
Anthropic vision route.

`data/.secrets/admin_token` is a 64-char hex string. Pass it as
`Authorization: Bearer <token>` to access `/api/portfolio` and any
`/api/admin/*` endpoint.

## Run locally

In three separate terminals:

```bash
make dev-redis    # Redis on :6379
make dev-api      # FastAPI on :8000 (also starts APScheduler cron jobs)
make dev-web      # Next.js on :3000
```

If you don't have Redis available, set `BRIEFALPHA_DISABLE_REDIS=1` —
the cache layer degrades to no-op (every request triggers a fresh DB
read or fallback to fixture data). To skip the cron scheduler too set
`BRIEFALPHA_DISABLE_SCHEDULER=1`.

<a id="switching-modes"></a>
## Switching modes (demo / live)

BriefAlpha runs in one of two modes, selected by the `BRIEFALPHA_MODE`
environment variable. The mode is **manual** — there is no
auto-detection, on purpose.

| Mode | Default | What it does | When to use |
|---|---|---|---|
| `demo` | yes | Serves a hand-curated fixture brief. Every "demo" surface is explicitly labeled (banner, source-health `(示例)`, evidence links open an internal modal). No external API calls. | First-time setup, design preview, demo to a reviewer without configuring keys. |
| `live` | opt-in | Runs the real ingestion → brief → QA pipeline. Fail-fasts on startup if required preconditions are missing. | Daily personal use after configuring keys. |

### Default behavior (no config needed)

```bash
make dev-api    # equivalent to BRIEFALPHA_MODE=demo
```

The API starts with `BRIEFALPHA_MODE=demo`. The web app shows a persistent
orange banner: "示例数据 · 未配置真实数据源". `/api/brief/today` returns
the fixture (with `system.data_quality = "fixture"` so the UI can
distinguish honestly). QA falls back to a small set of pre-baked
keyword answers labeled "示例回答".

### Switching to live

```bash
export BRIEFALPHA_MODE=live
export ANTHROPIC_API_KEY=sk-ant-...           # OR OPENAI_API_KEY
export SEC_EDGAR_USER_AGENT="BriefAlpha/dev your.email@example.com"
make dev-api
```

If any of these are missing, the API logs each missing item and exits
with code 1 — by design, so you can never accidentally serve stale
fixture content as "live".

#### Live preconditions (fail-fast checklist)

- **At least one LLM provider key.** Either:
  - `ANTHROPIC_API_KEY` env var, OR
  - `OPENAI_API_KEY` env var, OR
  - A non-placeholder value in `data/.secrets/llm_api_keys.json` (the
    init script seeds `sk-ant-replace-me` etc. — those are detected as
    placeholders and rejected).
- **`SEC_EDGAR_USER_AGENT`** in the form `AppName/version
  contact@example.com`. SEC's RSS feed requires it.

The default ingestion adapters (yfinance, GDELT, Google News RSS, SEC
EDGAR RSS, HKEX RSS) are key-less, so no other secrets are required for
a baseline live setup. `FINNHUB_API_KEY` / `ALPHA_VANTAGE_API_KEY` etc.
in `.env.example` are placeholders for future paid adapters.

### Refresh button

The top-bar "刷新数据" button is mode-aware:

- **Demo:** invalidates the brief cache so the next page load re-stamps
  `system.last_refreshed_at`, and shows `已刷新 HH:MM`. Does **not**
  trigger ingestion (there's no real data to fetch).
- **Live:** invalidates the cache and respawns brief generation
  (ingestion → pipeline → cache write). Shows `已排队，请稍候`.

## Quick smoke test

After `make dev-api` is up:

```bash
ADMIN_TOKEN=$(cat data/.secrets/admin_token)

curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/brief/today | jq '.brief_id, .conservative'
curl -s http://localhost:8000/api/source-health | jq '.overall, .rows[0]'
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/admin/diagnostics/conservative-brief-rate

curl -s -X POST http://localhost:8000/api/qa \
  -H "content-type: application/json" \
  -d '{"brief_id":"'"$(date -u +%Y-%m-%d)"'","scope":"global","question":"NVDA"}' | jq .
```

`/api/qa` returns `failure_reason: brief_expired` until the daily
07:55 HKT brief lands (or you trigger it manually via
`POST /api/admin/brief/regenerate`).

## Redis namespaces

| Key | TTL | Purpose |
| --- | --- | --- |
| `brief:{date}` | until next 07:55 freeze | Cached morning brief payload |
| `source_health:latest` | 5 min | Aggregated source health snapshot |
| `qa:context:{brief_id}:{scope}` | follows `brief:{date}` | QA history (last 3 turns) |
| `research:queue` / `reanalyze:queue` | n/a (list) | PDF parse + re-analyze queues |

## Security boundaries (demo mode)

- All third-party LLM / embedding / vision calls go through `apps/api/llm/wrapper.py`.
  Any other module that imports a provider SDK is blocked by `import-linter`.
- Evidence sent to LLM is reduced to the `AliasedEvidence` whitelist
  (`evidence_id`, `title_aliased`, `excerpt_aliased`, `quote_span_aliased`,
  `source_tier`, `asset_class`, `published_at`).
- `alias_map` ciphertext lives at `data/alias_maps/{brief_id}.enc` and is
  destroyed at 16:00 HKT each day.
- `audit_mode = demo` by default — only request/response **hashes** are stored.
- Switching to `audit_mode = compliance` requires admin token + reason and
  is **not** retroactive; old `demo` records keep their mode tag.

See `openspec/changes/build-briefalpha-mvp/design.md` §4 for the full
security architecture.

## Spec workflow (OpenSpec)

```bash
openspec list
openspec status --change build-briefalpha-mvp
openspec instructions apply --change build-briefalpha-mvp
```

Active proposal: `openspec/changes/build-briefalpha-mvp/`.

## Design parity check

The frontend MUST match `docs/Designs/BriefAlpha.pen` (Chinese frames are
canonical, English frames are reference only). After major frontend
changes:

```bash
pnpm --filter @briefalpha/web test:e2e -- --grep "visual"
```

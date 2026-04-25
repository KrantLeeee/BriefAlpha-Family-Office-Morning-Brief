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

# 3. Generate local secrets (alias key, admin token placeholders)
make init-secrets

# 4. Apply database migrations
make db-migrate
```

## Run locally

In three separate terminals:

```bash
make dev-redis    # Redis on :6379
make dev-api      # FastAPI on :8000
make dev-web      # Next.js on :3000
```

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

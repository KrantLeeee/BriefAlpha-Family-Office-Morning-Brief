# briefalpha-api

FastAPI backend. See repo root README for setup.

```bash
uv sync
uv run uvicorn briefalpha_api.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```bash
uv run pytest
```

Run import-linter (enforces "only `briefalpha_api.llm` may import provider SDKs"):

```bash
uv run lint-imports
```

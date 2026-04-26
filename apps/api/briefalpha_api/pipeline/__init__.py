"""brief-pipeline: 9-stage processor.

Stages run in fixed order:

  normalize → entity_linking → dedupe → base_scoring → portfolio_mapping
    → conflict_resolve → final_scoring → evidence_selection → anonymization

`conflict_resolve` MUST run before `final_scoring` so the conflict marker
can downweight `market_confirmation` (BPS).

Note: this package intentionally avoids eager re-exports of heavy entry
points (e.g. `run_full_brief`, `run_pipeline`) so lightweight schema-only
consumers (`briefalpha_api.pipeline.schemas`) don't pull the cache/redis
stack at import time. Import those directly from `.run` / `.artifact`.
"""

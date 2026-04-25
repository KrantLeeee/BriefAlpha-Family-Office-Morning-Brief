"""brief-pipeline: 9-stage processor.

The stages run in fixed order:

  normalize → entity_linking → dedupe → base_scoring → portfolio_mapping
    → conflict_resolve → final_scoring → evidence_selection → anonymization

`conflict_resolve` MUST run before `final_scoring` so the conflict marker
can downweight `market_confirmation`.
"""

from .run import build_brief_artifact, run_pipeline  # noqa: F401

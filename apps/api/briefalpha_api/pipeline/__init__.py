"""brief-pipeline: 9-stage processor.

Stages run in fixed order:

  normalize → entity_linking → dedupe → base_scoring → portfolio_mapping
    → conflict_resolve → final_scoring → evidence_selection → anonymization

`conflict_resolve` MUST run before `final_scoring` so the conflict marker
can downweight `market_confirmation` (BPS).
"""

from .artifact import build_brief_artifact  # noqa: F401
from .run import run_full_brief, run_pipeline  # noqa: F401

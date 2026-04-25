"""data-anonymization: ticker aliasing + sensitive entity dict + reverse alias.

Public API:
- `AliasContext`, `Segment`, `AliasedEvidence`
- `make_alias_context(brief_id, universe_tickers, sensitive_entity_dictionary)`
- `replace_in_text(text, ctx, *, field)`
- `aliased_to_original(span, segments)`
- `reverse_alias(text, ctx, *, cited_evidence_ids)`
- `encrypt_alias_map(brief_id, ctx)` / `decrypt_alias_map(brief_id)`
"""

from .alias import AliasContext, make_alias_context  # noqa: F401
from .map_storage import (  # noqa: F401
    decrypt_alias_map,
    delete_alias_map,
    encrypt_alias_map,
)
from .replace import (  # noqa: F401
    AliasedEvidence,
    Segment,
    aliased_to_original,
    build_aliased_evidence,
    replace_in_text,
)
from .reverse import reverse_alias  # noqa: F401
from .sensitive_entity_dictionary import (  # noqa: F401
    SensitiveEntityDictionary,
    build_sensitive_entity_dictionary,
)

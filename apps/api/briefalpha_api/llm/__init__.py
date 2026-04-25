"""llm-orchestration: the only module allowed to import provider SDKs.

Public surface (used by routers / pipeline / qa):

- `LlmRequest`, `LlmResponse`
- `call_text_llm()`, `call_vision_llm()`, `call_embedding()`
- `conservative_fallback()`

Implementation modules `providers/*.py` import the actual SDKs (anthropic /
openai). `import-linter` blocks any other module from importing them.
"""

from .schema import LlmRequest, LlmResponse  # noqa: F401
from .wrapper import (  # noqa: F401
    call_embedding,
    call_text_llm,
    call_vision_llm,
    conservative_fallback,
)

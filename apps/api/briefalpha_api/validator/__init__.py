"""accuracy_validator: post-generation gate for LLM responses.

Each validator runs in order; first failure short-circuits with a reason
the wrapper records under `failure_state`.
"""

from .runner import (  # noqa: F401
    ValidationFailure,
    ValidationResult,
    validate_response,
)

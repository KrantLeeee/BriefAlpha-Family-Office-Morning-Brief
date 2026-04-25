"""Redis cache layer.

The wrapper is resilient: every operation traps connection errors and
returns `None` / no-op so the surrounding code can still respond when
Redis isn't running. Cache misses are indistinguishable from cache
errors at the call-site — both mean "fetch from source".
"""

from .redis_client import (  # noqa: F401
    BRIEF_TTL_SECONDS,
    brief_key,
    get_brief_cache,
    get_redis,
    set_brief_cache,
)

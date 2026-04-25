"""data-ingestion: market / news / official adapters.

Public surface:
- `RawItem` (normalized output shape)
- `IngestionAdapter` ABC
- `MarketAdapter`, `NewsAdapter`, `OfficialAdapter` concrete adapters
- `run_ingestion(universe)` — orchestrator that respects data_sources.yml
"""
from .base import IngestionAdapter, RawItem  # noqa: F401
from .market import MarketAdapter  # noqa: F401
from .news import NewsAdapter  # noqa: F401
from .official import OfficialAdapter  # noqa: F401
from .runner import run_ingestion  # noqa: F401

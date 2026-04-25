"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Skip secrets check during tests.
os.environ.setdefault("BRIEFALPHA_SKIP_SECRETS_CHECK", "1")

# Make the package importable when pytest runs from apps/api.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

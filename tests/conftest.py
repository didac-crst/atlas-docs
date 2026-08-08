"""Test defaults: require an explicit ATLASDOCS_ENV for Settings/get_settings()."""

from __future__ import annotations

import os

# Must run before test modules import atlasdocs.api (which builds the app at import).
os.environ.setdefault("ATLASDOCS_ENV", "development")

"""Frozen editorial seed: values hand-entered in the original HTML pages.

The seed is read-only. Rendered pages must never be extracted back into it,
otherwise last week's output becomes this week's input and errors can only
accumulate. Live API data always takes precedence over seed values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEED_REL = Path("data") / "seed" / "editorial-2026-10-28.json"


def seed_path(repo_root: Path) -> Path:
    return repo_root / SEED_REL


def load_seed(repo_root: Path) -> dict[str, Any]:
    path = seed_path(repo_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

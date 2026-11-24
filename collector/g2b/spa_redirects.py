"""Remove legacy *.html redirect stubs that break GitHub Pages SPA routes.

GitHub Pages maps `/band` → `band.html`. A stub that meta-refreshes to
`/ai-agent-market/band` therefore loops forever. Client routes are served via
`404.html` (= SPA `index.html`) and React Router `*.html` Navigate routes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Former stub paths (kept for cleanup / CLI compatibility).
REDIRECTS: tuple[tuple[str, str], ...] = (
    ("band.html", "band"),
    ("awards.html", "awards"),
    ("pricing.html", "pricing"),
    ("plans.html", "plans"),
    ("prespecs.html", "prespecs"),
    ("bidders.html", "bidders"),
    ("agencies.html", "agencies"),
    ("competitors.html", "competitors"),
    ("consortium.html", "consortium"),
    ("alerts.html", "alerts"),
    ("deliverables.html", "deliverables"),
    ("reports/index.html", "reports"),
)


def _is_redirect_stub(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return 'meta http-equiv="refresh"' in text and "Redirect" in text


def write_spa_redirects(repo_root: Path, *, nested: bool = True) -> dict[str, Any]:
    """Delete redirect stubs instead of writing them (nested flag retained for CLI)."""
    del nested  # unused; CLI still passes --root/--nested
    removed: list[str] = []
    for rel, _target in REDIRECTS:
        path = repo_root / rel
        if not path.exists():
            continue
        # Always remove known page stubs; for reports/index.html only drop refresh stubs
        # so real report index HTML (if any) is preserved.
        if rel == "reports/index.html" and not _is_redirect_stub(path):
            continue
        path.unlink(missing_ok=True)
        removed.append(rel)
    return {"written": [], "removed": removed, "nested": False}

"""Write thin HTML stubs that send legacy *.html URLs to the React SPA routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# path relative to site root (GitHub Pages nests under /ai-agent-market/)
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


def _stub(target_path: str, *, nested: bool) -> str:
    # Absolute path under the Pages site so both /band.html and nested bases work.
    href = f"/ai-agent-market/{target_path}" if nested else f"/{target_path}"
    return (
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        f'<meta http-equiv="refresh" content="0;url={href}">'
        f'<link rel="canonical" href="{href}">'
        f"<title>Redirect</title></head><body>"
        f'<p><a href="{href}">페이지가 이동했습니다</a></p>'
        "</body></html>\n"
    )


def write_spa_redirects(repo_root: Path, *, nested: bool = True) -> dict[str, Any]:
    written: list[str] = []
    for rel, target in REDIRECTS:
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_stub(target, nested=nested), encoding="utf-8")
        written.append(rel)
    return {"written": written, "nested": nested}

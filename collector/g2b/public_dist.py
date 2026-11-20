"""Stage static public site files for Cloudflare Pages deploy (no git commit required)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

ROOT_FILES = (
    "index.html",
    "band.html",
    "awards.html",
    "competitors.html",
    "prespecs.html",
    "pricing.html",
    "plans.html",
    "bidders.html",
    "agencies.html",
    "alerts.html",
    "deliverables.html",
    "404.html",
    "sitemap.xml",
    "reports.json",
)

DIRS = ("assets", "bids", "reports", "feeds", "research")

# N-05: agency/bidder search fetch these under /data/…
DATA_FILES = ("bidders.json", "agencies.json", "firms.json")

# GitHub Pages nest under /ai-agent-market/; CF Pages mirror is site root /.
_NESTED_PREFIX_RE = re.compile(r'(href|src)="(/ai-agent-market/)')


def _rewrite_404_for_root(text: str) -> str:
    """N-05: CF Pages 404 must use / not /ai-agent-market/."""
    return _NESTED_PREFIX_RE.sub(r'\1="/', text)


def stage_public_dist(repo_root: Path, dest: Path | None = None) -> dict[str, Any]:
    dest = dest or (repo_root / "public-dist")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    copied_files = 0
    for name in ROOT_FILES:
        src = repo_root / name
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8") if name == "404.html" else None
        if text is not None:
            (dest / name).write_text(_rewrite_404_for_root(text), encoding="utf-8")
        else:
            shutil.copy2(src, dest / name)
        copied_files += 1

    copied_dirs: list[str] = []
    for name in DIRS:
        src = repo_root / name
        if src.is_dir():
            shutil.copytree(src, dest / name, dirs_exist_ok=True)
            copied_dirs.append(name)

    data_dest = dest / "data"
    data_dest.mkdir(exist_ok=True)
    data_copied = 0
    for name in DATA_FILES:
        src = repo_root / "data" / name
        if src.is_file():
            shutil.copy2(src, data_dest / name)
            data_copied += 1

    return {
        "dest": str(dest),
        "files": copied_files,
        "dirs": copied_dirs,
        "data_files": data_copied,
    }

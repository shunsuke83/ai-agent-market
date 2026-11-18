"""Stage static public site files for Cloudflare Pages deploy (no git commit required)."""

from __future__ import annotations

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


def stage_public_dist(repo_root: Path, dest: Path | None = None) -> dict[str, Any]:
    dest = dest or (repo_root / "public-dist")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    copied_files = 0
    for name in ROOT_FILES:
        src = repo_root / name
        if src.is_file():
            shutil.copy2(src, dest / name)
            copied_files += 1

    copied_dirs: list[str] = []
    for name in DIRS:
        src = repo_root / name
        if src.is_dir():
            shutil.copytree(src, dest / name, dirs_exist_ok=True)
            copied_dirs.append(name)

    return {"dest": str(dest), "files": copied_files, "dirs": copied_dirs}

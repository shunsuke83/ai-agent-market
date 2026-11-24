"""Stage public site for Cloudflare / GitHub Pages deploy.

Default (SPA): React `web/dist` + SPA JSON + feeds/sitemap. Legacy HTML copy is opt-in.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from .spa_export import copy_spa_into, write_spa_export

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


def _legacy_html_enabled() -> bool:
    return os.environ.get("STAGE_LEGACY_HTML", "").strip().lower() in ("1", "true", "yes")


def stage_spa_onto_dist(repo_root: Path, dist: Path) -> dict[str, Any]:
    """Merge SPA JSON + feeds/sitemap/favicon into an already-built React dist."""
    if not dist.is_dir():
        raise FileNotFoundError(f"React dist missing: {dist}")

    write = write_spa_export(repo_root)
    spa = copy_spa_into(repo_root, dist)

    extras: list[str] = []
    for name in ("sitemap.xml", "robots.txt"):
        src = repo_root / name
        if src.is_file():
            shutil.copy2(src, dist / name)
            extras.append(name)

    feeds_src = repo_root / "feeds"
    if feeds_src.is_dir():
        dest_feeds = dist / "feeds"
        if dest_feeds.exists():
            shutil.rmtree(dest_feeds)
        shutil.copytree(feeds_src, dest_feeds)
        extras.append("feeds/")

    favicon = repo_root / "assets" / "favicon.svg"
    if favicon.is_file():
        assets = dist / "assets"
        assets.mkdir(exist_ok=True)
        shutil.copy2(favicon, assets / "favicon.svg")
        extras.append("assets/favicon.svg")

    # Cloudflare Pages serves foo.html for /foo when that file exists, which would
    # shadow the SPA fallback. Strip any leftover legacy HTML from the dist tree.
    removed_html: list[str] = []
    keep_html = {"index.html", "404.html"}
    for path in dist.rglob("*.html"):
        rel = path.relative_to(dist).as_posix()
        if path.name in keep_html and path.parent == dist:
            continue
        if rel.startswith("data/") or rel.startswith("assets/"):
            continue
        path.unlink(missing_ok=True)
        removed_html.append(rel)
    extras.extend(f"-{name}" for name in removed_html)

    # Legacy HTML URL → SPA path (Cloudflare Pages _redirects). Vite also ships public/_redirects.
    redirects = dist / "_redirects"
    legacy_rules = """
/band.html /band 301
/awards.html /awards 301
/pricing.html /pricing 301
/plans.html /plans 301
/prespecs.html /prespecs 301
/bidders.html /bidders 301
/agencies.html /agencies 301
/competitors.html /competitors 301
/alerts.html /alerts 301
/deliverables.html /deliverables 301
/reports/index.html /reports 301
/index.html / 301
""".strip()
    existing = redirects.read_text(encoding="utf-8") if redirects.is_file() else "/*    /index.html   200\n"
    if "/band.html" not in existing:
        redirects.write_text(legacy_rules + "\n" + existing.lstrip(), encoding="utf-8")

    return {
        "dist": str(dist),
        "spa": write,
        "staged": spa,
        "extras": extras,
        "removed_html": removed_html,
    }


def stage_public_dist(repo_root: Path, dest: Path | None = None) -> dict[str, Any]:
    """Stage deploy tree.

    Prefer React dist when present (`web/dist`). Otherwise fall back to public-dist/
    with SPA JSON (+ optional legacy HTML when STAGE_LEGACY_HTML=1).
    """
    web_dist = repo_root / "web" / "dist"
    if web_dist.is_dir() and (web_dist / "index.html").is_file():
        return stage_spa_onto_dist(repo_root, web_dist)

    dest = dest or (repo_root / "public-dist")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    write = write_spa_export(repo_root)
    spa = copy_spa_into(repo_root, dest)

    copied_files = 0
    copied_dirs: list[str] = []
    if _legacy_html_enabled():
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

        for name in DIRS:
            src = repo_root / name
            if src.is_dir():
                shutil.copytree(src, dest / name, dirs_exist_ok=True)
                copied_dirs.append(name)
    else:
        # Minimal static companions without full HTML tree.
        for name in ("sitemap.xml", "robots.txt"):
            src = repo_root / name
            if src.is_file():
                shutil.copy2(src, dest / name)
                copied_files += 1
        feeds_src = repo_root / "feeds"
        if feeds_src.is_dir():
            shutil.copytree(feeds_src, dest / "feeds", dirs_exist_ok=True)
            copied_dirs.append("feeds")
        favicon = repo_root / "assets" / "favicon.svg"
        if favicon.is_file():
            (dest / "assets").mkdir(exist_ok=True)
            shutil.copy2(favicon, dest / "assets" / "favicon.svg")
            copied_dirs.append("assets")

    return {
        "dest": str(dest),
        "mode": "legacy-html" if _legacy_html_enabled() else "spa-data",
        "files": copied_files,
        "dirs": copied_dirs,
        "spa": write,
        "staged": spa,
        "data_files": spa.get("data_files", 0),
    }

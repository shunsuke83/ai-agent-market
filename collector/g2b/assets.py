from __future__ import annotations

import hashlib
import re
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parents[2] / "assets"
ASSET_FILES = ("site.css", "table-sort.js", "table-filter.js")

_ASSET_REF_RE = re.compile(
    r"(assets/(?:" + "|".join(re.escape(f) for f in ASSET_FILES) + r"))\?v=[\w.-]+"
)


def _content_version() -> str:
    h = hashlib.sha1()
    for name in ASSET_FILES:
        path = ASSET_DIR / name
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:10]


# Content hash, so any CSS/JS edit busts browser caches without a manual bump.
ASSET_VER = _content_version()


def stamp_asset_versions(html_text: str) -> str:
    return _ASSET_REF_RE.sub(rf"\g<1>?v={ASSET_VER}", html_text)

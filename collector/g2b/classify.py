from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEYWORDS = ROOT / "config" / "keywords.yaml"


def load_keywords(path: Path | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_KEYWORDS, encoding="utf-8") as f:
        return yaml.safe_load(f)


_ASCII_WORD = re.compile(r"[A-Za-z0-9/]+")


@lru_cache(maxsize=512)
def _patterns(keyword: str) -> tuple[re.Pattern[str], ...]:
    # Latin keywords match as whole words so "AI" skips Air, KAIST, Maxwell, Stainer.
    # An upper-case keyword may also end a product name (DocuRAG, VIXAI-SMART).
    k = re.escape(keyword)
    if not _ASCII_WORD.fullmatch(keyword):
        return (re.compile(k, re.IGNORECASE),)
    pats = [re.compile(rf"(?<![A-Za-z]){k}(?![A-Za-z])", re.IGNORECASE)]
    if keyword.isupper():
        pats.append(re.compile(rf"{k}(?![A-Za-z])"))
    return tuple(pats)


def _has_any(title: str, keywords: list[str]) -> bool:
    return any(p.search(title) for k in keywords for p in _patterns(k))


def classify_scope(title: str, rules: dict[str, Any] | None = None) -> str | None:
    """Return 생성형·Agent | AI SW 확대 | None."""
    rules = rules or load_keywords()
    scope = rules["scope"]
    if _has_any(title, scope["생성형·Agent"]["any"]):
        # Still require an AI signal for pure Agent false-positives handled by keyword list
        return "생성형·Agent"
    if _has_any(title, scope["AI SW 확대"]["any"]):
        return "AI SW 확대"
    return None


def classify_fields(title: str, rules: dict[str, Any] | None = None) -> list[str]:
    rules = rules or load_keywords()
    hits = [name for name, kws in rules["fields"].items() if _has_any(title, kws)]
    return hits or ["AI 일반"]


def classify_nature(title: str, rules: dict[str, Any] | None = None) -> str | None:
    rules = rules or load_keywords()
    for name, kws in rules["nature"].items():
        if _has_any(title, kws):
            return name
    return None


def classify_title(title: str, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or load_keywords()
    return {
        "scope": classify_scope(title, rules),
        "fields": classify_fields(title, rules),
        "nature": classify_nature(title, rules),
    }

"""Match notice text to GenON solutions (synonym dictionary + optional profile brands)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .classify import _has_any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOLUTIONS = ROOT / "config" / "genon_solutions.yaml"

PRIORITY_RANK = {"S": 0, "A": 1, "B": 2}
BUILD_MARKERS = ("구축", "고도화", "개발", "플랫폼", "기능 개발", "도입")
OPS_MARKERS = (
    "운영 용역",
    "센터 운영",
    "운영사업",
    "유지관리",
    "유지보수",
    "운영·유지",
    "운영 및 유지",
)
PRODUCT_MARKERS = ("라이선스", "라이센스", "구독", "상용 SW", "소프트웨어 구매")


@lru_cache(maxsize=4)
def load_solutions(path: str | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_SOLUTIONS, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _summary_blob(summary: dict[str, Any] | None) -> str:
    s = (summary or {}).get("summary") or {}
    parts = [*(s.get("requirements") or []), *(s.get("cautions") or []), s.get("evaluation") or ""]
    return "\n".join(str(p) for p in parts if p)


def _brand_aliases(profile: dict[str, Any] | None) -> list[tuple[str, str]]:
    """[(display_name, synonym)] from company.products / aliases."""
    company = (profile or {}).get("company") or {}
    out: list[tuple[str, str]] = []
    for p in company.get("products") or []:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        out.append((name.split()[0], name))
        for part in name.replace("(", " ").replace(")", " ").split():
            if len(part) >= 2:
                out.append((name.split()[0], part))
    for a in company.get("aliases") or []:
        if a:
            out.append((str(a), str(a)))
    return out


def match_solutions(
    text: str,
    profile: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return best solution match + all hits.

    Keys: solution, name, line, line_label, priority, hits, exclude_only
    """
    catalog = catalog or load_solutions()
    lines = catalog.get("lines") or {}
    text = text or ""
    scored: list[tuple[int, int, dict[str, Any]]] = []

    for sol in catalog.get("solutions") or []:
        syns = list(sol.get("synonyms") or [])
        hits = [s for s in syns if _has_any(text, [s])]
        if not hits:
            continue
        pr = str(sol.get("priority") or "B")
        scored.append(
            (
                PRIORITY_RANK.get(pr, 9),
                -len(hits),
                {
                    "solution": sol.get("id"),
                    "name": sol.get("name"),
                    "line": sol.get("line"),
                    "line_label": (lines.get(sol.get("line")) or {}).get("label") or sol.get("line"),
                    "priority": pr,
                    "hits": hits[:5],
                },
            )
        )

    for brand, syn in _brand_aliases(profile):
        if _has_any(text, [syn]):
            scored.append(
                (
                    0,
                    -1,
                    {
                        "solution": "brand",
                        "name": brand,
                        "line": "enterprise_ax",
                        "line_label": (lines.get("enterprise_ax") or {}).get("label") or "Enterprise AX",
                        "priority": "S",
                        "hits": [syn],
                    },
                )
            )

    scored.sort(key=lambda x: (x[0], x[1], str(x[2].get("solution") or "")))
    best = scored[0][2] if scored else None

    exclude_hits = [h for h in (catalog.get("exclude_hints") or []) if _has_any(text, [h])]
    exclude_only = bool(exclude_hits) and best is None

    if best is None:
        return {
            "solution": None,
            "name": None,
            "line": None,
            "line_label": None,
            "priority": None,
            "hits": [],
            "exclude_only": exclude_only,
            "exclude_hits": exclude_hits[:3],
        }
    return {**best, "exclude_only": False, "exclude_hits": exclude_hits[:3]}


def classify_engagement(
    title: str,
    nature: str | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify work kind: build | product | ops | other, plus ops exception strength.

    Exception C: ops titles can promote when title/summary shows build or product share.
    """
    title = title or ""
    summary_text = _summary_blob(summary)
    blob = f"{title}\n{summary_text}"
    nature = nature or ""

    title_build = bool(_has_any(title, list(BUILD_MARKERS)))
    summary_build = bool(_has_any(summary_text, list(BUILD_MARKERS + PRODUCT_MARKERS)))
    has_build = title_build or summary_build or nature == "시스템 구축·고도화"
    has_product = bool(_has_any(blob, list(PRODUCT_MARKERS))) or nature == "구독·라이선스"
    has_ops = bool(_has_any(blob, list(OPS_MARKERS))) or nature == "운영·유지보수"

    # Build/product in the title wins outright.
    if title_build or (nature == "시스템 구축·고도화" and not has_ops):
        return {"engagement": "build", "ops_exception": "strong" if has_ops else None}
    if has_product and not has_ops:
        return {"engagement": "product", "ops_exception": None}

    if has_ops:
        if title_build:
            return {"engagement": "build", "ops_exception": "strong"}
        if summary_build:
            # RFP shows build/product share — strong if summary is substantive.
            strength = "strong" if len(summary_text) >= 12 else "weak"
            return {"engagement": "ops", "ops_exception": strength}
        return {"engagement": "ops", "ops_exception": None}

    if has_build:
        return {"engagement": "build", "ops_exception": None}
    if has_product:
        return {"engagement": "product", "ops_exception": None}
    if nature in ("ISP·전략", "연구·교육·행사", "인프라") or _has_any(
        blob, ["ISP", "ISMP", "정보화전략"]
    ):
        return {"engagement": "other", "ops_exception": None}
    return {"engagement": "other", "ops_exception": None}


def notice_match_text(
    n: dict[str, Any],
    summary: dict[str, Any] | None = None,
) -> str:
    return "\n".join(
        [
            n.get("title") or "",
            n.get("nature") or "",
            " ".join(n.get("fields") or []),
            _summary_blob(summary),
        ]
    )

"""agencies.html: 수요기관명으로 AI 사업 공고·낙찰 업체 검색 (data/agencies.json + agency-search.js)."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from .firms import winner_bizno
from .pricing import load_notices
from .render import _award_amount, _today_kst, infer_status, load_run_status, stamp_text
from .site import detail_href, page, stat

INDEX_REL = Path("data") / "agencies.json"


def _num(v: Any) -> float | None:
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def build_agency_index(notices: list[dict[str, Any]], today: Any = None) -> dict[str, Any]:
    """Notices as rows [date, org, title, budget, href, winner, winner_bizno, award, status, bid_count, core]."""
    rows: list[list[Any]] = []
    seen: set[str] = set()
    ordered = sorted(notices, key=lambda n: n.get("open_date") or n.get("notice_date") or "", reverse=True)
    for n in ordered:
        org = (n.get("org") or "").strip()
        key = f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"
        if not org or not n.get("bid_no") or key in seen:
            continue
        seen.add(key)
        rows.append([
            n.get("notice_date") or n.get("open_date") or "",
            org,
            n.get("title") or "",
            _num(n.get("budget_eok")),
            detail_href(n),
            (n.get("winner") or n.get("first_rank") or "").strip(),
            winner_bizno(n) or "",
            _num(_award_amount(n)),
            infer_status(n, today),
            _int(n.get("bid_count")),
            1 if n.get("scope") == "생성형·Agent" else 0,
        ])
    return {"notices": rows}


def build_agencies_page(index: dict[str, Any], run_status: dict[str, Any], version: str) -> str:
    rows = index["notices"]
    orgs = {r[1] for r in rows}
    won = sum(1 for r in rows if r[8] == "낙찰")
    body = (
        '<div class="eyebrow">Agency Search</div><h1>발주기관 검색</h1>'
        '<p class="lede">수요기관 이름으로 그 기관이 낸 AI 사업 공고와 낙찰 업체를 찾습니다. '
        "어느 기관이 얼마 규모로 자주 발주하는지, 누가 그 기관 사업을 가져가는지 볼 수 있습니다.</p>"
        f'<div class="stamp">{html.escape(stamp_text(run_status))}</div>'
        '<div class="stats">'
        + stat(f"{len(orgs):,}곳", "수요기관")
        + stat(f"{len(rows):,}건", "AI 사업 공고")
        + stat(f"{won:,}건", "낙찰 확정")
        + "</div>"
        '<form class="bidder-search" role="search" onsubmit="return false">'
        '<input type="search" id="agency-q" placeholder="기관명 일부 (예: 한국전력, 교육청)" '
        'aria-label="수요기관명" autocomplete="off">'
        "</form>"
        f'<div id="agency-results" data-src="data/agencies.json?v={version}" aria-live="polite">'
        '<p class="meta">기관명 일부를 입력하세요.</p></div>'
        "<noscript><p class=\"empty\">검색에는 JavaScript가 필요합니다.</p></noscript>"
        '<p class="note">이 사이트가 수집하는 AI 사업 공고만 담았습니다. 기관의 전체 발주 이력이 아닙니다. '
        "수요기관은 나라장터 공고의 수요기관명 그대로라 같은 기관이 다른 이름으로 나뉠 수 있습니다. "
        "낙찰 업체는 낙찰 확정 건이고, 확정 전이면 개찰 1순위를 '(1순위)'로 표시합니다. "
        "낙찰금액은 나라장터에 공개된 건만 합칩니다.</p>"
    )
    return page("발주기관 검색", body, scripts=("agency-search.js",))


def render_agencies_page(repo_root: Path) -> dict[str, Any]:
    index = build_agency_index(load_notices(repo_root), _today_kst())
    data = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    (repo_root / INDEX_REL).write_text(data + "\n", encoding="utf-8")
    version = hashlib.sha1(data.encode("utf-8")).hexdigest()[:10]
    path = repo_root / "agencies.html"
    path.write_text(build_agencies_page(index, load_run_status(repo_root), version), encoding="utf-8")
    return {"path": str(path), "notices": len(index["notices"]), "bytes": len(data.encode("utf-8"))}

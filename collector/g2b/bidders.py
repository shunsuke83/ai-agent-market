"""bidders.html: 사업자번호·업체명으로 AI 사업 공고 투찰 이력 검색 (data/bidders.json + bidder-search.js)."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from .firms import firm_profile_text, load_firms, public_change_text, winner_bizno
from .pricing import load_notices
from .render import _today_kst, infer_status, load_run_status, stamp_text
from .site import detail_href, page, stat

INDEX_REL = Path("data") / "bidders.json"


def _digits(v: Any) -> str:
    return "".join(ch for ch in str(v or "") if ch.isdigit())


def _num(v: Any) -> float | None:
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def build_bidder_index(
    notices: list[dict[str, Any]], firms: dict[str, dict[str, Any]], today: Any = None
) -> dict[str, Any]:
    """Compact index: notices as rows, firms keyed by 사업자번호 with [notice idx, rank, rate, amount]."""
    rows: list[list[Any]] = []
    out: dict[str, list[Any]] = {}
    seen: set[str] = set()
    ordered = sorted(notices, key=lambda n: n.get("open_date") or n.get("notice_date") or "", reverse=True)
    for n in ordered:
        bidders = [b for b in n.get("bidders") or [] if isinstance(b, dict) and _digits(b.get("bizno"))]
        key = f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"
        if not bidders or key in seen:
            continue
        seen.add(key)
        idx = len(rows)
        rows.append([
            n.get("open_date") or n.get("notice_date") or "",
            n.get("org") or "",
            n.get("title") or "",
            _num(n.get("budget_eok")),
            detail_href(n),
            _digits(winner_bizno(n)),
            infer_status(n, today),
        ])
        for b in bidders:
            bz = _digits(b["bizno"])
            firm = out.setdefault(bz, [b.get("name") or "", "", []])
            if not firm[0]:
                firm[0] = b.get("name") or ""
            rank = b.get("rank") if isinstance(b.get("rank"), int) else None
            firm[2].append([idx, rank, _num(b.get("rate_pct")), _num(b.get("amount_eok"))])
    for bz, firm in out.items():
        info = firms.get(bz) or {}
        if info.get("corp_name"):
            firm[0] = info["corp_name"]
        firm[1] = firm_profile_text(info)
        changes = [
            [c.get("changed_at") or c.get("date") or "", public_change_text(c), bool(c.get("changed_at"))]
            for c in info.get("changes") or []
        ]
        if changes:
            firm.append(changes)
    return {"notices": rows, "firms": out}


def build_bidders_page(index: dict[str, Any], run_status: dict[str, Any], version: str) -> str:
    rows = index["notices"]
    dates = sorted(r[0] for r in rows if r[0])
    span = f"{dates[0][:7]} ~ {dates[-1][:7]}" if dates else "-"
    body = (
        '<div class="eyebrow">Bidder History</div><h1>업체 입찰이력 검색</h1>'
        '<p class="lede">사업자번호나 업체명으로 AI 사업 공고에 투찰한 이력을 찾습니다. '
        "경쟁사가 어떤 기관·규모의 사업에 얼마의 투찰률로 들어오는지, 누구와 자주 맞붙는지 볼 수 있습니다.</p>"
        f'<div class="stamp">{html.escape(stamp_text(run_status))}</div>'
        '<div class="stats">'
        + stat(f"{len(index['firms']):,}곳", "투찰 업체 (사업자번호 기준)")
        + stat(f"{len(rows):,}건", "개찰 결과가 있는 공고")
        + stat(span, "개찰일 범위")
        + "</div>"
        '<form class="bidder-search" role="search" onsubmit="return false">'
        '<input type="search" id="bidder-q" placeholder="사업자번호 10자리 또는 업체명" '
        'aria-label="사업자번호 또는 업체명" autocomplete="off">'
        "</form>"
        f'<div id="bidder-results" data-src="data/bidders.json?v={version}" aria-live="polite">'
        '<p class="meta">사업자번호(하이픈 있어도 됨)나 업체명 일부를 입력하세요.</p></div>'
        "<noscript><p class=\"empty\">검색에는 JavaScript가 필요합니다.</p></noscript>"
        '<p class="note">이 사이트가 수집하는 AI 사업 공고의 개찰결과만 담았습니다. 전 업종 이력이 아닙니다. '
        "순위·투찰률·투찰금액은 나라장터 개찰결과 그대로이고, '낙찰'은 낙찰 확정 건, "
        "'1순위'는 낙찰 확정 표시 없이 개찰 1위인 건입니다. 업체명은 나라장터 조달업체 기본정보를 확인한 업체만 공식 상호로 바꿉니다.</p>"
    )
    return page("업체 입찰이력 검색", body, scripts=("bidder-search.js",))


def render_bidders_page(repo_root: Path) -> dict[str, Any]:
    index = build_bidder_index(load_notices(repo_root), load_firms(repo_root), _today_kst())
    data = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    (repo_root / INDEX_REL).write_text(data + "\n", encoding="utf-8")
    version = hashlib.sha1(data.encode("utf-8")).hexdigest()[:10]
    path = repo_root / "bidders.html"
    path.write_text(build_bidders_page(index, load_run_status(repo_root), version), encoding="utf-8")
    return {"path": str(path), "firms": len(index["firms"]), "notices": len(index["notices"]),
            "bytes": len(data.encode("utf-8"))}

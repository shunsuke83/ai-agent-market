"""prespecs.html: AI 사전규격 (pre-specification) list from data/prespecs.json."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .assets import ASSET_VER
from .classify import load_keywords
from .render import KST, _fmt_budget, _kst_date, load_run_status

STATUS_BID = "본공고 게시"
STATUS_OPEN = "의견 접수 중"
STATUS_CLOSED = "의견 마감"

STATUS_TITLE = {
    STATUS_BID: "사전규격과 연결된 본공고가 나라장터에 게시됨",
    STATUS_OPEN: "의견등록 마감 전 — 규격 의견을 낼 수 있음",
    STATUS_CLOSED: "의견등록 마감, 본공고 대기",
}

NAV = (
    '<nav class="top"><b>공공 AI Agent 시장 리서치</b>'
    '<a href="index.html">홈</a>'
    '<a href="band.html">8~30억 분석</a>'
    '<a href="awards.html">수주 현황</a>'
    '<a href="prespecs.html">사전규격</a>'
    '<a href="competitors.html">국내 전문기업</a>'
    '<a href="reports/index.html">리포트 목록</a>'
    '<a href="deliverables.html">산출물 안내</a></nav>'
)

HEAD = (
    '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "<title>AI 사업 사전규격</title>"
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@500&display=swap">'
    '<meta http-equiv="Cache-Control" content="no-cache">'
    f'<link rel="stylesheet" href="assets/site.css?v={ASSET_VER}"></head><body>'
    '<div class="wrap">'
)

FOOTER = (
    "<footer>데이터 출처: 조달청 나라장터 사전규격정보(공공데이터포털 Open API). "
    "사업명 기준 자동 분류라 일부 오분류가 있을 수 있습니다. "
    "규격서 링크는 나라장터 원문 파일입니다.</footer>"
)

TAIL = (
    f'</div><script src="assets/table-sort.js?v={ASSET_VER}" defer></script>'
    f'<script src="assets/table-filter.js?v={ASSET_VER}" defer></script></body></html>'
)

THEAD = (
    "<thead><tr><th>등록일</th><th>의견마감</th><th>상태</th><th>수요기관</th>"
    "<th>사업명</th><th>범위</th>"
    '<th class="num" title="배정예산 기준">예산(억)</th>'
    "<th>규격서</th><th>본공고</th></tr></thead>"
)


def load_prespecs(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "data" / "prespecs.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("prespecs") or [])


def prespec_status(p: dict[str, Any], now: datetime | None = None) -> str:
    if p.get("bid_nos"):
        return STATUS_BID
    now = now or datetime.now(KST)
    close = p.get("opinion_close_at")
    if close and close >= now.strftime("%Y-%m-%d %H:%M"):
        return STATUS_OPEN
    return STATUS_CLOSED


def _bid_href(bid_no: str) -> str:
    no = bid_no.split("-")[0]
    return html.escape(
        f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={no}&bidPbancOrd=000",
        quote=True,
    )


def render_row(p: dict[str, Any], status: str) -> str:
    files = " ".join(
        f'<a href="{html.escape(u, quote=True)}" rel="noopener">{i}</a>'
        for i, u in enumerate(p.get("spec_files") or [], 1)
    )
    bids = " ".join(
        f'<a href="{_bid_href(b)}" rel="noopener">{html.escape(b)}</a>' for b in p.get("bid_nos") or []
    )
    close = (p.get("opinion_close_at") or "")[:10]
    style = "color:var(--accent)" if status == STATUS_OPEN else "color:var(--muted)"
    return (
        "<tr>"
        f"<td>{html.escape(p.get('registered_date') or '')}</td>"
        f"<td>{html.escape(close)}</td>"
        f'<td style="{style};white-space:nowrap" title="{html.escape(STATUS_TITLE[status])}">'
        f"{html.escape(status)}</td>"
        f"<td>{html.escape(p.get('org') or '')}</td>"
        f"<td>{html.escape(p.get('title') or '')}"
        f'<div class="meta">{html.escape(p.get("prespec_no") or "")}'
        f'{" · " + html.escape(p["biz_div"]) if p.get("biz_div") else ""}</div></td>'
        f"<td>{html.escape(p.get('scope') or '')}</td>"
        f'<td class="num">{_fmt_budget(p.get("asign_budget_eok"))}</td>'
        f"<td>{files}</td>"
        f"<td>{bids}</td>"
        "</tr>"
    )


def _stat(value: str, label: str) -> str:
    return f'<div class="stat"><div class="v">{value}</div><div class="l">{label}</div></div>'


def stamp_for(status: dict[str, Any]) -> str:
    stage = (status.get("stages") or {}).get("prespecs") or {}
    ok_day = _kst_date(stage.get("last_success_at"))
    text = f"데이터 기준 {ok_day.isoformat()}" if ok_day else "데이터 기준 미확인"
    if stage.get("last_outcome") not in (None, "success"):
        tried = _kst_date(stage.get("last_attempt_at"))
        text += f" · 최근 수집 실패{' ' + tried.isoformat() if tried else ''}, 기존 데이터 표시 중"
    return text


def render_prespecs_html(
    prespecs: list[dict[str, Any]], run_status: dict[str, Any], now: datetime | None = None
) -> str:
    rules = load_keywords()
    lo, hi = rules["filters"]["band_min_eok"], rules["filters"]["band_max_eok"]
    rows = sorted(prespecs, key=lambda p: p.get("registered_at") or "", reverse=True)
    statuses = [prespec_status(p, now) for p in rows]
    budgets = [p.get("asign_budget_eok") or 0 for p in rows]
    n_open = statuses.count(STATUS_OPEN)
    n_bid = statuses.count(STATUS_BID)
    n_band = sum(1 for b in budgets if lo <= b <= hi)
    since = min((p.get("registered_date") or "" for p in rows), default="")

    stats = (
        '<div class="stats">'
        + _stat(f"{len(rows):,}건", f"AI 사전규격 ({since} 이후)" if since else "AI 사전규격")
        + _stat(f"{n_open:,}건", "의견 접수 중")
        + _stat(f"{n_band:,}건", f"배정예산 {lo:g}~{hi:g}억")
        + _stat(f"{n_bid:,}건", "본공고 게시")
        + _stat(f"{round(sum(budgets)):,}억", "배정예산 합계")
        + "</div>"
    )
    body_rows = "".join(render_row(p, s) for p, s in zip(rows, statuses))
    table = (
        '<div class="tbl"><table class="notices prespecs js-filter">'
        f"{THEAD}<tbody>{body_rows}</tbody></table></div>"
        if rows
        else '<p class="note">수집된 사전규격이 아직 없습니다.</p>'
    )
    return (
        HEAD
        + NAV
        + '<div class="eyebrow">사전규격</div><h1>AI 사업 사전규격</h1>'
        '<p class="lede">본공고 전에 공개되는 사전규격(규격서 초안)입니다. '
        "의견등록 마감 전이면 규격에 의견을 낼 수 있고, 규격서로 본공고 RFP를 미리 볼 수 있습니다.</p>"
        f'<div class="stamp">{html.escape(stamp_for(run_status))}</div>'
        + stats
        + "<h2>사전규격 목록</h2>"
        '<p class="note">상태로 거르면 의견 접수 중인 건만 볼 수 있습니다. '
        "물품은 SW 납품이 분명한 건만 포함하고, GPU·서버 등 장비 구매와 교육·행사성 용역은 제외합니다.</p>"
        + table
        + FOOTER
        + TAIL
    )


def render_prespecs_page(repo_root: Path) -> dict[str, Any]:
    prespecs = load_prespecs(repo_root)
    path = repo_root / "prespecs.html"
    path.write_text(
        render_prespecs_html(prespecs, load_run_status(repo_root)), encoding="utf-8"
    )
    return {"path": str(path), "prespecs": len(prespecs)}

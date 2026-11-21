"""prespecs.html: AI 사전규격 (pre-specification) list from data/prespecs.json."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .classify import load_keywords
from .render import KST, _fmt_budget, load_run_status, stage_stamp
from .site import DETAIL_DIR, page, stat

STATUS_BID = "본공고 게시"
STATUS_OPEN = "의견 접수 중"
STATUS_CLOSED = "의견 마감"

STATUS_TITLE = {
    STATUS_BID: "사전규격과 연결된 본공고가 나라장터에 게시됨",
    STATUS_OPEN: "의견등록 마감 전 — 규격 의견을 낼 수 있음",
    STATUS_CLOSED: "의견등록 마감, 본공고 대기",
}

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


def _bid_link(bid_no: str, details: dict[str, str]) -> str:
    no = bid_no.split("-")[0]
    if no in details:
        return f'<a href="{DETAIL_DIR}/{html.escape(details[no])}.html">{html.escape(no)}</a>'
    url = f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={no}&bidPbancOrd=000"
    return (
        f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener"'
        f' title="나라장터 원문 (AI 분류 밖이거나 미수집)">{html.escape(no)} ↗</a>'
    )


def render_row(p: dict[str, Any], status: str, details: dict[str, str] | None = None, extras: str = "") -> str:
    files = " ".join(
        f'<a href="{html.escape(u, quote=True)}" rel="noopener">{i}</a>'
        for i, u in enumerate(p.get("spec_files") or [], 1)
    )
    bids = " ".join(_bid_link(b, details or {}) for b in p.get("bid_nos") or [])
    close = (p.get("opinion_close_at") or "")[:10]
    style = "color:var(--accent)" if status == STATUS_OPEN else "color:var(--muted)"
    return (
        f'<tr id="p-{html.escape(p.get("prespec_no") or "")}">'
        f"<td>{html.escape(p.get('registered_date') or '')}</td>"
        f"<td>{html.escape(close)}</td>"
        f'<td style="{style};white-space:nowrap" title="{html.escape(STATUS_TITLE[status])}">'
        f"{html.escape(status)}</td>"
        f"<td>{html.escape(p.get('org') or '')}</td>"
        f"<td>{html.escape(p.get('title') or '')}"
        f"{extras}"
        f'<div class="meta">{html.escape(p.get("prespec_no") or "")}'
        f'{" · " + html.escape(p["biz_div"]) if p.get("biz_div") else ""}</div></td>'
        f"<td>{html.escape(p.get('scope') or '')}</td>"
        f'<td class="num">{_fmt_budget(p.get("asign_budget_eok"))}</td>'
        f"<td>{files}</td>"
        f"<td>{bids}</td>"
        "</tr>"
    )


def stamp_for(status: dict[str, Any]) -> str:
    return stage_stamp((status.get("stages") or {}).get("prespecs") or {})


def render_prespecs_html(
    prespecs: list[dict[str, Any]],
    run_status: dict[str, Any],
    now: datetime | None = None,
    details: dict[str, str] | None = None,
    summaries: dict[str, dict[str, Any]] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    """details: 공고번호 → bids/ slug for notices that have a 사업 상세 page."""
    from .classify import apply_summary_labels
    from .normalize import list_excluded

    if now is None:
        now = datetime.now(KST)
    rules = load_keywords()
    lo, hi = rules["filters"]["band_min_eok"], rules["filters"]["band_max_eok"]
    rows = sorted(
        (p for p in prespecs if not list_excluded(p, rules)),
        key=lambda p: p.get("registered_at") or "",
        reverse=True,
    )
    summaries = summaries or {}
    statuses = [prespec_status(p, now) for p in rows]
    budgets = [p.get("asign_budget_eok") or 0 for p in rows]
    n_open = statuses.count(STATUS_OPEN)
    n_bid = statuses.count(STATUS_BID)
    n_band = sum(1 for b in budgets if lo <= b <= hi)
    since = min((p.get("registered_date") or "" for p in rows), default="")

    stats = (
        '<div class="stats">'
        + stat(f"{len(rows):,}건", f"AI 사전규격 ({since} 이후)" if since else "AI 사전규격")
        + stat(f"{n_open:,}건", "의견 접수 중")
        + stat(f"{n_band:,}건", f"배정예산 {lo:g}~{hi:g}억")
        + stat(f"{n_bid:,}건", "본공고 게시")
        + stat(f"{round(sum(budgets)):,}억", "배정예산 합계")
        + "</div>"
    )
    def _entry(p: dict[str, Any]) -> dict[str, Any] | None:
        hit = summaries.get(p.get("prespec_no"))
        if hit:
            return hit
        for b in p.get("bid_nos") or []:
            hit = summaries.get(str(b).split("-")[0])
            if hit:
                return hit
        return None

    def _extras(p: dict[str, Any], entry: dict[str, Any] | None) -> str:
        summary = ((entry or {}).get("summary") or {})
        overview = str(summary.get("overview") or "").strip()
        tech = ", ".join(summary.get("tech") or [])
        line = ""
        if overview:
            line += f'<div class="meta">{html.escape(overview[:180])}{"…" if len(overview) > 180 else ""}</div>'
        if tech:
            line += f'<div class="meta">{html.escape(tech)}</div>'
        if not profile or now is None:
            return line
        from .gonogo_policy import GO, NO_GO, REVIEW, score_policy

        scored = score_policy(p, profile, now, summary=entry)
        participate = {GO: "참여", REVIEW: "검토", NO_GO: "보류"}.get(
            scored["verdict"], scored["verdict"]
        )
        # N-13: stop-driven 보류 shows reason instead of a confusing high score.
        if scored["verdict"] == NO_GO and scored.get("stops"):
            fit_text = f'{participate} · {scored["stops"][0]}'
        else:
            fit_text = f'{participate} {scored["score"]}점'
        line += (
            f'<div class="meta">적합도 <span class="fit-pill" data-verdict="{html.escape(scored["verdict"])}">'
            f"{html.escape(fit_text)}</span></div>"
        )
        return line

    labeled = []
    extras = []
    for p in rows:
        entry = _entry(p)
        shown = dict(p)
        if shown.get("budget_eok") is None:
            shown["budget_eok"] = shown.get("asign_budget_eok")
        apply_summary_labels(shown, entry, rules)
        labeled.append(shown)
        extras.append(_extras(shown, entry))
    body_rows = "".join(
        render_row(p, s, details, extra) for p, s, extra in zip(labeled, statuses, extras)
    )
    table = (
        '<div class="tbl"><table class="notices prespecs js-filter">'
        f"{THEAD}<tbody>{body_rows}</tbody></table></div>"
        if rows
        else '<p class="note">수집된 사전규격이 아직 없습니다.</p>'
    )
    body = (
        '<div class="eyebrow">사전규격</div><h1>AI 사업 사전규격</h1>'
        '<p class="lede">본공고 전에 공개되는 사전규격(규격서 초안)입니다. '
        "의견등록 마감 전이면 규격에 의견을 낼 수 있고, 규격서로 본공고 RFP를 미리 볼 수 있습니다.</p>"
        f'<div class="stamp">{html.escape(stamp_for(run_status))}</div>'
        + stats
        + "<h2>사전규격 목록</h2>"
        '<p class="note">상태로 거르면 의견 접수 중인 건만 볼 수 있습니다. '
        "물품은 SW 납품이 분명한 건만 포함하고, GPU·서버 등 장비 구매와 교육·행사성 용역은 제외합니다.</p>"
        + table
    )
    return page(
        "AI 사업 사전규격",
        body,
        path="prespecs.html",
        scripts=("table-sort.js", "table-filter.js"),
    )


def detail_index(repo_root: Path) -> dict[str, str]:
    from .detail import load_detail_notices
    from .site import detail_slug

    return {n["bid_no"]: detail_slug(n) for n in load_detail_notices(repo_root)}


def render_prespecs_page(repo_root: Path) -> dict[str, Any]:
    from .gonogo import load_profile
    from .rfp import load_summaries

    prespecs = load_prespecs(repo_root)
    path = repo_root / "prespecs.html"
    path.write_text(
        render_prespecs_html(
            prespecs,
            load_run_status(repo_root),
            details=detail_index(repo_root),
            summaries=load_summaries(repo_root),
            profile=load_profile(),
        ),
        encoding="utf-8",
    )
    return {"path": str(path), "prespecs": len(prespecs)}

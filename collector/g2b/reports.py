"""Phase C: render weekly/monthly report HTML + reports.json from notices."""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .render import (
    KST,
    _bars_html,
    _fmt_budget,
    _fmt_num,
    _g2b_href,
    _parse_date,
    _today_kst,
)
from .assets import ASSET_VER

# 핵심 AI 사업 성격 (주간 「신규」·월간 「AI 사업」). 교육·장비·미분류는 기타.
CORE_NATURES = frozenset(
    {
        "시스템 구축·고도화",
        "ISP·전략",
        "구독·라이선스",
        "운영·유지보수",
    }
)

NATURE_LABELS = {
    "ISP·전략": "ISP·전략·컨설팅",
    "인프라": "인프라(GPU·서버·장비)",
    None: "기타",
    "": "기타",
}

_RANK_SUFFIX_RE = re.compile(r"\s*\([12]순위\)\s*$")

NAV = (
    '<nav class="top"><b>공공 AI Agent 시장 리서치</b>'
    '<a href="../index.html">홈</a>'
    '<a href="../band.html">8~30억 분석</a>'
    '<a href="../awards.html">수주 현황</a>'
    '<a href="../competitors.html">국내 전문기업</a>'
    '<a href="../reports/index.html">리포트 목록</a>'
    '<a href="../deliverables.html">산출물 안내</a></nav>'
)

FOOTER = (
    "<footer>데이터 출처: 조달청 나라장터 입찰공고·낙찰정보(공공데이터포털 Open API), "
    "각 사 공식 발표·보도자료. 사업명 기준 자동 분류라 일부 오분류가 있을 수 있습니다. "
    "확인하지 못한 항목은 '미확인'으로 표시합니다.</footer>"
)

HEAD_TMPL = (
    "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "<title>{title}</title>"
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@500&display=swap\">"
    '<meta http-equiv="Cache-Control" content="no-cache">'
    f'<link rel="stylesheet" href="../assets/site.css?v={ASSET_VER}"></head><body>'
    '<div class="wrap">'
)

SCRIPT = f'<script src="../assets/table-sort.js?v={ASSET_VER}" defer></script>'


def sane_budget(v: Any) -> float | None:
    """예산(억). 1e5 이상은 원으로 잘못 저장된 값으로 보고 억 환산."""
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n >= 1e5:
        return round(n / 1e8, 4)
    return n


def nature_label(nature: str | None) -> str:
    if nature in NATURE_LABELS:
        return NATURE_LABELS[nature]
    if not nature:
        return "기타"
    return nature


def clean_bidder_name(name: str | None) -> str:
    if not name:
        return ""
    return _RANK_SUFFIX_RE.sub("", str(name)).strip()


def notice_bidder_names(notice: dict[str, Any]) -> set[str]:
    """Firm names that bid on a notice (OpengCompt bidders[], else winner/second)."""
    names: set[str] = set()
    for b in notice.get("bidders") or []:
        raw = b.get("name") if isinstance(b, dict) else b
        nm = clean_bidder_name(raw if isinstance(raw, str) else str(raw or ""))
        if nm:
            names.add(nm)
    if names:
        return names
    for fld in ("winner", "second"):
        nm = clean_bidder_name(notice.get(fld))
        if nm:
            names.add(nm)
    return names


def aggregate_month_bidders(
    notices: list[dict[str, Any]],
    start: date,
    end: date,
    *,
    limit: int = 15,
) -> list[tuple[str, int]]:
    """Rank firms by distinct open_date-in-range notices they bid on."""
    by_firm: dict[str, set[str]] = defaultdict(set)
    for n in notices:
        if not _in_range(n.get("open_date"), start, end):
            continue
        key = f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"
        if not n.get("bid_no"):
            key = f"t:{n.get('title')}|{n.get('open_date')}"
        for nm in notice_bidder_names(n):
            by_firm[nm].add(key)
    ranked = sorted(
        ((name, len(keys)) for name, keys in by_firm.items() if name),
        key=lambda x: (-x[1], x[0]),
    )
    return ranked[:limit]


def is_core(notice: dict[str, Any]) -> bool:
    return notice.get("nature") in CORE_NATURES


def load_notices(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "data" / "notices.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    return list(raw.get("notices") or [])


def iso_week_bounds(year: int, week: int) -> tuple[date, date]:
    """ISO week Mon..Sun."""
    start = date.fromisocalendar(year, week, 1)
    return start, start + timedelta(days=6)


def last_completed_iso_week(today: date | None = None) -> tuple[int, int]:
    """직전 완료된 ISO 주 (월~일). 오늘이 월요일이면 지난주."""
    today = today or _today_kst()
    # ISO week containing yesterday's Monday-Sunday completed period:
    # use (today - 1 day) if today is Monday else go to last Sunday then get that week.
    last_sunday = today - timedelta(days=(today.weekday() + 1) % 7 or 7)
    y, w, _ = last_sunday.isocalendar()
    return y, w


def _in_range(s: str | None, start: date, end: date) -> bool:
    d = _parse_date(s)
    return d is not None and start <= d <= end


def _budget_sum(rows: list[dict[str, Any]]) -> float:
    return round(sum(sane_budget(n.get("budget_eok")) or 0.0 for n in rows), 1)


def _sort_by_budget(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda n: (
            -(sane_budget(n.get("budget_eok")) or 0.0),
            n.get("notice_date") or "",
            n.get("title") or "",
        ),
    )


def _title_link(notice: dict[str, Any]) -> str:
    title = html.escape(notice.get("title") or "")
    href = _g2b_href(notice)
    if href:
        return f'<a href="{href}" target="_blank" rel="noopener">{title}</a>'
    return title


def _fmt_int_comma(n: int | float) -> str:
    return f"{int(round(n)):,}"


def _fmt_budget_sum(n: float) -> str:
    """합계 표시: 1,112.9 / 1,083."""
    if abs(n - round(n)) < 0.05:
        return _fmt_int_comma(n)
    return f"{n:,.1f}"


def _page(title: str, body: str, with_sort: bool = True) -> str:
    tail = f"</div>{SCRIPT}</body></html>" if with_sort else "</div></body></html>"
    return HEAD_TMPL.format(title=html.escape(title)) + NAV + body + FOOTER + tail


# --- weekly -----------------------------------------------------------------


def aggregate_weekly(
    notices: list[dict[str, Any]],
    year: int,
    week: int,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or _today_kst()
    start, end = iso_week_bounds(year, week)
    in_week = [n for n in notices if _in_range(n.get("notice_date"), start, end)]
    core = _sort_by_budget([n for n in in_week if is_core(n)])
    other = [n for n in in_week if not is_core(n)]
    gen = sum(1 for n in core if n.get("scope") == "생성형·Agent")

    awards = [
        n
        for n in notices
        if _in_range(n.get("open_date"), start, end) and n.get("winner")
    ]
    awards.sort(
        key=lambda n: (
            -(sane_budget(n.get("award_amount_eok")) or sane_budget(n.get("budget_eok")) or 0.0),
            n.get("open_date") or "",
        )
    )

    up_start = end + timedelta(days=1)
    up_end = end + timedelta(days=15)
    upcoming = [
        n
        for n in notices
        if _in_range(n.get("open_date"), up_start, up_end)
        and is_core(n)
        and (sane_budget(n.get("budget_eok")) or 0.0) >= 1.0
    ]
    upcoming.sort(
        key=lambda n: (n.get("open_date") or "", -(sane_budget(n.get("budget_eok")) or 0.0))
    )

    # 개찰됐지만 낙찰 미확정 / 유찰 notes
    opened = [n for n in notices if _in_range(n.get("open_date"), start, end)]
    failed = sum(1 for n in opened if n.get("status") == "유찰")
    pending = sum(
        1
        for n in opened
        if not n.get("winner") and n.get("status") not in ("유찰",)
        and is_core(n)
    )

    return {
        "year": year,
        "week": week,
        "start": start,
        "end": end,
        "today": today,
        "core": core,
        "other_count": len(other),
        "gen_count": gen,
        "budget_sum": _budget_sum(core),
        "awards": awards,
        "upcoming": upcoming,
        "failed_count": failed,
        "pending_count": pending,
        "slug": f"weekly-{year}-W{week:02d}",
    }


def _weekly_core_rows(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for n in rows:
        bud = sane_budget(n.get("budget_eok"))
        parts.append(
            "<tr>"
            f"<td>{html.escape(n.get('notice_date') or '')}</td>"
            f"<td>{html.escape(n.get('org') or '')}</td>"
            f"<td>{_title_link(n)}</td>"
            f"<td>{html.escape(nature_label(n.get('nature')))}</td>"
            f'<td class="num">{_fmt_budget(bud) if bud is not None else ""}</td>'
            f"<td>{html.escape(n.get('open_date') or '')}</td>"
            "</tr>"
        )
    return "".join(parts)


def _weekly_award_rows(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for n in rows:
        winner = html.escape(n.get("winner") or "")
        status = n.get("status") or ""
        if status == "1순위" or (
            n.get("winner") and not n.get("award_amount_eok") and status != "낙찰"
        ):
            winner = f'{winner} <span class="meta">(1순위)</span>'
        amt = sane_budget(n.get("award_amount_eok"))
        bid_count = n.get("bid_count")
        try:
            bid_s = str(int(float(bid_count))) if bid_count not in (None, "") else ""
        except (TypeError, ValueError):
            bid_s = html.escape(str(bid_count))
        second = html.escape(n.get("second") or "")
        parts.append(
            "<tr>"
            f"<td>{html.escape(n.get('open_date') or '')}</td>"
            f"<td>{html.escape(n.get('org') or '')}</td>"
            f"<td>{html.escape(n.get('title') or '')}</td>"
            f"<td>{winner}</td>"
            f'<td class="num">{_fmt_budget(amt) if amt is not None else ""}</td>'
            f'<td class="num">{bid_s}</td>'
            f"<td>{second}</td>"
            "</tr>"
        )
    return "".join(parts)


def _weekly_upcoming_rows(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for n in rows:
        bud = sane_budget(n.get("budget_eok"))
        parts.append(
            "<tr>"
            f"<td>{html.escape(n.get('open_date') or '')}</td>"
            f"<td>{html.escape(n.get('org') or '')}</td>"
            f"<td>{_title_link(n)}</td>"
            f"<td>{html.escape(n.get('contract_method') or '')}</td>"
            f'<td class="num">{_fmt_budget(bud) if bud is not None else ""}</td>'
            "</tr>"
        )
    return "".join(parts)


def render_weekly_html(agg: dict[str, Any]) -> str:
    y, w = agg["year"], agg["week"]
    start: date = agg["start"]
    end: date = agg["end"]
    title = f"주간 브리프 {y}-W{w:02d}"
    eyebrow = f"주간 브리프 · {y}년 {w}주차"
    lede = (
        f"{start.isoformat()} ~ {end.isoformat()} 나라장터에 올라온 AI 사업 공고"
        "(생성형·Agent + AI SW 확대)와 개찰 결과입니다."
    )
    core_n = len(agg["core"])
    gen = agg["gen_count"]
    bud = agg["budget_sum"]
    other = agg["other_count"]
    awards_n = len(agg["awards"])

    stats = (
        '<div class="stats">'
        f'<div class="stat"><div class="v">{core_n}건</div>'
        f'<div class="l">신규 AI 사업 공고 (생성형·Agent {gen}건)</div></div>'
        f'<div class="stat"><div class="v">{_fmt_num(bud)}억</div>'
        f'<div class="l">신규 공고 예산 합계</div></div>'
        f'<div class="stat"><div class="v">{other}건</div>'
        f'<div class="l">기타 AI 공고 (교육·장비 등)</div></div>'
        f'<div class="stat"><div class="v">{awards_n}건</div>'
        f'<div class="l">낙찰자 확인된 개찰</div></div>'
        "</div>"
    )

    core_table = (
        '<h2>신규 AI 사업 공고</h2><div class="tbl"><table class="notices">'
        "<thead><tr><th>공고일</th><th>수요기관</th><th>사업명</th><th>성격</th>"
        '<th class="num">예산(억)</th><th>개찰 예정</th></tr></thead>'
        f"<tbody>{_weekly_core_rows(agg['core'])}</tbody></table></div>"
    )
    award_table = (
        '<h2>개찰 결과</h2><div class="tbl"><table class="notices">'
        "<thead><tr><th>개찰일</th><th>수요기관</th><th>사업명</th><th>낙찰자</th>"
        '<th class="num">낙찰금액(억)</th><th class="num">투찰 수</th><th>2순위</th>'
        "</tr></thead>"
        f"<tbody>{_weekly_award_rows(agg['awards'])}</tbody></table></div>"
    )
    notes = ""
    if agg["failed_count"]:
        notes += (
            f'<p class="note">같은 기간 유찰된 핵심 공고: {agg["failed_count"]}건.</p>'
        )
    if agg["pending_count"]:
        notes += (
            f'<p class="note">같은 기간 개찰됐지만 낙찰 확정 전이거나 결과가 아직 '
            f'등록되지 않은 핵심 공고: {agg["pending_count"]}건'
            "(다음 주 리포트에서 다시 확인).</p>"
        )
    up_table = (
        '<h2>다가오는 개찰 (향후 15일, 예산 1억 이상)</h2>'
        '<div class="tbl"><table class="notices">'
        "<thead><tr><th>개찰 예정</th><th>수요기관</th><th>사업명</th><th>계약방법</th>"
        '<th class="num">예산(억)</th></tr></thead>'
        f"<tbody>{_weekly_upcoming_rows(agg['upcoming'])}</tbody></table></div>"
    )
    body = (
        f'<div class="eyebrow">{html.escape(eyebrow)}</div>'
        f"<h1>공공 AI Agent 주간 브리프</h1>"
        f'<p class="lede">{html.escape(lede)}</p>'
        f"{stats}{core_table}{award_table}{notes}{up_table}"
    )
    return _page(title, body)


# --- monthly ----------------------------------------------------------------


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def aggregate_monthly(
    notices: list[dict[str, Any]],
    year: int,
    month: int,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or _today_kst()
    start, month_end = _month_bounds(year, month)
    # 진행 중 월이면 오늘까지
    end = min(month_end, today)
    in_month = [
        n
        for n in notices
        if _in_range(n.get("notice_date"), start, end) and is_core(n)
    ]
    in_month = _sort_by_budget(in_month)

    py, pm = _prev_month(year, month)
    p_start, p_end = _month_bounds(py, pm)
    prev_core = [
        n
        for n in notices
        if _in_range(n.get("notice_date"), p_start, p_end) and is_core(n)
    ]

    # 12개월 추이 (해당 월 포함 역방향)
    trend: list[dict[str, Any]] = []
    cursor = date(year, month, 1)
    for _ in range(12):
        ys, ms = cursor.year, cursor.month
        s, e = _month_bounds(ys, ms)
        e_eff = min(e, today) if (ys, ms) == (year, month) else e
        rows = [
            n
            for n in notices
            if _in_range(n.get("notice_date"), s, e_eff) and is_core(n)
        ]
        gen = sum(1 for n in rows if n.get("scope") == "생성형·Agent")
        sw = len(rows) - gen
        trend.append(
            {
                "year": ys,
                "month": ms,
                "label": f"{ys % 100:02d}.{ms:02d}",
                "ym": f"{ys}-{ms:02d}",
                "count": len(rows),
                "gen": gen,
                "sw": sw,
            }
        )
        # step back one month
        cursor = s - timedelta(days=1)
        cursor = date(cursor.year, cursor.month, 1)
    trend.reverse()

    natures = Counter(nature_label(n.get("nature")) for n in in_month)
    nature_list = sorted(natures.items(), key=lambda x: (-x[1], x[0]))
    fields: Counter[str] = Counter()
    for n in in_month:
        fs = n.get("fields") or ["AI 일반"]
        if isinstance(fs, str):
            fs = [fs]
        for f in fs:
            fields[f] += 1
    field_list = sorted(fields.items(), key=lambda x: (-x[1], x[0]))

    top10 = in_month[:10]
    orgs = Counter(n.get("org") or "미상" for n in in_month)
    top_orgs = sorted(orgs.items(), key=lambda x: (-x[1], x[0]))[:10]

    isp = _sort_by_budget([n for n in in_month if n.get("nature") == "ISP·전략"])

    # 낙찰: 개찰일이 이번 달
    winners_rows = [
        n
        for n in notices
        if _in_range(n.get("open_date"), start, end) and n.get("winner")
    ]
    by_winner: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "amount": 0.0}
    )
    for n in winners_rows:
        name = (n.get("winner") or "").strip()
        if not name:
            continue
        by_winner[name]["count"] = int(by_winner[name]["count"]) + 1
        by_winner[name]["amount"] = float(by_winner[name]["amount"]) + (
            sane_budget(n.get("award_amount_eok")) or 0.0
        )
    winners = sorted(
        ((k, int(v["count"]), float(v["amount"])) for k, v in by_winner.items()),
        key=lambda x: (-x[1], -x[2], x[0]),
    )

    # 투찰 참가: core AI 공고의 OpengCompt bidders[] (없으면 winner/second)
    bidders = aggregate_month_bidders(
        [n for n in notices if is_core(n)], start, end, limit=15
    )

    large = sum(1 for n in in_month if (sane_budget(n.get("budget_eok")) or 0) >= 10)
    in_progress = end < month_end

    return {
        "year": year,
        "month": month,
        "start": start,
        "end": end,
        "month_end": month_end,
        "today": today,
        "in_progress": in_progress,
        "core": in_month,
        "budget_sum": _budget_sum(in_month),
        "prev_count": len(prev_core),
        "prev_budget": _budget_sum(prev_core),
        "large_count": large,
        "isp_count": len(isp),
        "isp": isp,
        "trend": trend,
        "natures": nature_list,
        "fields": field_list,
        "top10": top10,
        "top_orgs": top_orgs,
        "winners": winners,
        "bidders": bidders,
        "slug": f"monthly-{year}-{month:02d}",
    }


def _month_bars_html(trend: list[dict[str, Any]]) -> str:
    if not trend:
        return '<div class="bars"></div>'
    top = max((t["count"] for t in trend), default=1) or 1
    parts = ['<div class="bars">']
    for t in trend:
        pct = 100.0 * t["count"] / top
        parts.append(
            f'<div class="bar"><span>{html.escape(t["label"])}</span>'
            f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="n">{t["count"]}건</span></div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _trend_scope_table(trend: list[dict[str, Any]]) -> str:
    rows = "".join(
        f'<tr><td>{html.escape(t["ym"])}</td>'
        f'<td class="num">{t["gen"]}</td>'
        f'<td class="num">{t["sw"]}</td></tr>'
        for t in trend
    )
    return (
        '<div class="tbl"><table class="rank"><thead><tr>'
        "<th>월</th>"
        '<th class="num">생성형·Agent</th>'
        '<th class="num">AI SW 확대</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _top10_rows(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for n in rows:
        bud = sane_budget(n.get("budget_eok"))
        parts.append(
            "<tr>"
            f"<td>{html.escape(n.get('notice_date') or '')}</td>"
            f"<td>{html.escape(n.get('org') or '')}</td>"
            f"<td>{_title_link(n)}</td>"
            f"<td>{html.escape(nature_label(n.get('nature')))}</td>"
            f'<td class="num">{_fmt_budget(bud) if bud is not None else ""}</td>'
            "</tr>"
        )
    return "".join(parts)


def _org_rows(orgs: list[tuple[str, int]]) -> str:
    return "".join(
        f"<tr><td>{html.escape(name)}</td>"
        f'<td class="num">{count}</td></tr>'
        for name, count in orgs
    )


def _isp_rows(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for n in rows:
        bud = sane_budget(n.get("budget_eok"))
        parts.append(
            "<tr>"
            f"<td>{html.escape(n.get('notice_date') or '')}</td>"
            f"<td>{html.escape(n.get('org') or '')}</td>"
            f"<td>{_title_link(n)}</td>"
            f'<td class="num">{_fmt_budget(bud) if bud is not None else ""}</td>'
            "</tr>"
        )
    return "".join(parts)


def _winner_rows(rows: list[tuple[str, int, float]]) -> str:
    return "".join(
        f"<tr><td>{html.escape(name)}</td>"
        f'<td class="num">{count}</td>'
        f'<td class="num">{_fmt_budget(amount)}</td></tr>'
        for name, count, amount in rows
    )


def _bidder_rows(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return ""
    return "".join(
        f"<tr><td>{html.escape(name)}</td>"
        f'<td class="num">{count}</td></tr>'
        for name, count in rows
    )


def render_monthly_html(agg: dict[str, Any]) -> str:
    y, m = agg["year"], agg["month"]
    end: date = agg["end"]
    in_prog = agg["in_progress"]
    title = f"월간 리포트 {y}-{m:02d}"
    eyebrow = f"월간 리포트 · {y}년 {m}월" + (" (진행 중)" if in_prog else "")
    day_span = (
        f"{y}년 {m}월 1~{end.day}일"
        if in_prog
        else f"{y}년 {m}월"
    )
    lede = (
        f"{day_span} 나라장터 AI 사업 공고(생성형·Agent + AI SW 확대) 동향, "
        "대형 사업, 발주 기관, 수주 현황입니다."
    )
    n = len(agg["core"])
    bud = agg["budget_sum"]
    prev_n = agg["prev_count"]
    prev_b = agg["prev_budget"]
    bud_disp = _fmt_budget_sum(bud)
    prev_disp = _fmt_budget_sum(prev_b)
    stats = (
        '<div class="stats">'
        f'<div class="stat"><div class="v">{n}건</div>'
        f'<div class="l">AI 사업 공고 (전월 {prev_n}건)</div></div>'
        f'<div class="stat"><div class="v">{bud_disp}억</div>'
        f'<div class="l">공고 예산 합계 (전월 {prev_disp}억)</div></div>'
        f'<div class="stat"><div class="v">{agg["large_count"]}건</div>'
        f'<div class="l">10억 원 이상 사업</div></div>'
        f'<div class="stat"><div class="v">{agg["isp_count"]}건</div>'
        f'<div class="l">ISP·전략 공고 (후속 본사업 후보)</div></div>'
        "</div>"
    )

    trend_sec = (
        "<h2>최근 12개월 공고 추이</h2>"
        f"{_month_bars_html(agg['trend'])}"
        '<p class="note">월별 AI 사업 공고 수(생성형·Agent + AI SW 확대, 공고일 기준). '
        "수집 기간 밖의 월은 0건일 수 있습니다.</p>"
        f"{_trend_scope_table(agg['trend'])}"
    )
    nature_sec = (
        "<h2>사업 성격</h2>"
        f"{_bars_html(agg['natures'])}"
    )
    field_sec = (
        "<h2>분야</h2>"
        f"{_bars_html(agg['fields'])}"
        '<p class="note">한 사업이 여러 분야에 걸리면 각각 셉니다.</p>'
    )
    top_sec = (
        "<h2>예산 상위 10개 사업</h2>"
        '<div class="tbl"><table class="notices"><thead><tr>'
        "<th>공고일</th><th>수요기관</th><th>사업명</th><th>성격</th>"
        '<th class="num">예산(억)</th></tr></thead>'
        f"<tbody>{_top10_rows(agg['top10'])}</tbody></table></div>"
    )
    org_sec = (
        "<h2>발주 기관 상위 10</h2>"
        '<div class="tbl"><table class="rank"><thead><tr>'
        '<th>수요기관</th><th class="num">공고 수</th></tr></thead>'
        f"<tbody>{_org_rows(agg['top_orgs'])}</tbody></table></div>"
    )
    isp_sec = (
        "<h2>ISP·전략 공고</h2>"
        '<div class="tbl"><table class="notices"><thead><tr>'
        '<th>공고일</th><th>수요기관</th><th>사업명</th>'
        '<th class="num">예산(억)</th></tr></thead>'
        f"<tbody>{_isp_rows(agg['isp'])}</tbody></table></div>"
    )
    win_sec = (
        "<h2>이번 달 낙찰 업체</h2>"
        '<div class="tbl"><table class="rank"><thead><tr>'
        "<th>낙찰 업체</th>"
        '<th class="num">낙찰 건수</th>'
        '<th class="num">낙찰금액 합계(억)</th></tr></thead>'
        f"<tbody>{_winner_rows(agg['winners'])}</tbody></table></div>"
    )
    if agg["bidders"]:
        bid_sec = (
            "<h2>이번 달 투찰 참여 업체</h2>"
            '<div class="tbl"><table class="rank"><thead><tr>'
            '<th>업체</th><th class="num">투찰 공고 수</th></tr></thead>'
            f"<tbody>{_bidder_rows(agg['bidders'])}</tbody></table></div>"
            '<p class="note">개찰일이 이번 달인 핵심 AI 공고(구축·ISP·구독·운영)의 '
            "나라장터 개찰 결과의 투찰업체 목록 기준입니다(목록이 없는 공고는 낙찰·2순위 업체만 셉니다).</p>"
        )
    else:
        bid_sec = (
            "<h2>이번 달 투찰 참여 업체</h2>"
            '<p class="note">이번 달 개찰 공고에 투찰업체 목록이 아직 없습니다. '
            "`enrich-bidders` 후 다시 렌더하세요.</p>"
        )

    body = (
        f'<div class="eyebrow">{html.escape(eyebrow)}</div>'
        f"<h1>공공 AI Agent 월간 리포트</h1>"
        f'<p class="lede">{html.escape(lede)}</p>'
        f"{stats}{trend_sec}{nature_sec}{field_sec}{top_sec}{org_sec}"
        f"{isp_sec}{win_sec}{bid_sec}"
    )
    return _page(title, body)


# --- index + orchestrator ---------------------------------------------------


def _discover_existing_reports(reports_dir: Path) -> dict[str, list[dict[str, Any]]]:
    weekly: list[dict[str, Any]] = []
    monthly: list[dict[str, Any]] = []
    for p in sorted(reports_dir.glob("weekly-*.html"), reverse=True):
        # weekly-2026-W43.html
        stem = p.stem  # weekly-2026-W43
        parts = stem.split("-")
        if len(parts) >= 3 and parts[2].startswith("W"):
            try:
                year = int(parts[1])
                week = int(parts[2][1:])
            except ValueError:
                continue
            weekly.append({"year": year, "week": week, "file": p.name, "slug": stem})
    for p in sorted(reports_dir.glob("monthly-*.html"), reverse=True):
        stem = p.stem  # monthly-2026-10
        parts = stem.split("-")
        if len(parts) >= 3:
            try:
                year = int(parts[1])
                month = int(parts[2])
            except ValueError:
                continue
            monthly.append({"year": year, "month": month, "file": p.name, "slug": stem})
    return {"weekly": weekly, "monthly": monthly}


def render_reports_index(
    repo_root: Path,
    weekly_meta: list[dict[str, Any]],
    monthly_meta: list[dict[str, Any]],
) -> str:
    def week_card(m: dict[str, Any]) -> str:
        start, end = iso_week_bounds(m["year"], m["week"])
        core_n = m.get("core_count", "?")
        bud = m.get("budget_sum", "?")
        awards_n = m.get("awards_count", "?")
        return (
            f'<a class="card" href="{html.escape(m["file"])}">'
            f'<span class="k">주간 · {start.isoformat()} ~ {end.isoformat()}</span>'
            f"<span><b>주간 브리프 {m['year']}년 {m['week']}주차</b>"
            f'<span class="d">신규 핵심 공고 {core_n}건, 예산 {bud}억, '
            f'개찰 결과 {awards_n}건</span></span>'
            '<span class="go">열기 →</span></a>'
        )

    def month_card(m: dict[str, Any]) -> str:
        prog = " (진행 중)" if m.get("in_progress") else ""
        core_n = m.get("core_count", "?")
        bud = m.get("budget_sum", "?")
        bud_s = _fmt_budget_sum(bud) if isinstance(bud, (int, float)) else str(bud)
        return (
            f'<a class="card" href="{html.escape(m["file"])}">'
            f'<span class="k">월간 · {m["year"]}-{m["month"]:02d}</span>'
            f"<span><b>월간 리포트 {m['year']}년 {m['month']}월{prog}</b>"
            f'<span class="d">핵심 공고 {core_n}건, 예산 {bud_s}억</span></span>'
            '<span class="go">열기 →</span></a>'
        )

    w_cards = "".join(week_card(m) for m in weekly_meta) or (
        '<p class="note">주간 리포트가 아직 없습니다.</p>'
    )
    m_cards = "".join(month_card(m) for m in monthly_meta) or (
        '<p class="note">월간 리포트가 아직 없습니다.</p>'
    )
    body = (
        '<div class="eyebrow">리포트 목록</div><h1>전체 리포트</h1>'
        f'<h2>주간</h2><div class="cards">{w_cards}</div>'
        f'<h2>월간</h2><div class="cards">{m_cards}</div>'
    )
    return _page("리포트 목록", body, with_sort=False)


def render_reports(
    repo_root: Path,
    *,
    week: tuple[int, int] | None = None,
    month: tuple[int, int] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Generate weekly + monthly HTML, reports/index.html, data/reports.json."""
    today = today or _today_kst()
    notices = load_notices(repo_root)
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if week is None:
        week = last_completed_iso_week(today)
    if month is None:
        month = (today.year, today.month)

    w_agg = aggregate_weekly(notices, week[0], week[1], today=today)
    m_agg = aggregate_monthly(notices, month[0], month[1], today=today)

    weekly_path = reports_dir / f"{w_agg['slug']}.html"
    monthly_path = reports_dir / f"{m_agg['slug']}.html"
    weekly_path.write_text(render_weekly_html(w_agg), encoding="utf-8")
    monthly_path.write_text(render_monthly_html(m_agg), encoding="utf-8")

    # Merge with any other already-rendered report files for the index
    existing = _discover_existing_reports(reports_dir)
    weekly_meta: list[dict[str, Any]] = []
    for item in existing["weekly"]:
        meta = {
            "year": item["year"],
            "week": item["week"],
            "file": item["file"],
            "slug": item["slug"],
        }
        if item["slug"] == w_agg["slug"]:
            meta.update(
                {
                    "core_count": len(w_agg["core"]),
                    "budget_sum": w_agg["budget_sum"],
                    "awards_count": len(w_agg["awards"]),
                    "other_count": w_agg["other_count"],
                    "start": w_agg["start"].isoformat(),
                    "end": w_agg["end"].isoformat(),
                }
            )
        weekly_meta.append(meta)

    monthly_meta: list[dict[str, Any]] = []
    for item in existing["monthly"]:
        meta = {
            "year": item["year"],
            "month": item["month"],
            "file": item["file"],
            "slug": item["slug"],
        }
        if item["slug"] == m_agg["slug"]:
            meta.update(
                {
                    "core_count": len(m_agg["core"]),
                    "budget_sum": m_agg["budget_sum"],
                    "large_count": m_agg["large_count"],
                    "isp_count": m_agg["isp_count"],
                    "in_progress": m_agg["in_progress"],
                    "start": m_agg["start"].isoformat(),
                    "end": m_agg["end"].isoformat(),
                }
            )
        monthly_meta.append(meta)

    index_path = reports_dir / "index.html"
    index_path.write_text(
        render_reports_index(repo_root, weekly_meta, monthly_meta), encoding="utf-8"
    )

    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(KST).isoformat(),
        "weekly": weekly_meta,
        "monthly": monthly_meta,
        "core_natures": sorted(CORE_NATURES),
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    json_path = repo_root / "data" / "reports.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(payload, encoding="utf-8")
    # Legacy root copy (Pages / older links)
    (repo_root / "reports.json").write_text(payload, encoding="utf-8")

    return {
        "weekly": {
            "path": str(weekly_path),
            "slug": w_agg["slug"],
            "core": len(w_agg["core"]),
            "budget_sum_eok": w_agg["budget_sum"],
            "other": w_agg["other_count"],
            "awards": len(w_agg["awards"]),
            "upcoming": len(w_agg["upcoming"]),
        },
        "monthly": {
            "path": str(monthly_path),
            "slug": m_agg["slug"],
            "core": len(m_agg["core"]),
            "budget_sum_eok": m_agg["budget_sum"],
            "large": m_agg["large_count"],
            "isp": m_agg["isp_count"],
            "in_progress": m_agg["in_progress"],
        },
        "index": str(index_path),
        "reports_json": str(json_path),
    }

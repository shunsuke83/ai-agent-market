"""pricing.html: 낙찰률 분포·업체별 투찰 습관·경쟁 강도 from OpengCompt bidders[] in notices.json."""

from __future__ import annotations

import html
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from .classify import load_keywords
from .render import _fmt_budget, _today_kst, infer_status, load_run_status, stamp_text, title_link
from .site import page, stat

# OpengCompt fills rate_pct from bidPrceEvlVal (협상계약 가격평가 점수, ~8–20) when bidprcrt
# is empty, so only values in this band are 예정가격 대비 투찰률.
RATE_MIN = 50.0
RATE_MAX = 110.0
MIN_SAMPLE = 5
CONTEXT_MIN_ORG = 3
WEAK_DAYS = 365
FIRM_MIN_BIDS = 5
LIMIT = 30
SAMPLE_SHORT = '<span class="meta">표본 부족</span>'

BUDGET_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.0, 1.0, "1억 미만"),
    (1.0, 8.0, "1~8억"),
    (8.0, 30.0, "8~30억"),
    (30.0, float("inf"), "30억 이상"),
)


def bid_rate(b: dict[str, Any]) -> float | None:
    try:
        r = float(b.get("rate_pct"))
    except (TypeError, ValueError):
        return None
    return r if RATE_MIN <= r <= RATE_MAX else None


def budget_band(eok: Any) -> str | None:
    try:
        v = float(eok)
    except (TypeError, ValueError):
        return None
    for lo, hi, label in BUDGET_BANDS:
        if lo <= v < hi:
            return label
    return None


def bid_count(n: dict[str, Any]) -> int | None:
    try:
        c = int(float(n.get("bid_count") or 0))
    except (TypeError, ValueError):
        return None
    return c if c > 0 else None


def competitive(n: dict[str, Any]) -> bool:
    """수의계약 picks one vendor up front, so its bid count says nothing about competition."""
    return n.get("contract_method") != "수의계약"


def winner_bid(n: dict[str, Any]) -> dict[str, Any] | None:
    from .competitors import normalize_firm

    winner = normalize_firm(n.get("winner"))
    if not winner:
        return None
    for b in n.get("bidders") or []:
        if isinstance(b, dict) and normalize_firm(b.get("name")) == winner:
            return b
    return None


def winner_rate(n: dict[str, Any]) -> float | None:
    b = winner_bid(n)
    return bid_rate(b) if b else None


def quartiles(values: list[float]) -> tuple[float, float, float] | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0], values[0], values[0]
    q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q2, q3


def _firm_key(b: dict[str, Any]) -> str:
    from .competitors import normalize_firm

    return str(b.get("bizno") or "") or f"name:{normalize_firm(b.get('name'))}"


def rate_rows(
    notices: list[dict[str, Any]], key: Callable[[dict[str, Any]], str | None]
) -> list[dict[str, Any]]:
    """Winner 투찰률 quartiles per group; groups under MIN_SAMPLE keep n but no figures."""
    groups: dict[str, list[float]] = defaultdict(list)
    for n in notices:
        label = key(n)
        rate = winner_rate(n)
        if label and rate is not None:
            groups[label].append(rate)
    rows = []
    for label, vals in groups.items():
        q = quartiles(vals) if len(vals) >= MIN_SAMPLE else None
        rows.append({"label": label, "n": len(vals), "q": q})
    return rows


def competition_rows(
    notices: list[dict[str, Any]], key: Callable[[dict[str, Any]], str | None]
) -> list[dict[str, Any]]:
    """Bid counts per group: median, 75th percentile, 단독 응찰 share, 유찰 count.

    A few open tenders draw hundreds of bidders, so means are not shown.
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in notices:
        label = key(n)
        if label and competitive(n) and (bid_count(n) or n.get("status") == "유찰"):
            groups[label].append(n)
    rows = []
    for label, rows_n in groups.items():
        counts = [c for c in (bid_count(n) for n in rows_n) if c]
        failed = sum(1 for n in rows_n if n.get("status") == "유찰")
        enough = len(counts) >= MIN_SAMPLE
        q = quartiles([float(c) for c in counts]) if enough else None
        rows.append(
            {
                "label": label,
                "n": len(rows_n),
                "median": q[1] if q else None,
                "p75": q[2] if q else None,
                "single_pct": 100.0 * sum(1 for c in counts if c == 1) / len(counts) if enough else None,
                "failed": failed,
            }
        )
    return rows


def firm_habits(notices: list[dict[str, Any]], min_bids: int = FIRM_MIN_BIDS) -> list[dict[str, Any]]:
    """Per firm (사업자번호, else name): bids, median 투찰률, wins, median 낙찰 투찰률."""
    acc: dict[str, dict[str, Any]] = {}
    for n in notices:
        won = winner_bid(n)
        won_key = _firm_key(won) if won else None
        day = n.get("open_date") or n.get("notice_date") or ""
        seen: set[str] = set()
        for b in n.get("bidders") or []:
            if not isinstance(b, dict) or not b.get("name"):
                continue
            k = _firm_key(b)
            if k in seen:
                continue
            seen.add(k)
            a = acc.setdefault(k, {"name": "", "day": "", "bids": 0, "rates": [], "wins": 0, "win_rates": []})
            if day >= a["day"]:
                a["name"], a["day"] = b["name"], day
            a["bids"] += 1
            rate = bid_rate(b)
            if rate is not None:
                a["rates"].append(rate)
            if k == won_key:
                a["wins"] += 1
                if rate is not None:
                    a["win_rates"].append(rate)
    rows = [
        {
            "name": a["name"],
            "bids": a["bids"],
            "wins": a["wins"],
            "rate_n": len(a["rates"]),
            "median_rate": statistics.median(a["rates"]) if len(a["rates"]) >= MIN_SAMPLE else None,
            "median_win_rate": statistics.median(a["win_rates"]) if a["win_rates"] else None,
        }
        for a in acc.values()
        if a["bids"] >= min_bids
    ]
    rows.sort(key=lambda r: (-r["bids"], -r["wins"], r["name"]))
    return rows


def _project_key(n: dict[str, Any]) -> tuple[str, str]:
    return (n.get("org") or "").strip(), re.sub(r"\s+|\(?재공고\)?", "", n.get("title") or "")


def weak_competition(notices: list[dict[str, Any]], today: date, days: int = WEAK_DAYS) -> list[dict[str, Any]]:
    """유찰 or 단독 응찰 within the last `days`, newest first, one row per 사업 (재공고 rounds merged)."""
    from .normalize import prespec_excluded

    rules = load_keywords()
    since = (today - timedelta(days=days)).isoformat()
    rows = [
        n
        for n in notices
        if since <= (n.get("open_date") or "") <= today.isoformat()
        and competitive(n)
        and (n.get("status") == "유찰" or bid_count(n) == 1)
        and not prespec_excluded(n, rules)
    ]
    rows.sort(key=lambda n: (n.get("open_date") or "", n.get("budget_eok") or 0), reverse=True)
    seen: set[tuple[str, str]] = set()
    unique = []
    for n in rows:
        key = _project_key(n)
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique


class ContextIndex:
    """Past opened notices by 기관 and by (사업 성격, 예산대) for the 사업 상세 경쟁 맥락."""

    def __init__(self, notices: list[dict[str, Any]]):
        self.by_org: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_kind: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for n in notices:
            if not competitive(n) or not (bid_count(n) or n.get("status") == "유찰"):
                continue
            if n.get("org"):
                self.by_org[n["org"]].append(n)
            band = budget_band(n.get("budget_eok"))
            if n.get("nature") and band:
                self.by_kind[(n["nature"], band)].append(n)

    def context(self, n: dict[str, Any]) -> dict[str, Any] | None:
        me = (n.get("bid_no"), n.get("bid_ord"))
        same_org = [r for r in self.by_org.get(n.get("org") or "", []) if (r.get("bid_no"), r.get("bid_ord")) != me]
        if len(same_org) >= CONTEXT_MIN_ORG:
            basis, pool = "같은 기관", same_org
        else:
            band = budget_band(n.get("budget_eok"))
            kind = (n.get("nature") or "", band or "")
            pool = [r for r in self.by_kind.get(kind, []) if (r.get("bid_no"), r.get("bid_ord")) != me]
            if len(pool) < MIN_SAMPLE:
                return None
            basis = f"같은 사업 성격·예산대 ({kind[0]}, {kind[1]})"
        counts = [c for c in (bid_count(r) for r in pool) if c]
        rates = [x for x in (winner_rate(r) for r in pool) if x is not None]
        firms: Counter = Counter()
        names: dict[str, str] = {}
        for r in pool:
            for k, b in {_firm_key(b): b for b in r.get("bidders") or [] if isinstance(b, dict) and b.get("name")}.items():
                firms[k] += 1
                names.setdefault(k, b["name"])
        return {
            "basis": basis,
            "n": len(pool),
            "median_bids": statistics.median(counts) if counts else None,
            "single_pct": 100.0 * sum(1 for c in counts if c == 1) / len(counts) if counts else None,
            "failed": sum(1 for r in pool if r.get("status") == "유찰"),
            "rates": quartiles(rates) if len(rates) >= MIN_SAMPLE else None,
            "rate_n": len(rates),
            "regulars": [(names[k], c) for k, c in firms.most_common(3) if c >= 2],
        }


def _pct(v: float | None, places: int = 1) -> str:
    return f"{v:.{places}f}%" if v is not None else ""


def _q_cells(q: tuple[float, float, float] | None) -> str:
    if not q:
        return '<td class="num meta" colspan="3">표본 부족</td>'
    return "".join(f'<td class="num">{_pct(v, 2)}</td>' for v in q)


def context_html(ctx: dict[str, Any] | None) -> str:
    """사업 상세용 '비슷한 과거 사업의 경쟁' block; '' when there is no usable sample."""
    if not ctx:
        return ""
    rows = [
        f"<tr><th>비교 기준</th><td>{html.escape(ctx['basis'])} · 개찰된 {ctx['n']}건</td></tr>",
    ]
    if ctx["median_bids"] is not None:
        rows.append(
            f"<tr><th>투찰 업체 수</th><td>보통 {ctx['median_bids']:g}곳"
            f' <span class="meta">단독 응찰 {_pct(ctx["single_pct"], 0)} · 유찰 {ctx["failed"]}건</span></td></tr>'
        )
    if ctx["rates"]:
        lo, mid, hi = ctx["rates"]
        rows.append(
            f"<tr><th>낙찰 투찰률</th><td>{_pct(lo, 2)} ~ {_pct(hi, 2)}"
            f' <span class="meta">중앙값 {_pct(mid, 2)} · {ctx["rate_n"]}건, 예정가격 대비</span></td></tr>'
        )
    if ctx["regulars"]:
        names = ", ".join(f"{html.escape(nm)} {c}회" for nm, c in ctx["regulars"])
        rows.append(f"<tr><th>자주 투찰한 업체</th><td>{names}</td></tr>")
    return (
        "<h2>비슷한 과거 사업의 경쟁</h2>"
        f'<div class="tbl"><table class="kv"><tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="note">나라장터 개찰결과 기준. 낙찰 투찰률은 낙찰자의 예정가격 대비 투찰률 사분위(25%~75%)입니다.</p>'
    )


def _weak_result(n: dict[str, Any], today: date) -> str:
    if n.get("status") == "유찰":
        return "유찰"
    who = n.get("winner") or n.get("first_rank")
    status = infer_status(n, today)
    tail = f' <span class="meta">{html.escape(status)} · {html.escape(who)}</span>' if who else ""
    return "단독 응찰" + tail


def _band_order(label: str) -> int:
    return next((i for i, (_, _, b) in enumerate(BUDGET_BANDS) if b == label), len(BUDGET_BANDS))


def _rate_table(title: str, rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(r['label'])}</td><td class=\"num\">{r['n']}</td>{_q_cells(r['q'])}</tr>"
        for r in rows
    )
    return (
        f"<h3>{html.escape(title)}</h3>"
        '<div class="tbl"><table class="notices"><thead><tr><th>구분</th><th class="num">낙찰 건수</th>'
        '<th class="num">하위 25%</th><th class="num">중앙값</th><th class="num">상위 25%</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _competition_table(title: str, rows: list[dict[str, Any]]) -> str:
    def cells(r: dict[str, Any]) -> str:
        if r["median"] is None:
            return '<td class="num meta" colspan="3">표본 부족</td>'
        return (
            f'<td class="num">{r["median"]:g}</td><td class="num">{r["p75"]:g}</td>'
            f'<td class="num">{_pct(r["single_pct"], 0)}</td>'
        )

    body = "".join(
        f"<tr><td>{html.escape(r['label'])}</td><td class=\"num\">{r['n']}</td>{cells(r)}"
        f"<td class=\"num\">{r['failed']}</td></tr>"
        for r in rows
    )
    return (
        f"<h3>{html.escape(title)}</h3>"
        '<div class="tbl"><table class="notices"><thead><tr><th>구분</th><th class="num">개찰 건수</th>'
        '<th class="num">투찰 수 중앙값</th><th class="num">상위 25%</th><th class="num">단독 응찰</th>'
        '<th class="num">유찰</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def build_pricing(notices: list[dict[str, Any]], run_status: dict[str, Any], today: date) -> str:
    by_nature: Callable[[dict[str, Any]], str | None] = lambda n: n.get("nature")
    by_band: Callable[[dict[str, Any]], str | None] = lambda n: budget_band(n.get("budget_eok"))
    by_method: Callable[[dict[str, Any]], str | None] = lambda n: n.get("contract_method")

    def ordered(rows: list[dict[str, Any]], banded: bool = False) -> list[dict[str, Any]]:
        if banded:
            return sorted(rows, key=lambda r: _band_order(r["label"]))
        return sorted(rows, key=lambda r: (-r["n"], r["label"]))

    rates = [x for x in (winner_rate(n) for n in notices) if x is not None]
    counts = [c for c in (bid_count(n) for n in notices if competitive(n)) if c]
    overall = quartiles(rates)
    weak = weak_competition(notices, today)
    firms = firm_habits(notices)

    stats = (
        '<div class="stats">'
        + stat(f"{len(rates):,}건", "투찰률 확인된 낙찰")
        + stat(_pct(overall[1], 2) if overall else "-", "낙찰 투찰률 중앙값")
        + stat(f"{statistics.median(counts):g}곳" if counts else "-", "공고당 투찰 업체 중앙값")
        + stat(_pct(100.0 * sum(1 for c in counts if c == 1) / len(counts), 0) if counts else "-", "단독 응찰 비율")
        + "</div>"
    )

    firm_rows = "".join(
        "<tr>"
        f"<td>{html.escape(r['name'])}</td>"
        f'<td class="num">{r["bids"]}</td>'
        f'<td class="num">{r["wins"]}</td>'
        f'<td class="num">{_pct(100.0 * r["wins"] / r["bids"], 0)}</td>'
        f'<td class="num">{_pct(r["median_rate"], 2) or SAMPLE_SHORT}</td>'
        f'<td class="num">{_pct(r["median_win_rate"], 2)}</td>'
        "</tr>"
        for r in firms[:LIMIT]
    )
    weak_rows = "".join(
        "<tr>"
        f"<td>{html.escape(n.get('open_date') or '')}</td>"
        f"<td>{html.escape(n.get('org') or '')}</td>"
        f"<td>{title_link(n)}</td>"
        f'<td class="num">{_fmt_budget(n.get("budget_eok"))}</td>'
        f"<td>{_weak_result(n, today)}</td>"
        "</tr>"
        for n in weak[:LIMIT]
    )
    weak_html = (
        '<div class="tbl"><table class="notices"><thead><tr><th>개찰일</th><th>수요기관</th><th>사업명</th>'
        '<th class="num">예산(억)</th><th>결과</th></tr></thead>'
        f"<tbody>{weak_rows}</tbody></table></div>"
        if weak_rows
        else '<p class="empty">최근 1년간 유찰·단독 응찰 사업이 없습니다.</p>'
    )

    body = (
        '<div class="eyebrow">Pricing &amp; Competition</div><h1>투찰·경쟁 분석</h1>'
        '<p class="lede">AI 사업 개찰결과로 본 낙찰 투찰률, 업체별 투찰 습관, 사업 유형별 경쟁 강도입니다. '
        "입찰가와 참여 여부를 정할 때 참고하세요.</p>"
        f'<div class="stamp">{html.escape(stamp_text(run_status))}</div>'
        + stats
        + "<h2>낙찰 투찰률 분포</h2>"
        '<p class="meta">낙찰자의 예정가격 대비 투찰률입니다. 협상계약의 가격평가 점수 등 50~110% 밖의 값은 뺐고, '
        f"낙찰이 {MIN_SAMPLE}건 미만인 구분은 수치 대신 '표본 부족'으로 둡니다.</p>"
        + _rate_table("사업 성격별", ordered(rate_rows(notices, by_nature)))
        + _rate_table("예산대별", ordered(rate_rows(notices, by_band), banded=True))
        + _rate_table("계약 방식별", ordered(rate_rows(notices, by_method)))
        + "<h2>경쟁 강도</h2>"
        '<p class="meta">개찰된 공고의 투찰 업체 수입니다. 수백 곳이 몰리는 공고가 있어 평균 대신 중앙값과 상위 25%를 씁니다. '
        "단독 응찰은 투찰 업체가 1곳인 비율이고, 처음부터 한 업체와 계약하는 수의계약은 뺐습니다.</p>"
        + _competition_table("사업 성격별", ordered(competition_rows(notices, by_nature)))
        + _competition_table("예산대별", ordered(competition_rows(notices, by_band), banded=True))
        + f"<h2>업체별 투찰 습관 (투찰 {FIRM_MIN_BIDS}건 이상)</h2>"
        '<div class="tbl"><table class="notices"><thead><tr><th>업체</th><th class="num">투찰</th>'
        '<th class="num">낙찰</th><th class="num">낙찰 비율</th><th class="num">투찰률 중앙값</th>'
        '<th class="num">낙찰 시 투찰률</th></tr></thead>'
        f"<tbody>{firm_rows}</tbody></table></div>"
        f'<p class="note">사업자번호 기준으로 묶었습니다. 상위 {LIMIT}곳만 표시합니다.</p>'
        + "<h2>경쟁이 약했던 사업 (최근 1년)</h2>"
        '<p class="meta">유찰됐거나 1곳만 투찰한 사업입니다. 수의계약, 장비 구매, 감리·PMO·교육·행사성 공고는 빼고 '
        "재공고 차수는 최신 1건만 둡니다. 같은 기관이 비슷한 사업을 다시 낼 때 진입 기회가 될 수 있습니다.</p>"
        + weak_html
    )
    return page("투찰·경쟁 분석", body)


def load_notices(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "data" / "notices.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("notices") or [])


def render_pricing_page(repo_root: Path, today: date | None = None) -> dict[str, Any]:
    today = today or _today_kst()
    notices = load_notices(repo_root)
    path = repo_root / "pricing.html"
    path.write_text(build_pricing(notices, load_run_status(repo_root), today), encoding="utf-8")
    return {"path": str(path), "notices": len(notices)}

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .normalize import in_band, merge_by_bid, sort_notices
from .classify import load_keywords

KST = timezone(timedelta(hours=9))


def _today_kst() -> date:
    return datetime.now(KST).date()


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def infer_status(notice: dict[str, Any], today: date | None = None) -> str:
    if notice.get("status"):
        return notice["status"]
    if notice.get("winner"):
        return "낙찰"
    today = today or _today_kst()
    open_d = _parse_date(notice.get("open_date"))
    if open_d and open_d > today:
        return "개찰 예정"
    if open_d:
        age = (today - open_d).days
        if age <= 60:
            return "결과 등록 대기"
        return "개찰 확인 필요"
    return "낙찰 미수집"


STATUS_STYLE = {
    "개찰 예정": ("color:var(--muted);white-space:nowrap", "개찰일 전"),
    "결과 등록 대기": (
        "color:var(--muted);white-space:nowrap",
        "개찰 후 60일 이내, 결과 미등록",
    ),
    "유찰": ("color:var(--muted);white-space:nowrap", "유찰"),
    "1순위": (
        "color:var(--accent);white-space:nowrap",
        "개찰 완료, 낙찰 확정 표시 없음(협상·적격심사 진행 추정)",
    ),
    "낙찰": ("color:var(--accent);white-space:nowrap", "낙찰자 확정"),
    "재공고됨": (
        "color:var(--muted);white-space:nowrap",
        "같은 사업의 재공고·다른 차수에 결과가 있음",
    ),
    "개찰 확인 필요": (
        "color:var(--stamp);white-space:nowrap",
        "개찰 후 60일 경과, 개찰 결과 미확인(나라장터 확인 필요)",
    ),
    "낙찰 미수집": (
        "color:var(--muted);white-space:nowrap",
        "이 공고의 개찰일 낙찰정보를 아직 수집하지 않음",
    ),
}


def _fmt_num(v: Any, places: int | None = None) -> str:
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    if places is not None:
        s = f"{n:.{places}f}"
    elif abs(n - round(n)) < 1e-9:
        s = str(int(round(n)))
    else:
        s = f"{n:.2f}".rstrip("0").rstrip(".")
        if "." not in s:
            pass
        elif len(s.split(".")[1]) == 1:
            s = f"{n:.1f}"
    return s


def _fmt_budget(v: Any) -> str:
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    # Match site style: one decimal (8.4, 13.9)
    return f"{round(n, 1):.1f}"


def _fmt_pct(v: Any) -> str:
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    return f"{n:.1f}%".replace(".0%", "%") if abs(n - round(n)) < 1e-9 else f"{n:.1f}%"


def _g2b_href(notice: dict[str, Any]) -> str:
    url = notice.get("g2b_url") or ""
    if not url and notice.get("bid_no"):
        ord_ = str(notice.get("bid_ord") or "000").zfill(3)
        url = (
            "https://www.g2b.go.kr/link/PNPE027_01/single/"
            f"?bidPbancNo={notice['bid_no']}&bidPbancOrd={ord_}"
        )
    return html.escape(url, quote=True)


def _status_cell(status: str) -> str:
    style, title = STATUS_STYLE.get(
        status, ("color:var(--muted);white-space:nowrap", status)
    )
    return (
        f'<td><span style="{style}" title="{html.escape(title)}">'
        f"{html.escape(status)}</span></td>"
    )


def render_notice_row(notice: dict[str, Any], today: date | None = None) -> str:
    status = infer_status(notice, today)
    fields = notice.get("fields") or []
    if isinstance(fields, str):
        field_txt = fields
    else:
        field_txt = ", ".join(fields)
    title = notice.get("title") or ""
    href = _g2b_href(notice)
    bid_count = notice.get("bid_count")
    if bid_count is not None and bid_count != "":
        try:
            bid_count_s = str(int(float(bid_count)))
        except (TypeError, ValueError):
            bid_count_s = html.escape(str(bid_count))
    else:
        bid_count_s = ""
    win_rate = notice.get("win_rate_pct")
    win_s = _fmt_pct(win_rate) if win_rate not in (None, "") else ""

    return (
        "<tr>"
        f"<td>{html.escape(notice.get('notice_date') or '')}</td>"
        f"<td>{html.escape(notice.get('scope') or '')}</td>"
        f"<td>{html.escape(notice.get('org') or '')}</td>"
        f'<td><a href="{href}" target="_blank" rel="noopener">{html.escape(title)}</a></td>'
        f"<td>{html.escape(field_txt)}</td>"
        f'<td class="num">{_fmt_budget(notice.get("budget_eok"))}</td>'
        f"<td>{html.escape(notice.get('open_date') or '')}</td>"
        f"{_status_cell(status)}"
        f'<td class="num">{bid_count_s}</td>'
        f"<td>{html.escape(notice.get('winner') or '')}</td>"
        f'<td class="num">{win_s}</td>'
        "</tr>"
    )


def load_merged_band(
    repo_root: Path,
    notices_path: Path | None = None,
    bootstrap_path: Path | None = None,
) -> list[dict[str, Any]]:
    rules = load_keywords()
    bootstrap_path = bootstrap_path or (repo_root / "data" / "bootstrap.json")
    notices_path = notices_path or (repo_root / "data" / "notices.json")

    existing: list[dict[str, Any]] = []
    if bootstrap_path.exists():
        boot = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        existing = list(boot.get("band_notices") or [])

    incoming: list[dict[str, Any]] = []
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        for n in raw.get("notices") or raw.get("band_notices") or []:
            if in_band(n, rules):
                incoming.append(n)

    merged = sort_notices(merge_by_bid(existing, incoming))
    # Ensure status filled for render
    today = _today_kst()
    for n in merged:
        n["status"] = infer_status(n, today)
    return merged


def _status_meta(notices: list[dict[str, Any]], today: date | None = None) -> str:
    from collections import Counter

    today = today or _today_kst()
    counts = Counter(infer_status(n, today) for n in notices)
    # Stable display order matching the original site note
    order = [
        "낙찰 미수집",
        "낙찰",
        "유찰",
        "개찰 예정",
        "1순위",
        "개찰 확인 필요",
        "재공고됨",
        "결과 등록 대기",
    ]
    parts = [f"{label} {counts[label]}건" for label in order if counts.get(label)]
    # any unexpected statuses
    for label, n in counts.most_common():
        if label not in order:
            parts.append(f"{label} {n}건")
    return '<p class="meta">' + " · ".join(parts) + "</p>"


def _bars_html(counts: list[tuple[str, int]]) -> str:
    if not counts:
        return '<div class="bars wide"></div>'
    top = max(c for _, c in counts) or 1
    parts = ['<div class="bars wide">']
    for label, n in counts:
        pct = 100.0 * n / top
        parts.append(
            f'<div class="bar"><span>{html.escape(label)}</span>'
            f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="n">{n}건</span></div>'
        )
    parts.append("</div>")
    return "".join(parts)


def replace_section_bars(html_text: str, section_h2: str, bars_html: str) -> str:
    marker = f"<h2>{section_h2}</h2>"
    start = html_text.find(marker)
    if start < 0:
        raise RuntimeError(f"Could not find section {section_h2!r}")
    after = start + len(marker)
    next_h2 = html_text.find("<h2>", after)
    if next_h2 < 0:
        raise RuntimeError(f"Could not find end of section {section_h2!r}")
    return html_text[:after] + bars_html + html_text[next_h2:]


def scope_field_counts(
    notices: list[dict[str, Any]],
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    from collections import Counter

    scopes = Counter(n.get("scope") or "미분류" for n in notices)
    # Prefer 생성형 first visually? Original put AI SW first (larger). Keep by count desc.
    scope_list = sorted(scopes.items(), key=lambda x: (-x[1], x[0]))
    fields = Counter()
    for n in notices:
        fs = n.get("fields") or ["AI 일반"]
        if isinstance(fs, str):
            fs = [fs]
        for f in fs:
            fields[f] += 1
    field_list = sorted(fields.items(), key=lambda x: (-x[1], x[0]))
    return scope_list, field_list


def replace_band_results_table(
    html_text: str,
    rows_html: str,
    count: int,
    meta_html: str | None = None,
) -> str:
    pattern = re.compile(
        r"<h2>공고별 결과 \(\d+건\)</h2>"
        r"(?:<p class=\"meta\">.*?</p>)?"
        r'<div class="tbl"><table(?:\s+class="[^"]*")?>'
        r"(<thead>.*?</thead><tbody>)"
        r".*?"
        r"(</tbody></table></div>)",
        re.S,
    )
    meta = meta_html or ""

    def repl(m: re.Match[str]) -> str:
        return (
            f"<h2>공고별 결과 ({count}건)</h2>"
            f"{meta}"
            f'<div class="tbl"><table class="band-results">'
            f"{m.group(1)}{rows_html}{m.group(2)}"
        )

    new, n = pattern.subn(repl, html_text, count=1)
    if n != 1:
        raise RuntimeError("Could not locate 공고별 결과 table in band.html")
    return new


def update_band_notice_stat(html_text: str, count: int, budget_sum_eok: float) -> str:
    """Update first stats card: N건 / 공고 (2023~, 예산 합계 X억)."""
    budget_txt = f"{budget_sum_eok:,.0f}"
    new, n = re.subn(
        r'(<div class="stats"><div class="stat"><div class="v">)\d+건'
        r'(</div><div class="l">공고 \(2023~, 예산 합계 )[\d,]+억(\)</div></div>)',
        rf"\g<1>{count}건\g<2>{budget_txt}억\g<3>",
        html_text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not update band.html notice stats card")
    return new


def update_stamp(html_text: str, day: date | None = None) -> str:
    day = day or _today_kst()
    stamp = day.isoformat()
    new, n = re.subn(
        r'(<div class="stamp">최종 갱신 )\d{4}-\d{2}-\d{2}(</div>)',
        rf"\g<1>{stamp}\g<2>",
        html_text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not update 최종 갱신 stamp")
    return new


def render_band_page(repo_root: Path) -> dict[str, Any]:
    notices = load_merged_band(repo_root)
    today = _today_kst()
    rows = "".join(render_notice_row(n, today) for n in notices)
    path = repo_root / "band.html"
    text = path.read_text(encoding="utf-8")
    text = replace_band_results_table(
        text, rows, len(notices), meta_html=_status_meta(notices, today)
    )
    budget_sum = sum(
        float(n["budget_eok"]) for n in notices if n.get("budget_eok") is not None
    )
    text = update_band_notice_stat(text, len(notices), budget_sum)
    scope_counts, field_counts = scope_field_counts(notices)
    text = replace_section_bars(text, "사업 범위", _bars_html(scope_counts))
    text = replace_section_bars(text, "분야", _bars_html(field_counts))
    # cache-bust CSS when we ship layout fixes
    text = re.sub(
        r"assets/site\.css\?v=\d+",
        "assets/site.css?v=20261029",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
    return {
        "path": str(path),
        "count": len(notices),
        "budget_sum_eok": round(budget_sum, 1),
        "scopes": dict(scope_counts),
        "fields_top": dict(field_counts[:5]),
    }


def render_index_stamp(repo_root: Path, day: date | None = None) -> dict[str, Any]:
    path = repo_root / "index.html"
    text = path.read_text(encoding="utf-8")
    day = day or _today_kst()
    text = update_stamp(text, day)
    text = re.sub(
        r"assets/site\.css\?v=\d+",
        "assets/site.css?v=20261029",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "stamp": day.isoformat()}


# --- Phase B: awards.html -------------------------------------------------

BUILD_NATURE = "시스템 구축·고도화"


def _large_min_eok(rules: dict[str, Any] | None = None) -> float:
    rules = rules or load_keywords()
    return float(rules["filters"]["large_award_min_eok"])


def _is_build_title(title: str | None, rules: dict[str, Any] | None = None) -> bool:
    from .classify import classify_title

    labels = classify_title(title or "", rules or load_keywords())
    return labels.get("nature") == BUILD_NATURE


def _award_amount(row: dict[str, Any]) -> float | None:
    for key in ("award_amount_eok", "win_amount_eok"):
        v = row.get(key)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    bud = row.get("budget_eok")
    rate = row.get("win_rate_pct")
    if bud not in (None, "") and rate not in (None, ""):
        try:
            return round(float(bud) * float(rate) / 100.0, 1)
        except (TypeError, ValueError):
            return None
    if bud not in (None, ""):
        try:
            return float(bud)
        except (TypeError, ValueError):
            return None
    return None


def _fmt_eok_display(v: Any) -> str:
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    # Match awards.html: one decimal, with thousands separators for >= 1000
    s = f"{n:,.1f}"
    return s


def _bid_count_str(v: Any) -> str:
    if v is None or v == "":
        return ""
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return html.escape(str(v))


def load_large_awards(repo_root: Path) -> list[dict[str, Any]]:
    """Bootstrap large awards ∪ notices with budget ≥ 30억 and a winner."""
    rules = load_keywords()
    min_eok = _large_min_eok(rules)
    bootstrap_path = repo_root / "data" / "bootstrap.json"
    notices_path = repo_root / "data" / "notices.json"

    existing: list[dict[str, Any]] = []
    if bootstrap_path.exists():
        boot = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        existing = list(boot.get("large_awards") or [])

    incoming: list[dict[str, Any]] = []
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        for n in raw.get("notices") or []:
            b = n.get("budget_eok")
            if b is None:
                continue
            try:
                if float(b) < min_eok:
                    continue
            except (TypeError, ValueError):
                continue
            if not n.get("winner"):
                continue
            incoming.append(
                {
                    "source": n.get("source") or "g2b_api",
                    "bid_no": n.get("bid_no"),
                    "bid_ord": n.get("bid_ord"),
                    "open_date": n.get("open_date"),
                    "org": n.get("org"),
                    "title": n.get("title"),
                    "budget_eok": n.get("budget_eok"),
                    "award_amount_eok": _award_amount(n),
                    "winner": n.get("winner"),
                    "bid_count": n.get("bid_count"),
                    "second": n.get("second"),
                    "g2b_url": n.get("g2b_url"),
                }
            )

    merged = merge_by_bid(existing, incoming)
    merged = [r for r in merged if r.get("winner")]
    merged.sort(
        key=lambda r: (
            -(float(r["budget_eok"]) if r.get("budget_eok") is not None else -1),
            r.get("open_date") or "",
        )
    )
    return merged


def load_award_pool(repo_root: Path) -> list[dict[str, Any]]:
    """Rows usable for firm / yearly rollups (large awards + notices with winners)."""
    pool: list[dict[str, Any]] = []
    for a in load_large_awards(repo_root):
        row = dict(a)
        row["_amount"] = _award_amount(a)
        pool.append(row)

    # All notices (band merge ∪ notices.json) that have a winner
    rows = list(load_merged_band(repo_root))
    notices_path = repo_root / "data" / "notices.json"
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        rows = merge_by_bid(rows, list(raw.get("notices") or []))

    for n in rows:
        if not n.get("winner"):
            continue
        st = n.get("status")
        if st and st not in ("낙찰", "1순위"):
            continue
        row = {
            "bid_no": n.get("bid_no"),
            "bid_ord": n.get("bid_ord"),
            "open_date": n.get("open_date"),
            "org": n.get("org"),
            "title": n.get("title"),
            "budget_eok": n.get("budget_eok"),
            "award_amount_eok": _award_amount(n),
            "winner": n.get("winner"),
            "bid_count": n.get("bid_count"),
            "win_rate_pct": n.get("win_rate_pct"),
            "g2b_url": n.get("g2b_url"),
            "nature": n.get("nature"),
        }
        row["_amount"] = _award_amount(n)
        pool.append(row)
    return merge_by_bid([], pool)


def aggregate_top_winners(
    pool: list[dict[str, Any]],
    *,
    limit: int = 20,
    build_only: bool = True,
    rules: dict[str, Any] | None = None,
) -> list[tuple[str, int, float]]:
    from collections import defaultdict

    rules = rules or load_keywords()
    wins: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "amount": 0.0})
    for row in pool:
        winner = (row.get("winner") or "").strip()
        if not winner:
            continue
        if build_only and not _is_build_title(row.get("title"), rules):
            continue
        wins[winner]["count"] += 1
        amt = row.get("_amount")
        if amt is None:
            amt = _award_amount(row)
        if amt is not None:
            wins[winner]["amount"] += float(amt)
    ranked = sorted(
        ((name, int(v["count"]), round(v["amount"], 1)) for name, v in wins.items()),
        key=lambda x: (-x[2], -x[1], x[0]),
    )
    return ranked[:limit]


def aggregate_frequent_bidders(
    notices: list[dict[str, Any]],
    *,
    min_bids: int = 3,
    limit: int = 20,
    build_only: bool = True,
    rules: dict[str, Any] | None = None,
) -> list[tuple[str, int, int, float]]:
    """Return (name, bid_notices, wins, win_rate_pct) for firms with ≥min_bids."""
    from collections import defaultdict

    rules = rules or load_keywords()
    bids: dict[str, set[str]] = defaultdict(set)
    wins: dict[str, int] = defaultdict(int)
    for n in notices:
        if build_only and not _is_build_title(n.get("title"), rules):
            continue
        key = f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"
        if not n.get("bid_no"):
            key = f"t:{n.get('title')}|{n.get('open_date')}"
        bidders = n.get("bidders") or []
        names = set()
        for b in bidders:
            name = (b.get("name") or "").strip()
            if name:
                names.add(name)
                bids[name].add(key)
        winner = (n.get("winner") or "").strip()
        if winner:
            # Count win even if bidder list missing (award-only)
            if not bidders:
                bids[winner].add(key)
            wins[winner] += 1

    ranked: list[tuple[str, int, int, float]] = []
    for name, notice_keys in bids.items():
        bid_n = len(notice_keys)
        if bid_n < min_bids:
            continue
        win_n = wins.get(name, 0)
        rate = round(100.0 * win_n / bid_n) if bid_n else 0.0
        ranked.append((name, bid_n, win_n, float(rate)))
    ranked.sort(key=lambda x: (-x[1], -x[2], x[0]))
    return ranked[:limit]


def render_frequent_bidder_row(
    name: str, bids: int, wins: int, rate: float
) -> str:
    rate_s = f"{int(rate)}%" if abs(rate - round(rate)) < 1e-9 else f"{rate:.0f}%"
    return (
        f"<tr><td>{html.escape(name)}</td>"
        f'<td class="num">{bids}</td>'
        f'<td class="num">{wins}</td>'
        f'<td class="num">{rate_s}</td></tr>'
    )


def aggregate_yearly(
    pool: list[dict[str, Any]],
) -> list[tuple[str, int, float]]:
    from collections import defaultdict

    years: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "amount": 0.0})
    for row in pool:
        if not row.get("winner"):
            continue
        od = row.get("open_date") or ""
        if len(od) < 4:
            continue
        y = od[:4]
        years[y]["count"] += 1
        amt = row.get("_amount")
        if amt is None:
            amt = _award_amount(row)
        if amt is not None:
            years[y]["amount"] += float(amt)
    return [
        (y, int(v["count"]), round(v["amount"], 1))
        for y, v in sorted(years.items(), key=lambda x: x[0])
    ]


def load_needs_confirm(
    repo_root: Path, *, limit: int = 30
) -> tuple[list[dict[str, Any]], int]:
    """개찰 확인 필요: bootstrap seed ∪ live inference; top-N by budget."""
    today = _today_kst()
    bootstrap_path = repo_root / "data" / "bootstrap.json"
    seed: list[dict[str, Any]] = []
    seed_total = 0
    if bootstrap_path.exists():
        boot = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        seed = list(boot.get("needs_confirm") or [])
        seed_total = int(boot.get("needs_confirm_total") or len(seed))

    rows: list[dict[str, Any]] = []
    notices_path = repo_root / "data" / "notices.json"
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        rows = list(raw.get("notices") or [])
    band = load_merged_band(repo_root)
    merged = merge_by_bid(band, rows)
    live: list[dict[str, Any]] = []
    for n in merged:
        st = infer_status(n, today)
        if st != "개찰 확인 필요":
            continue
        row = dict(n)
        row["status"] = "개찰 확인 필요"
        live.append(row)

    # Seed preserves historical top rows until award API covers full history
    combined = merge_by_bid(seed, live)
    combined.sort(
        key=lambda r: (
            -(float(r["budget_eok"]) if r.get("budget_eok") is not None else -1),
            r.get("open_date") or "",
        )
    )
    total = max(seed_total, len(live), len(combined))
    return combined[:limit], total


def render_large_award_row(row: dict[str, Any]) -> str:
    href = _g2b_href(row)
    title = row.get("title") or ""
    return (
        "<tr>"
        f"<td>{html.escape(row.get('open_date') or '')}</td>"
        f"<td>{html.escape(row.get('org') or '')}</td>"
        f'<td><a href="{href}" target="_blank" rel="noopener">{html.escape(title)}</a></td>'
        f'<td class="num">{_fmt_eok_display(row.get("budget_eok"))}</td>'
        f'<td class="num">{_fmt_eok_display(_award_amount(row))}</td>'
        f"<td>{html.escape(row.get('winner') or '')}</td>"
        f'<td class="num">{_bid_count_str(row.get("bid_count"))}</td>'
        f"<td>{html.escape(row.get('second') or '')}</td>"
        "</tr>"
    )


def render_top_winner_row(name: str, count: int, amount: float) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(name)}</td>"
        f'<td class="num">{count}</td>'
        f'<td class="num">{_fmt_eok_display(amount)}</td>'
        "</tr>"
    )


def render_yearly_row(year: str, count: int, amount: float) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(year)}</td>"
        f'<td class="num">{count}</td>'
        f'<td class="num">{_fmt_eok_display(amount)}</td>'
        "</tr>"
    )


def render_needs_confirm_row(row: dict[str, Any]) -> str:
    href = _g2b_href(row)
    title = row.get("title") or ""
    return (
        "<tr>"
        f"<td>{html.escape(row.get('open_date') or '')}</td>"
        f"<td>{html.escape(row.get('org') or '')}</td>"
        f'<td><a href="{href}" target="_blank" rel="noopener">{html.escape(title)}</a></td>'
        f'<td class="num">{_fmt_eok_display(row.get("budget_eok"))}</td>'
        f"<td>{html.escape(row.get('contract_method') or '')}</td>"
        "</tr>"
    )


def replace_awards_table(
    html_text: str,
    *,
    h2: str,
    h2_out: str | None = None,
    rows_html: str,
    table_class: str = "notices",
) -> str:
    """Replace tbody of the table under a given <h2>…</h2> (optional meta)."""
    h2_out = h2_out or h2
    pattern = re.compile(
        re.escape(f"<h2>{h2}</h2>")
        + r"(?:<p class=\"meta\">.*?</p>)?"
        + r'<div class="tbl"><table(?:\s+class="[^"]*")?>'
        + r"(<thead>.*?</thead><tbody>)"
        + r".*?"
        + r"(</tbody></table></div>)",
        re.S,
    )

    def repl(m: re.Match[str]) -> str:
        # Preserve meta if present in original match span via separate search
        return (
            f"<h2>{h2_out}</h2>"
            + _extract_meta_after_h2(html_text, h2)
            + f'<div class="tbl"><table class="{table_class}">'
            + f"{m.group(1)}{rows_html}{m.group(2)}"
        )

    new, n = pattern.subn(repl, html_text, count=1)
    if n != 1:
        raise RuntimeError(f"Could not locate awards table under h2 {h2!r}")
    return new


def _extract_meta_after_h2(html_text: str, h2: str) -> str:
    marker = f"<h2>{h2}</h2>"
    i = html_text.find(marker)
    if i < 0:
        return ""
    after = html_text[i + len(marker) : i + len(marker) + 400]
    m = re.match(r'<p class="meta">.*?</p>', after, re.S)
    return m.group(0) if m else ""


def replace_awards_table_by_prefix(
    html_text: str,
    *,
    h2_prefix: str,
    h2_out: str,
    rows_html: str,
    table_class: str = "notices",
) -> str:
    pattern = re.compile(
        rf"<h2>{re.escape(h2_prefix)}[^<]*</h2>"
        r"(?:<p class=\"meta\">.*?</p>)?"
        r'<div class="tbl"><table(?:\s+class="[^"]*")?>'
        r"(<thead>.*?</thead><tbody>)"
        r".*?"
        r"(</tbody></table></div>)",
        re.S,
    )

    def repl(m: re.Match[str]) -> str:
        meta = ""
        full = m.group(0)
        mm = re.search(r'<p class="meta">.*?</p>', full, re.S)
        if mm:
            meta = mm.group(0)
        return (
            f"<h2>{h2_out}</h2>{meta}"
            f'<div class="tbl"><table class="{table_class}">'
            f"{m.group(1)}{rows_html}{m.group(2)}"
        )

    new, n = pattern.subn(repl, html_text, count=1)
    if n != 1:
        raise RuntimeError(f"Could not locate awards table with prefix {h2_prefix!r}")
    return new


def render_awards_page(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "awards.html"
    text = path.read_text(encoding="utf-8")

    large = load_large_awards(repo_root)
    large_rows = "".join(render_large_award_row(r) for r in large)
    text = replace_awards_table(
        text,
        h2="예산 30억 원 이상 사업 낙찰 결과",
        rows_html=large_rows,
        table_class="notices",
    )

    rules = load_keywords()
    pool = load_award_pool(repo_root)
    top = aggregate_top_winners(pool, limit=20, build_only=True, rules=rules)
    if top:
        top_rows = "".join(render_top_winner_row(n, c, a) for n, c, a in top)
        text = replace_awards_table(
            text,
            h2="시스템 구축·고도화 수주 상위 20개사",
            rows_html=top_rows,
            table_class="rank",
        )

    yearly = aggregate_yearly(pool)
    if yearly:
        year_rows = "".join(render_yearly_row(y, c, a) for y, c, a in yearly)
        text = replace_awards_table(
            text,
            h2="연도별 낙찰",
            rows_html=year_rows,
            table_class="rank",
        )

    # 자주 투찰: OpengCompt bidder lists. Prefer 구축·고도화 ≥3; ease threshold
    # while bidder coverage is still growing.
    notices_path = repo_root / "data" / "notices.json"
    bidder_notices: list[dict[str, Any]] = []
    if notices_path.exists():
        raw_n = json.loads(notices_path.read_text(encoding="utf-8"))
        bidder_notices = list(raw_n.get("notices") or [])
    frequent = aggregate_frequent_bidders(
        bidder_notices, min_bids=3, limit=20, build_only=True, rules=rules
    )
    freq_label = "구축·고도화, 3건 이상"
    if len(frequent) < 10:
        frequent = aggregate_frequent_bidders(
            bidder_notices, min_bids=2, limit=20, build_only=True, rules=rules
        )
        freq_label = "구축·고도화, 2건 이상"
    if len(frequent) < 5:
        frequent = aggregate_frequent_bidders(
            bidder_notices, min_bids=3, limit=20, build_only=False, rules=rules
        )
        freq_label = "AI 공고, 3건 이상"
    if frequent:
        freq_rows = "".join(
            render_frequent_bidder_row(n, b, w, r) for n, b, w, r in frequent
        )
        text = replace_awards_table_by_prefix(
            text,
            h2_prefix="자주 투찰하는 업체",
            h2_out=f"자주 투찰하는 업체 ({freq_label})",
            rows_html=freq_rows,
            table_class="rank",
        )

    needs, needs_total = load_needs_confirm(repo_root, limit=30)
    needs_rows = "".join(render_needs_confirm_row(r) for r in needs)
    text = replace_awards_table_by_prefix(
        text,
        h2_prefix="개찰 확인 필요",
        h2_out=f"개찰 확인 필요 ({needs_total}개 사업)",
        rows_html=needs_rows,
        table_class="notices",
    )

    # Stats: recompute from award pool + merged notices when we have winners
    text = update_awards_stats(text, repo_root, pool)

    text = re.sub(
        r"assets/site\.css\?v=\d+[a-z]?",
        "assets/site.css?v=20261029f",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
    return {
        "path": str(path),
        "large_awards": len(large),
        "top_winners": len(top),
        "frequent_bidders": len(frequent),
        "yearly": {y: {"count": c, "amount": a} for y, c, a in yearly},
        "needs_confirm_total": needs_total,
        "needs_confirm_shown": len(needs),
        "pool_size": len(pool),
    }


def update_awards_stats(
    html_text: str,
    repo_root: Path,
    pool: list[dict[str, Any]] | None = None,
) -> str:
    """Refresh the four awards.html summary cards from live data when possible."""
    import statistics

    today = _today_kst()
    band = load_merged_band(repo_root)
    notices_path = repo_root / "data" / "notices.json"
    all_rows = list(band)
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        all_rows = merge_by_bid(all_rows, list(raw.get("notices") or []))

    opened = 0
    with_winner = 0
    failed = 0
    bid_counts: list[int] = []
    for n in all_rows:
        st = infer_status(n, today)
        if st == "개찰 예정":
            continue
        opened += 1
        if n.get("winner") or st == "낙찰":
            with_winner += 1
        if st == "유찰":
            failed += 1
        if _is_build_title(n.get("title")) and n.get("bid_count") not in (None, ""):
            try:
                bid_counts.append(int(float(n["bid_count"])))
            except (TypeError, ValueError):
                pass

    if opened < 10 and with_winner < 10:
        # Not enough live signal — keep editorial stats
        return html_text

    median_bids = int(statistics.median(bid_counts)) if bid_counts else 0

    def fmt_int(n: int) -> str:
        return f"{n:,}"

    new, n = re.subn(
        r'(<div class="stats">\s*<div class="stat"><div class="v">)[\d,]+건'
        r'(</div><div class="l">개찰 결과 확보 공고</div></div>\s*'
        r'<div class="stat"><div class="v">)[\d,]+건'
        r'(</div><div class="l">낙찰자 확인</div></div>\s*'
        r'<div class="stat"><div class="v">)[\d,]+건'
        r'(</div><div class="l">유찰</div></div>\s*'
        r'<div class="stat"><div class="v">)[\d,]+곳'
        r'(</div><div class="l">구축 사업 투찰 업체 수\(중앙값\)</div></div></div>)',
        rf"\g<1>{fmt_int(opened)}건\g<2>{fmt_int(with_winner)}건\g<3>{fmt_int(failed)}건\g<4>{fmt_int(median_bids)}곳\g<5>",
        html_text,
        count=1,
        flags=re.S,
    )
    if n != 1:
        # Non-fatal — layout may have drifted
        return html_text
    return new

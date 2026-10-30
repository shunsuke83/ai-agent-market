"""Aggregate competitor KPIs (투찰·낙찰·금액) and refresh competitors.html."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .assets import stamp_asset_versions
from .normalize import merge_by_bid
from .render import _award_amount, _fmt_budget, infer_status
from .seed import load_seed

CONFIG = Path(__file__).resolve().parents[1] / "config" / "competitors.yaml"

# Strip corporate suffixes / rank markers before alias match.
_CORP_RE = re.compile(
    r"\(주\)|㈜|주식회사|\(유\)|유한회사|\s*\(1순위\)|\s*\(2순위\)"
)
_SPACE_RE = re.compile(r"\s+")


def normalize_firm(name: str | None) -> str:
    if not name:
        return ""
    s = _CORP_RE.sub("", name)
    s = _SPACE_RE.sub("", s)
    return s.casefold()


def load_competitors_config(path: Path | None = None) -> list[dict[str, Any]]:
    raw = yaml.safe_load((path or CONFIG).read_text(encoding="utf-8"))
    return list(raw.get("competitors") or [])


def build_alias_index(
    competitors: list[dict[str, Any]],
) -> dict[str, str]:
    """normalized alias → canonical name."""
    idx: dict[str, str] = {}
    for c in competitors:
        canon = c["name"]
        aliases = list(c.get("aliases") or [])
        aliases.append(canon)
        # Extra: bare name before parenthesis e.g. 타임리(업스테이지) → 타임리
        if "(" in canon:
            aliases.append(canon.split("(", 1)[0].strip())
        for a in aliases:
            n = normalize_firm(a)
            if n:
                idx[n] = canon
    return idx


def match_competitor(winner: str | None, alias_index: dict[str, str]) -> str | None:
    n = normalize_firm(winner)
    if not n:
        return None
    if n in alias_index:
        return alias_index[n]
    # Winner may include extra suffixes; require alias ⊆ winner (not the reverse),
    # so "업스테이지" does not match alias "타임리(업스테이지)".
    for alias, canon in sorted(alias_index.items(), key=lambda x: -len(x[0])):
        if len(alias) < 2:
            continue
        if alias in n:
            if len(alias) <= 2 and alias != n:
                continue
            return canon
    return None


def _row_key(row: dict[str, Any]) -> str:
    if row.get("bid_no"):
        return f"{row.get('bid_no')}-{row.get('bid_ord') or '000'}"
    return f"t:{row.get('title')}|{row.get('open_date') or row.get('notice_date')}"


def load_win_pool(repo_root: Path) -> list[dict[str, Any]]:
    """Seed band / large awards ∪ notices, keeping confirmed awards only (no 1순위)."""
    boot = load_seed(repo_root)
    rows: list[dict[str, Any]] = list(boot.get("band_notices") or [])
    rows += list(boot.get("large_awards") or [])
    notices_path = repo_root / "data" / "notices.json"
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        rows += list(raw.get("notices") or [])
    return [
        n
        for n in merge_by_bid([], rows)
        if n.get("winner") and infer_status(n) == "낙찰"
    ]


def load_seed_overview(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Editorial competitor profile (type, model, procurement) keyed by name."""
    boot = load_seed(repo_root)
    out: dict[str, dict[str, Any]] = {}
    for row in boot.get("competitors_overview") or []:
        name = row.get("name")
        if name:
            out[name] = dict(row)
    return out


def load_all_notices(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "data" / "notices.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return list(raw.get("notices") or [])


def count_live_bids(
    notices: list[dict[str, Any]],
    win_pool: list[dict[str, Any]],
    alias_index: dict[str, str],
    competitor_names: set[str],
) -> dict[str, set[str]]:
    """Notice keys where each competitor appears in OpengCompt bidders or as winner."""
    bids_by: dict[str, set[str]] = {n: set() for n in competitor_names}

    for row in notices:
        key = _row_key(row)
        found: set[str] = set()
        for b in row.get("bidders") or []:
            nm = b.get("name") if isinstance(b, dict) else str(b)
            canon = match_competitor(nm, alias_index)
            if canon and canon in bids_by:
                found.add(canon)
        # Winner always counts as a bid (even before bidders[] enrich)
        w = match_competitor(row.get("winner"), alias_index)
        if w and w in bids_by:
            found.add(w)
        for canon in found:
            bids_by[canon].add(key)

    # Bootstrap win pool may include awards not yet in notices.json
    for row in win_pool:
        canon = match_competitor(row.get("winner"), alias_index)
        if not canon or canon not in bids_by:
            continue
        bids_by[canon].add(_row_key(row))

    return bids_by


def core_bidder_coverage(notices: list[dict[str, Any]]) -> dict[str, float | int]:
    """Share of core AI notices (with open_date) that already have bidders[]."""
    try:
        from .reports import is_core
    except Exception:  # pragma: no cover
        def is_core(n: dict[str, Any]) -> bool:  # type: ignore
            return bool(n.get("nature"))

    core_open = [
        n
        for n in notices
        if n.get("bid_no") and n.get("open_date") and is_core(n)
    ]
    with_b = sum(1 for n in core_open if n.get("bidders"))
    total = len(core_open)
    return {
        "core_open": total,
        "with_bidders": with_b,
        "ratio": (with_b / total) if total else 0.0,
    }


def aggregate_competitor_kpis(
    repo_root: Path,
    competitors: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Per competitor: confirmed wins and reported award amounts from the win pool;
    bids from OpengCompt bidders[]. No seed floor: values drop when sources are
    corrected. Editorial seed counts are returned for reference only.
    """
    competitors = competitors or load_competitors_config()
    alias_index = build_alias_index(competitors)
    seed = load_seed_overview(repo_root)
    pool = load_win_pool(repo_root)
    notices = load_all_notices(repo_root)
    names = {c["name"] for c in competitors}
    live_bid_keys = count_live_bids(notices, pool, alias_index, names)
    coverage = core_bidder_coverage(notices)

    wins_by: dict[str, list[dict[str, Any]]] = {c["name"]: [] for c in competitors}
    seen_keys: dict[str, set[str]] = {c["name"]: set() for c in competitors}

    for row in pool:
        canon = match_competitor(row.get("winner"), alias_index)
        if not canon or canon not in wins_by:
            continue
        key = _row_key(row)
        if key in seen_keys[canon]:
            continue
        seen_keys[canon].add(key)
        wins_by[canon].append(row)

    results: list[dict[str, Any]] = []
    for c in competitors:
        name = c["name"]
        live = wins_by[name]
        live_wins = len(live)
        live_bids = len(live_bid_keys.get(name) or ())
        amounts = [a for a in (_award_amount(r) for r in live) if a is not None]
        live_amount = round(sum(amounts), 1)
        s = seed.get(name) or {}
        seed_wins = int(s.get("wins") or 0)
        seed_bids = int(s.get("bids") or 0)
        wins = live_wins
        amount = live_amount
        bids = max(live_bids, wins)

        live_sorted = sorted(
            live,
            key=lambda r: (
                r.get("open_date") or r.get("notice_date") or "",
                _award_amount(r) or 0.0,
            ),
            reverse=True,
        )
        results.append(
            {
                "name": name,
                "type": c.get("type") or s.get("type") or "",
                "own_model": c.get("own_model") or s.get("own_model") or "",
                "procurement": c.get("procurement") or s.get("procurement") or "",
                "bids": bids,
                "wins": wins,
                "award_amount_eok": amount,
                "amount_known": len(amounts),
                "live_wins": live_wins,
                "live_bids": live_bids,
                "live_amount_eok": live_amount,
                "seed_wins": seed_wins,
                "seed_bids": seed_bids,
                "seed_amount_eok": s.get("award_amount_eok"),
                "coverage_ratio": round(float(coverage["ratio"]), 3),
                "recent": live_sorted[:5],
            }
        )

    results.sort(
        key=lambda r: (-int(r["wins"]), -float(r["award_amount_eok"]), r["name"])
    )
    return results


def _fmt_amount(row: dict[str, Any]) -> str:
    """Sum of reported amounts; 미확인 when wins exist but no amount was reported."""
    if int(row["wins"]) == 0:
        return "-"
    if not row.get("amount_known", 1):
        return "미확인"
    return _fmt_budget(row["award_amount_eok"])


def _anchor_id(name: str) -> str:
    return f"c-{name}"


def _win_rate(bids: int, wins: int) -> int | None:
    if bids <= 0:
        return None
    return int(round(100.0 * wins / bids))


def render_overview_row(row: dict[str, Any]) -> str:
    name = row["name"]
    href = html.escape(f"#{_anchor_id(name)}", quote=True)
    return (
        "<tr>"
        f'<td><a href="{href}">{html.escape(name)}</a></td>'
        f"<td>{html.escape(row.get('type') or '')}</td>"
        f'<td class="num">{int(row["bids"])}</td>'
        f'<td class="num">{int(row["wins"])}</td>'
        f'<td class="num">{_fmt_amount(row)}</td>'
        f'<td class="num">{_fmt_seed(row)}</td>'
        f"<td>{html.escape(row.get('own_model') or '')}</td>"
        f"<td>{html.escape(row.get('procurement') or '')}</td>"
        "</tr>"
    )


def _fmt_seed(row: dict[str, Any]) -> str:
    wins = int(row.get("seed_wins") or 0)
    if not wins:
        return "-"
    amt = row.get("seed_amount_eok")
    return f"{wins}건 · {_fmt_budget(amt)}억" if amt not in (None, "") else f"{wins}건"


OVERVIEW_THEAD = (
    "<thead><tr><th>업체</th><th>유형</th>"
    '<th class="num" title="수집한 개찰 결과의 투찰업체 목록 기준">투찰</th>'
    '<th class="num" title="나라장터 낙찰 확정 건(개찰 1순위 제외)">낙찰</th>'
    '<th class="num" title="낙찰금액이 공개·수집된 건만 합산">낙찰금액(억)</th>'
    '<th class="num" title="2026-10-28 편집 조사값. 소액 구독·라이선스 구매 포함, 수집 범위와 다름">'
    "편집 조사 낙찰</th>"
    "<th>자체 모델</th><th>조달 자격</th></tr></thead>"
)

OVERVIEW_NOTE = (
    '<p class="note">낙찰 건수 순. 투찰·낙찰·낙찰금액은 이 사이트가 수집한 나라장터 개찰·낙찰 결과만 '
    "집계합니다(2023년 이후 AI 사업). 개찰 1순위만 확인된 건은 낙찰에 넣지 않고, 낙찰금액은 금액이 "
    "공개된 건만 더하므로 실제보다 적을 수 있습니다. 투찰업체 목록은 아직 모으는 중입니다. "
    "‘편집 조사 낙찰’은 2026-10-28에 사람이 조사한 값으로 소액 구독·라이선스 구매까지 포함해 "
    "집계 범위가 다르며, 두 값을 합치지 않습니다. 컨소시엄 구성원만 참여한 사업은 집계되지 않습니다.</p>"
)


def replace_overview_table(html_text: str, rows_html: str) -> str:
    pattern = re.compile(
        r"(<h2>한눈에 보기</h2><div class=\"tbl\"><table(?:\s+class=\"[^\"]*\")?>)"
        r"<thead>.*?</thead><tbody>"
        r".*?"
        r"(</tbody></table></div>)(?:<p class=\"note\">.*?</p>)?",
        re.S,
    )

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{OVERVIEW_THEAD}<tbody>{rows_html}{m.group(2)}{OVERVIEW_NOTE}"

    new, n = pattern.subn(repl, html_text, count=1)
    if n != 1:
        raise RuntimeError("Could not locate 한눈에 보기 table in competitors.html")
    return new


def _amount_label(row: dict[str, Any]) -> str:
    amt = _fmt_amount(row)
    return {"-": "-", "미확인": "금액 미확인"}.get(amt, f"{amt}억")


def _fmt_kpi_span(row: dict[str, Any]) -> str:
    return (
        f'<span class="kpi">투찰 {int(row["bids"])} · 낙찰 {int(row["wins"])} · '
        f"{_amount_label(row)}</span>"
    )


def _fmt_perf_p(row: dict[str, Any]) -> str:
    bids, wins = int(row["bids"]), int(row["wins"])
    known = int(row.get("amount_known") or 0)
    rate = _win_rate(bids, wins)
    rate_s = f" · 투찰 대비 낙찰 {rate}%" if rate is not None else ""
    lab = _amount_label(row)
    amt_s = {"-": "", "금액 미확인": " · 낙찰금액 미확인"}.get(lab, f" · 낙찰금액 {lab}")
    if 0 < known < wins:
        amt_s += f"(금액 확인 {known}/{wins}건)"
    seed_s = _fmt_seed(row)
    seed_line = (
        f'<br><span class="meta">편집 조사(2026-10-28, 소액 구독 포함): 낙찰 {seed_s}</span>'
        if seed_s != "-"
        else ""
    )
    return f"<p>수집 확인: 투찰 {bids}건 · 낙찰 {wins}건{rate_s}{amt_s}{seed_line}</p>"


def _recent_li(row: dict[str, Any]) -> str:
    day = row.get("open_date") or row.get("notice_date") or ""
    org = row.get("org") or ""
    title = row.get("title") or ""
    amt = _award_amount(row)
    amt_s = f" ({_fmt_budget(amt)}억)" if amt is not None else ""
    return (
        f"<li>{html.escape(str(day)[:7])} · {html.escape(org)} · "
        f"{html.escape(title)}{html.escape(amt_s)}</li>"
    )


def update_competitor_detail(
    html_text: str,
    row: dict[str, Any],
) -> str:
    """Update kpi span + 나라장터 실적 paragraph (+ optional recent list)."""
    name = row["name"]
    anchor = re.escape(_anchor_id(name))

    # kpi in summary
    kpi_pat = re.compile(
        rf'(<details class="co" id="{anchor}">\s*<summary>.*?)'
        rf'(<span class="kpi">.*?</span>)',
        re.S,
    )
    html_text, _ = kpi_pat.subn(
        lambda m: m.group(1) + _fmt_kpi_span(row),
        html_text,
        count=1,
    )

    # 나라장터 실적 paragraph (first <p> after that h4 inside this details)
    perf_pat = re.compile(
        rf'(<details class="co" id="{anchor}">.*?<h4>나라장터 실적 \(AI 사업 공고\)</h4>)'
        rf"\s*<p>.*?</p>",
        re.S,
    )
    html_text, _ = perf_pat.subn(
        lambda m: m.group(1) + _fmt_perf_p(row),
        html_text,
        count=1,
    )

    # Recent wins list: only replace when we have live rows
    recent = row.get("recent") or []
    if recent:
        lis = "".join(_recent_li(r) for r in recent[:3])
        ul_pat = re.compile(
            rf'(<details class="co" id="{anchor}">.*?<h4>나라장터 실적 \(AI 사업 공고\)</h4>.*?)'
            rf"(<ul class=\"plain\">).*?(</ul>)",
            re.S,
        )
        html_text, _ = ul_pat.subn(
            rf"\g<1>\g<2>{lis}\g<3>",
            html_text,
            count=1,
        )

    return html_text


def render_competitors_page(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "competitors.html"
    text = path.read_text(encoding="utf-8")
    rows = aggregate_competitor_kpis(repo_root)
    overview = "".join(render_overview_row(r) for r in rows)
    text = replace_overview_table(text, overview)
    for r in rows:
        text = update_competitor_detail(text, r)

    text = stamp_asset_versions(text)
    path.write_text(text, encoding="utf-8")

    matched = sum(1 for r in rows if r["live_wins"] > 0)
    return {
        "path": str(path),
        "competitors": len(rows),
        "with_live_wins": matched,
        "top": [
            {
                "name": r["name"],
                "bids": r["bids"],
                "wins": r["wins"],
                "award_amount_eok": r["award_amount_eok"],
            }
            for r in rows[:5]
        ],
    }

"""Aggregate competitor KPIs (투찰·낙찰·금액) and refresh competitors.html."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .normalize import merge_by_bid
from .render import _fmt_budget

CONFIG = Path(__file__).resolve().parents[1] / "config" / "competitors.yaml"
ASSET_VER = "20261029f"

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


def _row_key(row: dict[str, Any]) -> str:
    if row.get("bid_no"):
        return f"{row.get('bid_no')}-{row.get('bid_ord') or '000'}"
    return f"t:{row.get('title')}|{row.get('open_date') or row.get('notice_date')}"


def load_win_pool(repo_root: Path) -> list[dict[str, Any]]:
    """Union of band / large awards / notices that have a winner."""
    pool: list[dict[str, Any]] = []
    boot_path = repo_root / "data" / "bootstrap.json"
    if boot_path.exists():
        boot = json.loads(boot_path.read_text(encoding="utf-8"))
        for n in boot.get("band_notices") or []:
            if n.get("winner"):
                pool.append(n)
        for n in boot.get("large_awards") or []:
            if n.get("winner"):
                pool.append(n)
    notices_path = repo_root / "data" / "notices.json"
    if notices_path.exists():
        raw = json.loads(notices_path.read_text(encoding="utf-8"))
        for n in raw.get("notices") or []:
            if n.get("winner"):
                pool.append(n)
    return merge_by_bid([], pool)


def load_seed_overview(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Seed KPIs from bootstrap (editorial HTML extract) keyed by name."""
    path = repo_root / "data" / "bootstrap.json"
    if not path.exists():
        return {}
    boot = json.loads(path.read_text(encoding="utf-8"))
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


def aggregate_competitor_kpis(
    repo_root: Path,
    competitors: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Per competitor: wins/amount from win pool; bids from OpengCompt bidders[]
    with seed floor while coverage is still growing.
    wins/amount never regress below seed overview values.
    """
    competitors = competitors or load_competitors_config()
    alias_index = build_alias_index(competitors)
    seed = load_seed_overview(repo_root)
    pool = load_win_pool(repo_root)
    notices = load_all_notices(repo_root)
    names = {c["name"] for c in competitors}
    live_bid_keys = count_live_bids(notices, pool, alias_index, names)

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
        live_amount = round(
            sum(_award_amount(r) or 0.0 for r in live),
            1,
        )
        s = seed.get(name) or {}
        seed_wins = int(s.get("wins") or 0)
        seed_bids = int(s.get("bids") or 0)
        seed_amount = float(s.get("award_amount_eok") or 0.0)

        # Live pool is often a subset of editorial history. Only replace KPIs
        # when live coverage is at least as wide as the seed win count.
        if live_wins > seed_wins:
            wins = live_wins
            amount = live_amount
        elif live_wins == seed_wins and live_wins > 0:
            wins = live_wins
            amount = max(seed_amount, live_amount)
        else:
            wins = seed_wins
            amount = seed_amount
        # 투찰: OpengCompt 실측 + 시드 floor (커버리지 부족 시 시드 유지)
        bids = max(seed_bids, live_bids, wins)

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
                "live_wins": live_wins,
                "live_bids": live_bids,
                "live_amount_eok": live_amount,
                "seed_wins": seed_wins,
                "seed_bids": seed_bids,
                "recent": live_sorted[:5],
            }
        )

    results.sort(
        key=lambda r: (-float(r["award_amount_eok"]), -int(r["wins"]), r["name"])
    )
    return results


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
        f'<td class="num">{_fmt_budget(row["award_amount_eok"])}</td>'
        f"<td>{html.escape(row.get('own_model') or '')}</td>"
        f"<td>{html.escape(row.get('procurement') or '')}</td>"
        "</tr>"
    )


def replace_overview_table(html_text: str, rows_html: str) -> str:
    pattern = re.compile(
        r"(<h2>한눈에 보기</h2><div class=\"tbl\"><table(?:\s+class=\"[^\"]*\")?>"
        r"<thead>.*?</thead><tbody>)"
        r".*?"
        r"(</tbody></table></div>)",
        re.S,
    )

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{rows_html}{m.group(2)}"

    new, n = pattern.subn(repl, html_text, count=1)
    if n != 1:
        raise RuntimeError("Could not locate 한눈에 보기 table in competitors.html")
    return new


def _fmt_kpi_span(bids: int, wins: int, amount: float) -> str:
    return (
        f'<span class="kpi">투찰 {bids} · 낙찰 {wins} · '
        f"{_fmt_budget(amount)}억</span>"
    )


def _fmt_perf_p(bids: int, wins: int, amount: float) -> str:
    rate = _win_rate(bids, wins)
    rate_s = f" · 낙찰률 {rate}%" if rate is not None else ""
    return (
        f"<p>투찰 {bids}건 · 낙찰 {wins}건{rate_s} · "
        f"낙찰금액 {_fmt_budget(amount)}억</p>"
    )


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
    bids, wins = int(row["bids"]), int(row["wins"])
    amount = float(row["award_amount_eok"])

    # kpi in summary
    kpi_pat = re.compile(
        rf'(<details class="co" id="{anchor}">\s*<summary>.*?)'
        rf'(<span class="kpi">.*?</span>)',
        re.S,
    )
    html_text, n = kpi_pat.subn(
        rf"\g<1>{_fmt_kpi_span(bids, wins, amount)}",
        html_text,
        count=1,
    )
    if n != 1:
        # Some pages may reorder; try looser kpi inside that details block
        pass

    # 나라장터 실적 paragraph (first <p> after that h4 inside this details)
    perf_pat = re.compile(
        rf'(<details class="co" id="{anchor}">.*?<h4>나라장터 실적 \(AI 사업 공고\)</h4>)'
        rf"\s*<p>.*?</p>",
        re.S,
    )
    html_text, n2 = perf_pat.subn(
        rf"\g<1>{_fmt_perf_p(bids, wins, amount)}",
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

    text = re.sub(
        r"assets/site\.css\?v=\d+[a-z]?",
        f"assets/site.css?v={ASSET_VER}",
        text,
        count=1,
    )
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

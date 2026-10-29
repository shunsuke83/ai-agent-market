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
    # Match site style: one decimal when needed (8.4, 13.9)
    if abs(n - round(n, 1)) < 1e-9:
        return f"{n:.1f}"
    return f"{n:.2f}".rstrip("0").rstrip(".")


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


def replace_band_results_table(
    html_text: str,
    rows_html: str,
    count: int,
    meta_html: str | None = None,
) -> str:
    pattern = re.compile(
        r"<h2>공고별 결과 \(\d+건\)</h2>"
        r"(?:<p class=\"meta\">.*?</p>)?"
        r'(<div class="tbl"><table><thead>.*?</thead><tbody>)'
        r".*?"
        r"(</tbody></table></div>)",
        re.S,
    )
    meta = meta_html or ""

    def repl(m: re.Match[str]) -> str:
        return (
            f"<h2>공고별 결과 ({count}건)</h2>"
            f"{meta}"
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
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "count": len(notices), "budget_sum_eok": round(budget_sum, 1)}


def render_index_stamp(repo_root: Path, day: date | None = None) -> dict[str, Any]:
    path = repo_root / "index.html"
    text = path.read_text(encoding="utf-8")
    day = day or _today_kst()
    path.write_text(update_stamp(text, day), encoding="utf-8")
    return {"path": str(path), "stamp": day.isoformat()}

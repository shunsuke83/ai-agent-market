"""bids/<공고번호>-<차수>.html: one static page per AI notice (public data only)."""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import Any

from .normalize import merge_by_bid
from .render import (
    AMOUNT_UNKNOWN,
    _award_amount,
    _bid_count_str,
    _fmt_budget,
    _fmt_pct,
    _g2b_href,
    _today_kst,
    infer_status,
)
from .seed import load_seed
from .site import DETAIL_DIR, detail_slug, page

BIZ_LABEL = {"servc": "용역", "thng": "물품"}


def load_detail_notices(repo_root: Path) -> list[dict[str, Any]]:
    """notices.json + editorial seed rows, merged by 공고번호 (seed fills blanks only)."""
    seed = load_seed(repo_root)
    existing = [
        dict(r)
        for key in ("band_notices", "large_awards", "needs_confirm")
        for r in seed.get(key) or []
        if r.get("bid_no")
    ]
    path = repo_root / "data" / "notices.json"
    incoming = []
    if path.exists():
        incoming = [n for n in json.loads(path.read_text(encoding="utf-8")).get("notices") or [] if n.get("bid_no")]
    return merge_by_bid(existing, incoming)


def _kv(label: str, value: str) -> str:
    return f"<tr><th>{html.escape(label)}</th><td>{value}</td></tr>" if value else ""


def _eok(v: Any) -> str:
    s = _fmt_budget(v)
    return f"{s}억" if s else ""


def _result_rows(n: dict[str, Any], status: str) -> str:
    if n.get("winner"):
        who = _kv("낙찰자", html.escape(n["winner"]))
    elif n.get("first_rank"):
        who = _kv(
            "개찰 1순위",
            f'{html.escape(n["first_rank"])} <span class="meta">낙찰 확정 전</span>',
        )
    else:
        who = ""
    amount = _award_amount(n)
    amount_s = _eok(amount) if amount is not None else (AMOUNT_UNKNOWN if n.get("winner") else "")
    ratio = n.get("award_to_budget_pct")
    rate = n.get("win_rate_pct")
    ratio_s = _fmt_pct(ratio) if ratio not in (None, "") else ""
    rate_s = f'{_fmt_pct(rate)} <span class="meta">예정가격 대비</span>' if rate not in (None, "") else ""
    return (
        _kv("상태", html.escape(status))
        + who
        + _kv("낙찰금액", amount_s)
        + _kv("예산 대비 낙찰금액", ratio_s)
        + _kv("낙찰률", rate_s)
        + _kv("투찰 업체 수", _bid_count_str(n.get("bid_count")))
        + _kv("2순위", html.escape(n.get("second") or ""))
    )


def _bidder_table(bidders: list[Any]) -> str:
    rows = []
    for b in bidders:
        if not isinstance(b, dict):
            continue
        rate = b.get("rate_pct")
        rows.append(
            "<tr>"
            f'<td class="num">{html.escape(str(b.get("rank") or ""))}</td>'
            f"<td>{html.escape(b.get('name') or '')}</td>"
            f'<td class="num">{_fmt_budget(b.get("amount_eok"))}</td>'
            f'<td class="num">{f"{float(rate):.3f}%" if rate not in (None, "") else ""}</td>'
            "</tr>"
        )
    if not rows:
        return ""
    return (
        "<h2>투찰 업체</h2>"
        '<div class="tbl"><table class="notices"><thead><tr><th class="num">순위</th><th>업체</th>'
        '<th class="num">투찰금액(억)</th><th class="num">투찰률</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        '<p class="note">나라장터 개찰결과 기준. 투찰률은 예정가격 대비입니다.</p>'
    )


def _prespec_table(prespecs: list[dict[str, Any]]) -> str:
    if not prespecs:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(p.get('registered_date') or '')}</td>"
        f"<td>{html.escape((p.get('opinion_close_at') or '')[:10])}</td>"
        f"<td>{html.escape(p.get('title') or '')}"
        f'<div class="meta">{html.escape(p.get("prespec_no") or "")}</div></td>'
        f'<td class="num">{_fmt_budget(p.get("asign_budget_eok"))}</td>'
        "<td>"
        + " ".join(
            f'<a href="{html.escape(u, quote=True)}" rel="noopener">규격서 {i}</a>'
            for i, u in enumerate(p.get("spec_files") or [], 1)
        )
        + "</td></tr>"
        for p in prespecs
    )
    return (
        "<h2>관련 사전규격</h2>"
        '<div class="tbl"><table class="notices"><thead><tr><th>등록일</th><th>의견마감</th>'
        '<th>사전규격명</th><th class="num">배정예산(억)</th><th>규격서</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def _same_org_table(rows: list[dict[str, Any]], today: date) -> str:
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{html.escape(r.get('notice_date') or r.get('open_date') or '')}</td>"
        f'<td><a href="{detail_slug(r)}.html">{html.escape(r.get("title") or "")}</a></td>'
        f'<td class="num">{_fmt_budget(r.get("budget_eok"))}</td>'
        f"<td>{html.escape(infer_status(r, today))}</td>"
        "</tr>"
        for r in rows
    )
    return (
        "<h2>같은 기관의 다른 AI 공고</h2>"
        '<div class="tbl"><table class="notices"><thead><tr><th>공고일</th><th>사업명</th>'
        '<th class="num">예산(억)</th><th>상태</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def render_detail_html(
    n: dict[str, Any],
    *,
    prespecs: list[dict[str, Any]] | None = None,
    same_org: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> str:
    today = today or _today_kst()
    status = infer_status(n, today)
    fields = n.get("fields") or []
    fields_s = fields if isinstance(fields, str) else ", ".join(fields)
    labels = " · ".join(x for x in (n.get("scope"), n.get("nature"), fields_s) if x)
    budget = _eok(n.get("budget_eok"))
    if budget and n.get("budget_kind"):
        budget += f' <span class="meta">{html.escape(n["budget_kind"])} 기준</span>'
    g2b = _g2b_href(n)
    info = (
        _kv("공고번호", html.escape(detail_slug(n) or ""))
        + _kv("수요기관", html.escape(n.get("org") or ""))
        + _kv("구분", html.escape(BIZ_LABEL.get(n.get("biz") or "", "")))
        + _kv("분류", html.escape(labels))
        + _kv("공고일", html.escape(n.get("notice_date") or ""))
        + _kv("입찰 마감", html.escape(n.get("close_at") or n.get("close_date") or ""))
        + _kv("개찰", html.escape(n.get("open_at") or n.get("open_date") or ""))
        + _kv("계약 방식", html.escape(n.get("contract_method") or ""))
        + _kv("공고 종류", html.escape(n.get("ntce_kind") or ""))
        + _kv("기준 예산", budget)
        + _kv("배정예산", _eok(n.get("asign_budget_eok")))
        + _kv("추정가격", _eok(n.get("presmpt_eok")))
        + _kv("기초금액", _eok(n.get("base_amount_eok")))
        + _kv("나라장터 원문", f'<a href="{g2b}" target="_blank" rel="noopener">공고 보기 ↗</a>' if g2b else "")
    )
    body = (
        f'<div class="eyebrow">사업 상세 · {html.escape(detail_slug(n) or "")}</div>'
        f"<h1>{html.escape(n.get('title') or '')}</h1>"
        f'<p class="lede">{html.escape(n.get("org") or "")}</p>'
        "<h2>공고 정보</h2>"
        f'<div class="tbl"><table class="kv"><tbody>{info}</tbody></table></div>'
        "<h2>개찰·낙찰 결과</h2>"
        f'<div class="tbl"><table class="kv"><tbody>{_result_rows(n, status)}</tbody></table></div>'
        + _bidder_table(n.get("bidders") or [])
        + _prespec_table(prespecs or [])
        + _same_org_table(same_org or [], today)
    )
    return page(f"{n.get('title') or '사업 상세'} — 사업 상세", body, prefix="../")


def render_detail_pages(repo_root: Path, today: date | None = None) -> dict[str, Any]:
    from .prespecs import load_prespecs

    today = today or _today_kst()
    notices = load_detail_notices(repo_root)
    by_bid: dict[str, list[dict[str, Any]]] = {}
    for p in load_prespecs(repo_root):
        for b in p.get("bid_nos") or []:
            by_bid.setdefault(b.split("-")[0], []).append(p)
    by_org: dict[str, list[dict[str, Any]]] = {}
    for n in notices:
        if n.get("org"):
            by_org.setdefault(n["org"], []).append(n)
    for rows in by_org.values():
        rows.sort(key=lambda r: r.get("notice_date") or r.get("open_date") or "", reverse=True)

    out_dir = repo_root / DETAIL_DIR
    out_dir.mkdir(exist_ok=True)
    written: set[str] = set()
    for n in notices:
        slug = detail_slug(n)
        if not slug or slug in written:
            continue
        same = [r for r in by_org.get(n.get("org") or "", []) if detail_slug(r) != slug][:10]
        text = render_detail_html(n, prespecs=by_bid.get(n["bid_no"]), same_org=same, today=today)
        path = out_dir / f"{slug}.html"
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
        written.add(slug)
    removed = 0
    for path in out_dir.glob("*.html"):
        if path.stem not in written:
            path.unlink()
            removed += 1
    return {"dir": str(out_dir), "pages": len(written), "removed": removed}

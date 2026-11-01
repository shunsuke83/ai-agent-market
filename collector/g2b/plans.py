"""plans.html: 발주계획(아직 공고 전인 AI 사업)과 계약 만료 예정(재발주 후보), 공동수급 실적.

data/order_plans.json ← 발주계획현황서비스 (15129462), data/contracts.json ← 계약정보서비스 (15129427).
"""

from __future__ import annotations

import calendar
import html
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .classify import _has_any, classify_title, load_keywords
from .normalize import _first, always_won_to_eok, band_excluded, parse_api_dt, parse_api_dt_minutes, prespec_excluded
from .render import _fmt_budget, _kst_date, _today_kst, load_run_status
from .site import detail_href, page, stat

PLANS_REL = Path("data") / "order_plans.json"
CONTRACTS_REL = Path("data") / "contracts.json"

EXPIRY_PAST_DAYS = 30
EXPIRY_AHEAD_DAYS = 180
FIRM_DAYS = 365
LIMIT_FIRMS = 30

_BID_NO_RE = re.compile(r"^(R\d{2}[A-Z]{2}\d{8})\d{3}$")
_DATE_RE = re.compile(r"(20\d{2})\s*[./\-년]\s*(\d{1,2})\s*[./\-월]\s*(\d{1,2})")
_SPAN_RE = re.compile(r"(\d+)\s*(일|개월|월|년)")


def _eok(v: Any) -> float | None:
    """원 → 억; planners type 0 or 1 when the amount is undisclosed."""
    e = always_won_to_eok(v)
    return e if e and e >= 0.01 else None


def _bid_no(raw: str) -> str:
    raw = raw.strip()
    m = _BID_NO_RE.match(raw)
    return m.group(1) if m else raw


def normalize_plan_item(item: dict[str, Any], rules: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rules = rules or load_keywords()
    title = (item.get("bizNm") or "").strip()
    plan_no = item.get("orderPlanUntyNo")
    if not title or not plan_no:
        return None
    labels = classify_title(title, rules)
    if not labels["scope"]:
        return None
    year, month = str(item.get("orderYear") or ""), str(item.get("orderMnth") or "")
    record = {
        "plan_no": str(plan_no),
        "title": title,
        "org": _first(item, "orderInsttNm", "totlmngInsttNm"),
        "top_org": item.get("totlmngInsttNm") or None,
        "org_kind": item.get("jrsdctnDivNm") or None,
        "order_ym": f"{year}-{month.zfill(2)}" if year and month else None,
        "amount_eok": _eok(item.get("sumOrderAmt")),
        "contract_method": item.get("cntrctMthdNm") or None,
        "procurement": item.get("prcrmntMethd") or None,
        "dept": item.get("deptNm") or None,
        "tel": item.get("telNo") or None,
        "posted_date": parse_api_dt(item.get("nticeDt")),
        "bid_nos": [_bid_no(b) for b in str(item.get("bidNtceNoList") or "").split(",") if b.strip()],
        "url": item.get("orderPlanDtlUrl") or None,
        "biz": item.get("_biz"),
        "biz_div": item.get("bsnsDivNm") or None,
        "product": item.get("prdctClsfcNoNm") or None,
        **labels,
    }
    return None if plan_excluded(record, rules) else record


def plan_excluded(plan: dict[str, Any], rules: dict[str, Any] | None = None) -> bool:
    """사전규격과 같은 규칙에, 물품은 품명이 장비면 뺀다."""
    rules = rules or load_keywords()
    if prespec_excluded({**plan, "sw_biz": None}, rules):
        return True
    hardware = rules["filters"].get("prespec_goods_hardware_title") or []
    return plan.get("biz") == "thng" and _has_any(plan.get("product") or "", hardware)


def _split_list(raw: str | None) -> list[list[str]]:
    """'[1^a^b],[2^c^d]' → [['1','a','b'], ['2','c','d']]."""
    out = []
    for chunk in re.findall(r"\[([^\]]*)\]", raw or ""):
        out.append([p.strip() for p in chunk.split("^")])
    return out


def parse_firms(raw: str | None) -> list[dict[str, Any]]:
    firms = []
    for f in _split_list(raw):
        if len(f) < 4 or not f[3]:
            continue
        try:
            share = float(f[6]) if len(f) > 6 and f[6] else None
        except ValueError:
            share = None
        bizno = "".join(ch for ch in (f[9] if len(f) > 9 else "") if ch.isdigit())
        firms.append({"name": f[3], "role": f[1] or None, "share": share, "bizno": bizno or None})
    return firms


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def parse_end(text: str | None, signed: str | None) -> str | None:
    """계약기간 원문 → 종료일. '2027/07/30', '2026.11.01~2027.10.31', '계약 후 180일 이내', '착수일로부터 6개월'."""
    text = (text or "").strip()
    if not text:
        return None
    for y, m, d in reversed(_DATE_RE.findall(text)):
        try:
            return date(int(y), int(m), int(d)).isoformat()
        except ValueError:
            continue
    m = _SPAN_RE.search(text)
    if not m or not signed:
        return None
    try:
        start = date.fromisoformat(signed)
    except ValueError:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit == "일":
        return (start + timedelta(days=n)).isoformat()
    return _add_months(start, n * 12 if unit == "년" else n).isoformat()


def _contract_key(item: dict[str, Any]) -> str | None:
    ref = str(_first(item, "cntrctRefNo", "dcsnCntrctNo", "untyCntrctNo") or "")
    # Trailing 2 digits are the 변경 차수; changes replace the original row.
    return ref[:-2] if re.fullmatch(r"R\d{2}TA\d{10}", ref) else (ref or None)


def normalize_contract_item(item: dict[str, Any], rules: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rules = rules or load_keywords()
    title = (item.get("cntrctNm") or "").strip()
    key = _contract_key(item)
    if not title or not key:
        return None
    labels = classify_title(title, rules)
    if not labels["scope"]:
        return None
    demand = [d[2] for d in _split_list(item.get("dminsttList")) if len(d) > 2 and d[2]]
    signed = parse_api_dt(_first(item, "cntrctCnclsDate", "cntrctDate"))
    period = (item.get("cntrctPrd") or "").strip() or None
    amounts = [a for a in (_eok(item.get("totCntrctAmt")), _eok(item.get("thtmCntrctAmt"))) if a]
    record = {
        "contract_no": key,
        "title": title,
        "org": demand[0] if demand else item.get("cntrctInsttNm"),
        "contract_org": item.get("cntrctInsttNm") or None,
        "signed_date": signed,
        "period_text": period,
        "end_date": parse_api_dt(item.get("ttalScmpltDate")) or parse_end(period, signed),
        "amount_eok": max(amounts) if amounts else None,
        "long_term": item.get("lngtrmCtnuDivNm") or None,
        "method": item.get("cntrctCnclsMthdNm") or None,
        "joint": item.get("cmmnCntrctYn") == "Y",
        "firms": parse_firms(item.get("corpList")),
        "bid_no": item.get("ntceNo") or None,
        "registered_at": parse_api_dt_minutes(item.get("rgstDt")),
        "url": item.get("cntrctDtlInfoUrl") or None,
        **labels,
    }
    return None if band_excluded(record, rules) else record


def merge_contracts(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest 등록일시 wins per 계약 (변경계약 rows supersede the original)."""
    by_key: dict[str, dict[str, Any]] = {}
    for c in existing + incoming:
        prev = by_key.get(c["contract_no"])
        if prev is None or (c.get("registered_at") or "") >= (prev.get("registered_at") or ""):
            by_key[c["contract_no"]] = c
    return sorted(by_key.values(), key=lambda c: c.get("signed_date") or "", reverse=True)


def _load(repo_root: Path, rel: Path, key: str) -> list[dict[str, Any]]:
    path = repo_root / rel
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get(key) or [])


def load_plans(repo_root: Path) -> list[dict[str, Any]]:
    return _load(repo_root, PLANS_REL, "plans")


def load_contracts(repo_root: Path) -> list[dict[str, Any]]:
    return _load(repo_root, CONTRACTS_REL, "contracts")


def upcoming_plans(plans: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """공고가 아직 없고 발주 예정월이 이번 달 이후인 계획."""
    this_month = today.strftime("%Y-%m")
    rows = [p for p in plans if not p.get("bid_nos") and (p.get("order_ym") or "") >= this_month]
    return sorted(rows, key=lambda p: (p.get("order_ym") or "", -(p.get("amount_eok") or 0)))


def expiring_contracts(contracts: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    lo = (today - timedelta(days=EXPIRY_PAST_DAYS)).isoformat()
    hi = (today + timedelta(days=EXPIRY_AHEAD_DAYS)).isoformat()
    rows = [c for c in contracts if c.get("end_date") and lo <= c["end_date"] <= hi]
    return sorted(rows, key=lambda c: c["end_date"])


def firm_contract_rows(contracts: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """최근 1년 계약을 지분율대로 나눈 업체별 수주액. 지분이 없으면 단독(100%)으로 본다."""
    since = (today - timedelta(days=FIRM_DAYS)).isoformat()
    agg: dict[str, dict[str, Any]] = {}
    for c in contracts:
        if (c.get("signed_date") or "") < since:
            continue
        firms = c.get("firms") or []
        for f in firms:
            key = f.get("bizno") or f["name"]
            row = agg.setdefault(key, {"name": f["name"], "contracts": 0, "joint": 0, "lead": 0, "amount": 0.0})
            row["contracts"] += 1
            if len(firms) > 1:
                row["joint"] += 1
            if f.get("role") == "주계약업체":
                row["lead"] += 1
            share = f.get("share") if f.get("share") is not None else (100.0 if len(firms) == 1 else 0.0)
            row["amount"] += (c.get("amount_eok") or 0) * share / 100
    return sorted(agg.values(), key=lambda r: (-r["amount"], -r["contracts"]))


def firms_text(firms: list[dict[str, Any]]) -> str:
    def one(f: dict[str, Any]) -> str:
        share = f" {f['share']:g}%" if f.get("share") is not None and len(firms) > 1 else ""
        return html.escape(f["name"]) + share

    return " · ".join(one(f) for f in firms)


def _stamp(status: dict[str, Any], stage: str, label: str) -> str:
    s = (status.get("stages") or {}).get(stage) or {}
    ok_day = _kst_date(s.get("last_success_at"))
    text = f"{label} 기준 {ok_day.isoformat()}" if ok_day else f"{label} 미수집"
    if s.get("last_outcome") not in (None, "success"):
        text += " · 최근 수집 실패, 기존 데이터 표시 중"
    return text


def _link(url: str | None, label: str = "원문 ↗") -> str:
    if not url:
        return ""
    return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'


def _meta(*parts: Any) -> str:
    text = " · ".join(html.escape(str(p)) for p in parts if p)
    return f'<div class="meta">{text}</div>' if text else ""


def contract_title_cell(c: dict[str, Any], details: dict[str, dict[str, Any]]) -> str:
    n = details.get(c.get("bid_no") or "")
    title = html.escape(c["title"])
    if n:
        title = f'<a href="{detail_href(n)}">{title}</a>'
    return title + _meta(c.get("nature"), c.get("period_text"), c.get("long_term"), c.get("method"))


def build_plans_page(
    plans: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    run_status: dict[str, Any],
    today: date,
    details: dict[str, dict[str, Any]] | None = None,
) -> str:
    details = details or {}
    upcoming = upcoming_plans(plans, today)
    soon = (today.replace(day=1) + timedelta(days=92)).strftime("%Y-%m")
    expiring = expiring_contracts(contracts, today)
    firms = firm_contract_rows(contracts, today)
    since = (today - timedelta(days=FIRM_DAYS)).isoformat()
    recent = [c for c in contracts if (c.get("signed_date") or "") >= since]
    joint = sum(1 for c in recent if len(c.get("firms") or []) > 1)

    stats = (
        '<div class="stats">'
        + stat(f"{len(upcoming):,}건", "공고 전 발주계획")
        + stat(f"{sum(1 for p in upcoming if (p.get('order_ym') or '') < soon):,}건", "3개월 안 발주 예정")
        + stat(f"{round(sum(p.get('amount_eok') or 0 for p in upcoming)):,}억", "발주계획 금액 합계")
        + stat(f"{len(expiring):,}건", f"{EXPIRY_AHEAD_DAYS}일 안 계약 종료")
        + stat(f"{len(recent):,}건", "최근 1년 AI 용역 계약")
        + stat(f"{round(100 * joint / len(recent)) if recent else 0}%", "공동수급 비율")
        + "</div>"
    )

    plan_rows = "".join(
        "<tr>"
        f"<td>{html.escape(p.get('order_ym') or '')}</td>"
        f"<td>{html.escape(p.get('org') or '')}</td>"
        f"<td>{html.escape(p['title'])}"
        + _meta(p.get("scope"), p.get("nature"), p.get("biz_div"), p.get("contract_method"), p.get("procurement"))
        + "</td>"
        f'<td class="num">{_fmt_budget(p.get("amount_eok"))}</td>'
        f"<td>{html.escape(p.get('dept') or '')}{_meta(p.get('tel'))}</td>"
        f"<td>{_link(p.get('url'))}</td>"
        "</tr>"
        for p in upcoming
    )
    plan_html = (
        '<div class="tbl"><table class="notices js-filter"><thead><tr><th>발주 예정</th><th>발주기관</th>'
        '<th>사업명</th><th class="num">금액(억)</th><th>담당 부서</th><th>계획</th></tr></thead>'
        f"<tbody>{plan_rows}</tbody></table></div>"
        if plan_rows
        else '<p class="empty">공고 전인 AI 발주계획이 없습니다.</p>'
    )

    exp_rows = "".join(
        "<tr>"
        f"<td>{html.escape(c['end_date'])}"
        + ('<div class="meta">종료됨</div>' if c["end_date"] < today.isoformat() else "")
        + "</td>"
        f"<td>{html.escape(c.get('org') or '')}</td>"
        f"<td>{contract_title_cell(c, details)}</td>"
        f'<td class="num">{_fmt_budget(c.get("amount_eok"))}</td>'
        f"<td>{firms_text(c.get('firms') or [])}</td>"
        f"<td>{html.escape(c.get('signed_date') or '')}"
        f'<div class="meta">{_link(c.get("url"), "계약 ↗")}</div></td>'
        "</tr>"
        for c in expiring
    )
    exp_html = (
        '<div class="tbl"><table class="notices js-filter"><thead><tr><th>종료(추정)</th><th>수요기관</th>'
        '<th>계약명</th><th class="num">계약금액(억)</th><th>수행업체</th><th>체결일</th></tr></thead>'
        f"<tbody>{exp_rows}</tbody></table></div>"
        if exp_rows
        else '<p class="empty">기간 안에 끝나는 AI 용역 계약이 없습니다.</p>'
    )

    firm_rows = "".join(
        "<tr>"
        f"<td>{html.escape(r['name'])}</td>"
        f'<td class="num">{r["contracts"]}</td>'
        f'<td class="num">{r["lead"]}</td>'
        f'<td class="num">{r["joint"]}</td>'
        f'<td class="num">{_fmt_budget(r["amount"])}</td>'
        "</tr>"
        for r in firms[:LIMIT_FIRMS]
    )
    firm_html = (
        '<div class="tbl"><table class="notices"><thead><tr><th>업체</th><th class="num">계약</th>'
        '<th class="num">주계약</th><th class="num">공동수급</th><th class="num">지분 반영 금액(억)</th>'
        f"</tr></thead><tbody>{firm_rows}</tbody></table></div>"
        if firm_rows
        else '<p class="empty">수집된 계약이 없습니다.</p>'
    )

    body = (
        '<div class="eyebrow">Pipeline</div><h1>발주 예정 · 재발주 후보</h1>'
        '<p class="lede">공고가 나오기 전에 움직일 수 있는 사업입니다. 기관이 올린 발주계획 중 아직 공고되지 않은 AI 사업과, '
        "곧 끝나는 AI 용역 계약(후속·재발주 후보)을 모았습니다.</p>"
        f'<div class="stamp">{html.escape(_stamp(run_status, "plans", "발주계획"))} · '
        f'{html.escape(_stamp(run_status, "contracts", "계약정보"))}</div>'
        + stats
        + "<h2>공고 전 발주계획</h2>"
        '<p class="meta">발주 예정월이 이번 달 이후이고 연결된 입찰공고가 아직 없는 계획입니다. 계획은 기관 사정으로 바뀌거나 '
        "취소될 수 있고, 금액 0·1원처럼 비공개인 경우는 비워 둡니다. 장비 구매와 감리·교육·행사성 사업은 뺍니다.</p>"
        + plan_html
        + "<h2>계약 종료 예정 (재발주 후보)</h2>"
        f'<p class="meta">최근 {EXPIRY_PAST_DAYS}일 안에 끝났거나 {EXPIRY_AHEAD_DAYS}일 안에 끝나는 AI 용역 계약입니다. '
        "종료일은 총완수일이 있으면 그 날짜, 없으면 계약기간 원문(날짜, '계약 후 N일')으로 추정합니다. "
        "운영·유지보수는 해마다 다시 발주되는 경우가 많습니다.</p>"
        + exp_html
        + "<h2>최근 1년 AI 용역 계약 업체</h2>"
        '<p class="meta">계약금액을 공동수급 지분율대로 나눠 더했습니다. 계약명 기준 자동 분류이고, 물품 계약은 포함하지 않습니다.</p>'
        + firm_html
    )
    return page("발주 예정 · 재발주 후보", body, scripts=("table-sort.js", "table-filter.js"))


def contract_block(c: dict[str, Any] | None) -> str:
    """사업 상세 page: 계약 결과 (체결일·기간·금액·공동수급 지분)."""
    if not c:
        return ""
    rows = [
        ("체결일", html.escape(c.get("signed_date") or "")),
        ("계약기간", html.escape(c.get("period_text") or "")
         + (f' <span class="meta">종료 {html.escape(c["end_date"])}</span>' if c.get("end_date") else "")),
        ("계약금액", f"{_fmt_budget(c['amount_eok'])}억" if c.get("amount_eok") else ""),
        ("수행업체", firms_text(c.get("firms") or [])),
        ("원문", _link(c.get("url"), "나라장터 계약 ↗")),
    ]
    body = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows if v)
    return f'<h2>계약</h2><div class="tbl"><table class="kv"><tbody>{body}</tbody></table></div>'


def contracts_by_bid(repo_root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in load_contracts(repo_root):
        if c.get("bid_no") and c["bid_no"] not in out:
            out[c["bid_no"]] = c
    return out


def render_plans_page(repo_root: Path, today: date | None = None) -> dict[str, Any]:
    from .detail import load_detail_notices

    today = today or _today_kst()
    plans = load_plans(repo_root)
    contracts = load_contracts(repo_root)
    details = {n["bid_no"]: n for n in load_detail_notices(repo_root)}
    path = repo_root / "plans.html"
    path.write_text(
        build_plans_page(plans, contracts, load_run_status(repo_root), today, details), encoding="utf-8"
    )
    return {"path": str(path), "plans": len(plans), "contracts": len(contracts)}

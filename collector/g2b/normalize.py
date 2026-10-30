from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .classify import classify_title, load_keywords


def parse_api_dt(value: str | None) -> str | None:
    """Normalize API datetime (YYYYMMDD / YYYYMMDDHHMM / with separators) → YYYY-MM-DD."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        return None
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"


# Budgets/awards stored as 억. Raw 원 sneaking through are typically ≥ 10만.
_WON_HINT = 100_000.0


def won_to_eok(value: Any) -> float | None:
    """Heuristic: large numbers are 원, small ones already 억."""
    if value is None or value == "":
        return None
    try:
        n = float(str(value).replace(",", ""))
    except ValueError:
        return None
    if n >= _WON_HINT:
        return round(n / 100_000_000, 4)
    return round(n, 4)


def always_won_to_eok(value: Any) -> float | None:
    """BidPublicInfo / Scsbid money fields documented as 원."""
    if value is None or value == "":
        return None
    try:
        n = float(str(value).replace(",", ""))
    except ValueError:
        return None
    return round(n / 100_000_000, 4)


def coerce_stored_eok(value: Any) -> float | None:
    """Repair a field that should already be 억 but may still hold 원."""
    if value is None or value == "":
        return None
    try:
        n = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if n >= _WON_HINT:
        return round(n / 100_000_000, 4)
    return round(n, 4)


def sanitize_notice_money_fields(notice: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Fix budget/presmpt/award amounts left in 원. Returns (notice, changed)."""
    changed = False
    out = notice
    for key in ("budget_eok", "presmpt_eok", "award_amount_eok", "win_amount_eok"):
        raw = notice.get(key)
        if raw in (None, ""):
            continue
        fixed = coerce_stored_eok(raw)
        if fixed is None:
            continue
        try:
            cur = float(raw)
        except (TypeError, ValueError):
            continue
        if abs(cur - fixed) > 1e-9:
            if out is notice:
                out = dict(notice)
            out[key] = fixed
            changed = True
    return out, changed


def g2b_notice_url(bid_no: str | None, bid_ord: str | None = "000") -> str | None:
    if not bid_no:
        return None
    ord_ = (bid_ord or "000").zfill(3)
    return (
        "https://www.g2b.go.kr/link/PNPE027_01/single/"
        f"?bidPbancNo={bid_no}&bidPbancOrd={ord_}"
    )


def normalize_bid_item(item: dict[str, Any], rules: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Map raw BidPublicInfoService item → site notice schema. Drops non-AI titles."""
    rules = rules or load_keywords()
    title = (item.get("bidNtceNm") or item.get("bidPbancNm") or "").strip()
    if not title:
        return None
    labels = classify_title(title, rules)
    if not labels["scope"]:
        return None

    bid_no = item.get("bidNtceNo") or item.get("bidPbancNo")
    bid_ord = item.get("bidNtceOrd") or item.get("bidPbancOrd") or "000"
    budget = (
        item.get("asignBdgtAmt")
        or item.get("bdgtAmt")
        or item.get("presmptPrce")
        or item.get("bsisAmount")
    )

    return {
        "source": "g2b_api",
        "bid_no": bid_no,
        "bid_ord": str(bid_ord).zfill(3) if bid_ord is not None else None,
        "notice_date": parse_api_dt(
            item.get("bidNtceDt") or item.get("bidNtceDate") or item.get("rgstDt")
        ),
        "open_date": parse_api_dt(
            item.get("opengDt") or item.get("opengDate") or item.get("bidClseDt")
        ),
        "org": item.get("dminsttNm") or item.get("ntceInsttNm"),
        "title": title,
        "scope": labels["scope"],
        "fields": labels["fields"],
        "nature": labels["nature"],
        # asignBdgtAmt / presmptPrce are 원 (see docs/bid-public-info-api.md)
        "budget_eok": always_won_to_eok(budget),
        "presmpt_eok": always_won_to_eok(item.get("presmptPrce")),
        "contract_method": item.get("cntrctCnclsMthdNm") or item.get("bidMethdNm"),
        "ntce_kind": item.get("ntceKindNm"),
        "biz": item.get("_biz"),
        "g2b_url": item.get("bidNtceDtlUrl")
        or g2b_notice_url(bid_no, str(bid_ord) if bid_ord is not None else None),
    }


def in_band(notice: dict[str, Any], rules: dict[str, Any] | None = None) -> bool:
    rules = rules or load_keywords()
    f = rules["filters"]
    b = notice.get("budget_eok")
    if b is None:
        return False
    return f["band_min_eok"] <= b <= f["band_max_eok"]


def band_excluded(notice: dict[str, Any], rules: dict[str, Any] | None = None) -> bool:
    """감리·PMO 등 비(非)구축 공고 — band.html 집계에서 뺀다."""
    from .classify import classify_nature

    rules = rules or load_keywords()
    f = rules["filters"]
    title = notice.get("title") or ""
    t = title.casefold()
    if any(k.casefold() in t for k in f.get("band_exclude_title") or []):
        return True
    nature = notice.get("nature") or classify_nature(title, rules)
    if nature not in set(f.get("band_exclude_natures") or []):
        return False
    return not any(k.casefold() in t for k in f.get("band_keep_title") or [])


def merge_by_bid(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in existing + incoming:
        key = f"{row.get('bid_no')}-{row.get('bid_ord')}"
        if not row.get("bid_no"):
            key = f"title:{row.get('title')}|{row.get('notice_date')}"
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = row
            continue
        # Prefer API rows; fill blanks from previous
        merged = dict(prev)
        for k, v in row.items():
            if k == "raw_keys":
                continue
            if v not in (None, "", [], {}):
                merged[k] = v
        by_key[key] = merged
    return list(by_key.values())


def sort_notices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(r: dict[str, Any]) -> tuple:
        return (r.get("notice_date") or "", r.get("bid_no") or "", r.get("title") or "")

    return sorted(rows, key=key, reverse=True)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def clean_firm_name(name: str | None) -> str | None:
    if not name:
        return None
    s = str(name).strip()
    for token in (
        " 주식회사",
        "주식회사 ",
        "주식회사",
        "(주) ",
        " (주)",
        "(주)",
        "㈜ ",
        " ㈜",
        "㈜",
        "㈔",
    ):
        s = s.replace(token, "")
    return s.strip() or None


def parse_openg_corp_info(raw: str | None) -> dict[str, Any]:
    """Parse `업체^사업자번호^대표^금액^…` from opengCorpInfo."""
    if not raw:
        return {}
    parts = str(raw).split("^")
    out: dict[str, Any] = {}
    if parts:
        out["winner"] = clean_firm_name(parts[0])
    if len(parts) >= 4 and parts[3]:
        out["award_amount_eok"] = always_won_to_eok(parts[3])
    return out


def normalize_bidder_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map OpengCompt row → {rank, name, amount_eok, rate_pct, bizno}."""
    name = clean_firm_name(item.get("prcbdrNm") or item.get("bidprcrNm"))
    if not name:
        return None
    rank = item.get("opengRank")
    try:
        rank_i = int(float(rank)) if rank not in (None, "") else None
    except (TypeError, ValueError):
        rank_i = None
    rate_raw = item.get("bidprcrt") or item.get("bidPrceEvlVal")
    rate: float | None = None
    if rate_raw not in (None, ""):
        try:
            rate = float(str(rate_raw).replace("%", "").replace(",", ""))
        except ValueError:
            rate = None
    return {
        "rank": rank_i,
        "name": name,
        "amount_eok": always_won_to_eok(item.get("bidprcAmt")),
        "rate_pct": rate,
        "bizno": (item.get("prcbdrBizno") or "").strip() or None,
        "ceo": clean_firm_name(item.get("prcbdrCeoNm")) if item.get("prcbdrCeoNm") else None,
    }


def apply_bidders_to_notice(
    notice: dict[str, Any],
    bidder_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach normalized bidders + second place onto a notice."""
    bidders = [b for b in (normalize_bidder_item(r) for r in bidder_rows) if b]
    bidders.sort(key=lambda b: (b.get("rank") is None, b.get("rank") or 9999))
    merged = dict(notice)
    if bidders:
        merged["bidders"] = bidders
        merged["bid_count"] = max(int(merged.get("bid_count") or 0), len(bidders)) or len(
            bidders
        )
        second = next((b for b in bidders if b.get("rank") == 2), None)
        if second and second.get("name"):
            merged["second"] = second["name"]
        # If no winner yet, rank-1 is the top opener (may be 1순위)
        if not merged.get("winner"):
            top = next((b for b in bidders if b.get("rank") == 1), bidders[0])
            if top.get("name"):
                merged["winner"] = top["name"]
                if not merged.get("status"):
                    merged["status"] = "1순위"
    return merged


def normalize_award_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map ScsbidListSttus* item → award fields keyed by bid_no/ord."""
    bid_no = item.get("bidNtceNo") or item.get("bidPbancNo")
    if not bid_no:
        return None
    bid_ord = item.get("bidNtceOrd") or item.get("bidPbancOrd") or "000"
    winner = clean_firm_name(item.get("bidwinnrNm") or item.get("bidwinnrName"))
    amount = always_won_to_eok(item.get("sucsfbidAmt"))
    rate_raw = item.get("sucsfbidRate")
    rate: float | None = None
    if rate_raw not in (None, ""):
        try:
            rate = float(str(rate_raw).replace("%", "").replace(",", ""))
        except ValueError:
            rate = None
    bid_count = None
    cnum = item.get("prtcptCnum")
    if cnum not in (None, ""):
        try:
            bid_count = int(float(cnum))
        except (TypeError, ValueError):
            bid_count = None

    status = "낙찰" if winner else None
    progrs = item.get("progrsDivCdNm") or ""
    if "유찰" in progrs:
        status = "유찰"

    return {
        "bid_no": bid_no,
        "bid_ord": str(bid_ord).zfill(3) if bid_ord is not None else None,
        "title": item.get("bidNtceNm"),
        "org": item.get("dminsttNm"),
        "winner": winner,
        "bid_count": bid_count,
        "award_amount_eok": amount,
        "win_rate_pct": rate,
        "open_date": parse_api_dt(item.get("rlOpengDt") or item.get("opengDt")),
        "fnl_sucsf_date": parse_api_dt(item.get("fnlSucsfDate")),
        "status": status,
        "source": "scsbid_api",
        "biz": item.get("_biz"),
    }


def apply_awards_to_notices(
    notices: list[dict[str, Any]],
    awards: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Merge normalized award rows into notices by bid_no+ord. Returns (notices, updated_count)."""
    by_key: dict[str, dict[str, Any]] = {}
    for a in awards:
        if not a.get("bid_no"):
            continue
        key = f"{a.get('bid_no')}-{a.get('bid_ord') or '000'}"
        by_key[key] = a

    updated = 0
    out: list[dict[str, Any]] = []
    for n in notices:
        key = f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"
        award = by_key.get(key)
        if not award:
            out.append(n)
            continue
        merged = dict(n)
        changed = False
        # Scsbid fields always win over blanks / prior bad conversions
        for field in (
            "winner",
            "bid_count",
            "award_amount_eok",
            "win_rate_pct",
            "second",
            "status",
        ):
            val = award.get(field)
            if val in (None, "", [], {}):
                continue
            if merged.get(field) != val:
                merged[field] = val
                changed = True
        # Derive win rate if API left it blank (and budget looks like 억, not 원)
        if merged.get("win_rate_pct") in (None, "") and merged.get("award_amount_eok") and merged.get(
            "budget_eok"
        ):
            try:
                bud = float(merged["budget_eok"])
                amt = float(merged["award_amount_eok"])
                if 0 < bud < 100_000 and amt >= 0:
                    merged["win_rate_pct"] = round(100.0 * amt / bud, 1)
                    changed = True
            except (TypeError, ValueError):
                pass
        if merged.get("winner") and merged.get("status") in (
            None,
            "",
            "낙찰 미수집",
            "결과 등록 대기",
            "개찰 확인 필요",
        ):
            merged["status"] = "낙찰"
            changed = True
        if changed:
            updated += 1
        out.append(merged)
    return out, updated

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


def won_to_eok(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(str(value).replace(",", ""))
    except ValueError:
        return None
    # API amounts are usually in 원
    if n >= 10_000_000:  # >= 1천만 원 → treat as 원
        return round(n / 100_000_000, 2)
    return round(n, 2)


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
        "budget_eok": won_to_eok(budget),
        "presmpt_eok": won_to_eok(item.get("presmptPrce")),
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

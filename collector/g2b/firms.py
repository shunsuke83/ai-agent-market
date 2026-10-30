"""사업자번호(bizno) 기준 업체 집계: 투찰·낙찰·맞대결, 나라장터 조달업체 기본정보."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .normalize import parse_api_dt

FIRMS_REL = Path("data") / "firms.json"


def fmt_bizno(bizno: str | None) -> str:
    s = "".join(ch for ch in str(bizno or "") if ch.isdigit())
    return f"{s[:3]}-{s[3:5]}-{s[5:]}" if len(s) == 10 else s


@dataclass
class FirmStats:
    bizno: str
    name: str = ""
    bids: set[str] = field(default_factory=set)
    wins: set[str] = field(default_factory=set)
    firsts: set[str] = field(default_factory=set)
    last_date: str = ""
    faced: Counter = field(default_factory=Counter)
    beat: Counter = field(default_factory=Counter)
    lost: Counter = field(default_factory=Counter)


def _key(n: dict[str, Any]) -> str:
    return f"{n.get('bid_no')}-{n.get('bid_ord') or '000'}"


def winner_bizno(notice: dict[str, Any]) -> str | None:
    """사업자번호 of the confirmed winner, matched by name inside the bidder list."""
    from .competitors import normalize_firm

    winner = normalize_firm(notice.get("winner"))
    if not winner:
        return None
    for b in notice.get("bidders") or []:
        if isinstance(b, dict) and b.get("bizno") and normalize_firm(b.get("name")) == winner:
            return str(b["bizno"])
    return None


def bidder_stats(notices: list[dict[str, Any]]) -> dict[str, FirmStats]:
    """Per bizno: notices bid, confirmed wins, 1순위-only, and head-to-head vs every co-bidder."""
    stats: dict[str, FirmStats] = {}
    for n in notices:
        bidders = [b for b in n.get("bidders") or [] if isinstance(b, dict) and b.get("bizno")]
        if not bidders:
            continue
        key = _key(n)
        day = n.get("open_date") or n.get("notice_date") or ""
        won = winner_bizno(n)
        for b in bidders:
            s = stats.setdefault(str(b["bizno"]), FirmStats(bizno=str(b["bizno"])))
            s.name = s.name or (b.get("name") or "")
            if day >= s.last_date:
                s.name = b.get("name") or s.name
                s.last_date = day
            s.bids.add(key)
            if won == s.bizno:
                s.wins.add(key)
            elif not n.get("winner") and b.get("rank") == 1:
                s.firsts.add(key)
        ranked = [b for b in bidders if isinstance(b.get("rank"), int)]
        for a in ranked:
            sa = stats[str(a["bizno"])]
            for o in ranked:
                if o is a or o["bizno"] == a["bizno"]:
                    continue
                sa.faced[str(o["bizno"])] += 1
                if a["rank"] < o["rank"]:
                    sa.beat[str(o["bizno"])] += 1
                elif a["rank"] > o["rank"]:
                    sa.lost[str(o["bizno"])] += 1
    return stats


def load_firms(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = repo_root / FIRMS_REL
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("firms") or {})


def _int(v: Any) -> int | None:
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def normalize_corp_item(item: dict[str, Any]) -> dict[str, Any]:
    """조달업체 기본정보 (getPrcrmntCorpBasicInfo02) → firm record."""
    return {
        "bizno": "".join(ch for ch in str(item.get("bizno") or "") if ch.isdigit()) or None,
        "corp_name": item.get("corpNm"),
        "ceo": item.get("ceoNm"),
        "region": item.get("rgnNm"),
        "opened": parse_api_dt(item.get("opbizDt")),
        "employees": _int(item.get("emplyeNum")),
        "biz_div": item.get("corpBsnsDivNm"),
        "mnfct_div": item.get("mnfctDivNm"),
        "hq_div": item.get("hdoffceDivNm"),
        "homepage": item.get("hmpgAdrs"),
    }


_PROVINCE_SUFFIX = ("특별자치도", "특별자치시", "특별시", "광역시", "도")
_PROVINCE_SHORT = {"충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전라남도": "전남",
                   "경상북도": "경북", "경상남도": "경남", "전북특별자치도": "전북"}


def short_region(region: str | None) -> str:
    """'서울특별시 영등포구 당산동3가' → '서울 영등포구'."""
    parts = str(region or "").split()
    if not parts:
        return ""
    head = _PROVINCE_SHORT.get(parts[0])
    if head is None:
        head = parts[0]
        for suf in _PROVINCE_SUFFIX:
            if head.endswith(suf) and len(head) > len(suf) + 1:
                head = head[: -len(suf)]
                break
    return " ".join([head, *parts[1:2]])


def firm_profile_text(firm: dict[str, Any] | None) -> str:
    """'서울 서초구 · 종업원 194명 · 개업 1999' from the 조달업체 기본정보; '' when not fetched."""
    if not firm:
        return ""
    parts = []
    if firm.get("region"):
        parts.append(short_region(firm["region"]))
    if firm.get("employees"):
        parts.append(f"종업원 {firm['employees']:,}명")
    if firm.get("opened"):
        parts.append(f"개업 {str(firm['opened'])[:4]}")
    return " · ".join(parts)

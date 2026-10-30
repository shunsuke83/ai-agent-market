from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_eok(text: str) -> float | None:
    t = text.replace(",", "").replace("%", "").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _bid_from_href(href: str | None) -> tuple[str | None, str | None]:
    if not href:
        return None, None
    href = href.replace("&amp;", "&")
    detail = re.search(r"bids/([^/]+)-(\d{3})\.html$", href)
    if detail:
        return detail.group(1), detail.group(2)
    q = parse_qs(urlparse(href).query)
    no = (q.get("bidPbancNo") or q.get("bidNtceNo") or [None])[0]
    ord_ = (q.get("bidPbancOrd") or q.get("bidNtceOrd") or [None])[0]
    return no, ord_


def _g2b_only(href: str | None) -> str | None:
    return href if href and "g2b.go.kr" in href else None


class _TableParser(HTMLParser):
    """Collect tables under matching h2 section substrings."""

    def __init__(self, section_substr: str):
        super().__init__()
        self.want = section_substr
        self.h2 = ""
        self.in_h2 = False
        self.capture = False
        self.in_tbody = False
        self.in_th = False
        self.in_td = False
        self.cell = ""
        self.href: str | None = None
        self.headers: list[str] = []
        self.rows: list[list[dict[str, Any]]] = []
        self._row: list[dict[str, Any]] | None = None
        self.result: tuple[list[str], list[list[dict[str, Any]]]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = dict(attrs)
        if tag == "h2":
            self.in_h2 = True
            self.h2 = ""
        if tag == "table":
            self.capture = self.want in self.h2
            if self.capture:
                self.headers = []
                self.rows = []
        if self.capture and tag == "th":
            self.in_th = True
            self.cell = ""
        if self.capture and tag == "tbody":
            self.in_tbody = True
        if self.capture and tag == "tr" and self.in_tbody:
            self._row = []
        if self.capture and tag == "td" and self.in_tbody:
            self.in_td = True
            self.cell = ""
            self.href = None
        if self.capture and tag == "a" and self.in_td:
            self.href = ad.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self.in_h2 = False
        if tag == "th" and self.in_th:
            self.in_th = False
            self.headers.append(_clean(self.cell))
        if tag == "td" and self.in_td:
            self.in_td = False
            assert self._row is not None
            self._row.append({"text": _clean(self.cell), "href": self.href})
        if tag == "tr" and self.in_tbody and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        if tag == "tbody":
            self.in_tbody = False
        if tag == "table" and self.capture:
            self.result = (self.headers, self.rows)
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.in_h2:
            self.h2 += data
        if self.in_th or self.in_td:
            self.cell += data


def parse_table(html: str, section_substr: str) -> tuple[list[str], list[list[dict[str, Any]]]]:
    p = _TableParser(section_substr)
    p.feed(html)
    if not p.result:
        raise ValueError(f"No table found for section containing {section_substr!r}")
    return p.result


def extract_band_notices(repo_root: Path) -> list[dict[str, Any]]:
    html = (repo_root / "band.html").read_text(encoding="utf-8")
    headers, rows = parse_table(html, "공고별 결과")
    idx = {h: i for i, h in enumerate(headers)}

    out: list[dict[str, Any]] = []
    for r in rows:
        title_cell = r[idx["사업명"]]
        bid_no, bid_ord = _bid_from_href(title_cell.get("href"))
        out.append(
            {
                "source": "band.html",
                "bid_no": bid_no,
                "bid_ord": bid_ord,
                "notice_date": r[idx["공고일"]]["text"] or None,
                "scope": r[idx["범위"]]["text"] or None,
                "org": r[idx["수요기관"]]["text"] or None,
                "title": title_cell["text"] or None,
                "fields": [x.strip() for x in (r[idx["분야"]]["text"] or "").split(",") if x.strip()],
                "budget_eok": _parse_eok(r[idx["예산(억)"]]["text"]),
                "open_date": r[idx["개찰일"]]["text"] or None,
                "status": r[idx["상태"]]["text"] or None,
                "bid_count": _parse_eok(r[idx["투찰 수"]]["text"]),
                "winner": r[idx["낙찰자"]]["text"] or None,
                "win_rate_pct": _parse_eok(r[idx.get("낙찰률", idx.get("낙찰가율"))]["text"]),
                "g2b_url": _g2b_only(title_cell.get("href")),
            }
        )
    return out


def extract_large_awards(repo_root: Path) -> list[dict[str, Any]]:
    html = (repo_root / "awards.html").read_text(encoding="utf-8")
    headers, rows = parse_table(html, "예산 30억 원 이상 사업 낙찰 결과")
    idx = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, Any]] = []
    for r in rows:
        title_cell = r[idx["사업명"]]
        bid_no, bid_ord = _bid_from_href(title_cell.get("href"))
        out.append(
            {
                "source": "awards.html",
                "bid_no": bid_no,
                "bid_ord": bid_ord,
                "open_date": r[idx["개찰일"]]["text"] or None,
                "org": r[idx["수요기관"]]["text"] or None,
                "title": title_cell["text"] or None,
                "budget_eok": _parse_eok(r[idx["예산(억)"]]["text"]),
                "award_amount_eok": _parse_eok(r[idx["낙찰금액(억)"]]["text"]),
                "winner": r[idx["낙찰자"]]["text"] or None,
                "bid_count": _parse_eok(r[idx["투찰 수"]]["text"]),
                "second": r[idx["2순위"]]["text"] or None,
                "g2b_url": _g2b_only(title_cell.get("href")),
            }
        )
    return out


def extract_needs_confirm(repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    """Top budget rows under 개찰 확인 필요 + total from the h2 count."""
    html = (repo_root / "awards.html").read_text(encoding="utf-8")
    m = re.search(r"<h2>개찰 확인 필요 \((\d+)개 사업\)</h2>", html)
    total = int(m.group(1)) if m else 0
    headers, rows = parse_table(html, "개찰 확인 필요")
    idx = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, Any]] = []
    for r in rows:
        title_cell = r[idx["사업명"]]
        bid_no, bid_ord = _bid_from_href(title_cell.get("href"))
        out.append(
            {
                "source": "awards.html",
                "bid_no": bid_no,
                "bid_ord": bid_ord,
                "open_date": r[idx["개찰일"]]["text"] or None,
                "org": r[idx["수요기관"]]["text"] or None,
                "title": title_cell["text"] or None,
                "budget_eok": _parse_eok(r[idx["예산(억)"]]["text"]),
                "contract_method": r[idx["계약방법"]]["text"] or None,
                "g2b_url": _g2b_only(title_cell.get("href")),
                "status": "개찰 확인 필요",
            }
        )
    if not total:
        total = len(out)
    return out, total


def extract_competitors_overview(repo_root: Path) -> list[dict[str, Any]]:
    html = (repo_root / "competitors.html").read_text(encoding="utf-8")
    headers, rows = parse_table(html, "한눈에 보기")
    idx = {h: i for i, h in enumerate(headers)}
    out = []
    for r in rows:
        out.append(
            {
                "name": r[idx["업체"]]["text"],
                "type": r[idx["유형"]]["text"],
                "bids": int(_parse_eok(r[idx["투찰"]]["text"]) or 0),
                "wins": int(_parse_eok(r[idx["낙찰"]]["text"]) or 0),
                "award_amount_eok": _parse_eok(r[idx["낙찰금액(억)"]]["text"]),
                "own_model": r[idx["자체 모델"]]["text"],
                "procurement": r[idx["조달 자격"]]["text"],
            }
        )
    return out


def bootstrap_all(repo_root: Path) -> dict[str, Any]:
    needs, needs_total = extract_needs_confirm(repo_root)
    return {
        "schema_version": 1,
        "band_notices": extract_band_notices(repo_root),
        "large_awards": extract_large_awards(repo_root),
        "needs_confirm": needs,
        "needs_confirm_total": needs_total,
        "competitors_overview": extract_competitors_overview(repo_root),
    }

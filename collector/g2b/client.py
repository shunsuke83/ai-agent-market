from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterator

import requests

# Public Data Portal endpoints (조달청 나라장터, 2024+ gateway paths)
BID_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
SCSBID_BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"

# PPSSrch = 나라장터 검색조건 조회 (공고명 키워드 가능)
BID_OPS = {
    "servc": f"{BID_BASE}/getBidPblancListInfoServcPPSSrch",
    "thng": f"{BID_BASE}/getBidPblancListInfoThngPPSSrch",
    "cnstwk": f"{BID_BASE}/getBidPblancListInfoCnstwkPPSSrch",
    "frgcpt": f"{BID_BASE}/getBidPblancListInfoFrgcptPPSSrch",
}

# 개찰완료 목록 (낙찰정보)
SCSBID_OPS = {
    "servc": f"{SCSBID_BASE}/getScsbidListSttusServc",
    "thng": f"{SCSBID_BASE}/getScsbidListSttusThng",
    "cnstwk": f"{SCSBID_BASE}/getScsbidListSttusCnstwk",
    "frgcpt": f"{SCSBID_BASE}/getScsbidListSttusFrgcpt",
}

# 개찰순위 (투찰 업체)
SCSBID_RANK_OPS = {
    "servc": f"{SCSBID_BASE}/getScsbidListSttusServcBidResult",
    # Some deployments use ...OpenResult; keep configurable fallbacks in fetch helpers.
}


class G2BError(RuntimeError):
    pass


def service_key() -> str:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY") or os.environ.get("SERVICE_KEY") or ""
    if not key:
        raise G2BError(
            "Missing DATA_GO_KR_SERVICE_KEY (공공데이터포털 인증키). "
            "Apply at https://www.data.go.kr for BidPublicInfoService + ScsbidInfoService."
        )
    return key


def _dt_param(d: date | datetime, end: bool = False) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y%m%d%H%M")
    return d.strftime("%Y%m%d") + ("2359" if end else "0000")


def month_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """API typically allows ~1 month per request — split ranges."""
    cur = start
    while cur <= end:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        window_end = min(end, nxt - timedelta(days=1))
        yield cur, window_end
        cur = window_end + timedelta(days=1)


class G2BClient:
    def __init__(self, key: str | None = None, sleep_s: float = 0.15, timeout: float = 60.0):
        self.key = key or service_key()
        self.sleep_s = sleep_s
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        # data.go.kr keys are often already URL-encoded; requests will encode again if we pass
        # via params. Prefer appending serviceKey manually when it contains '%'.
        q = dict(params)
        q.setdefault("type", "json")
        q.setdefault("numOfRows", 100)
        q.setdefault("pageNo", 1)
        time.sleep(self.sleep_s)
        if "%" in self.key:
            # pre-encoded key — build URL carefully
            from urllib.parse import urlencode

            other = urlencode({k: v for k, v in q.items()})
            full = f"{url}?serviceKey={self.key}&{other}"
            resp = self.session.get(full, timeout=self.timeout)
        else:
            q["serviceKey"] = self.key
            resp = self.session.get(url, params=q, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        header = (
            data.get("response", {}).get("header")
            or data.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader")
            or {}
        )
        code = str(header.get("resultCode") or header.get("returnReasonCode") or "")
        msg = header.get("resultMsg") or header.get("returnAuthMsg") or header.get("errMsg")
        if code and code not in ("00", "0", ""):
            raise G2BError(f"API error {code}: {msg}")
        return data

    def _items(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        body = data.get("response", {}).get("body") or {}
        items = body.get("items")
        if items is None:
            return []
        if isinstance(items, dict):
            item = items.get("item", [])
        else:
            item = items
        if item is None:
            return []
        if isinstance(item, dict):
            return [item]
        return list(item)

    def _total(self, data: dict[str, Any]) -> int:
        body = data.get("response", {}).get("body") or {}
        try:
            return int(body.get("totalCount") or 0)
        except (TypeError, ValueError):
            return 0

    def iter_pages(self, url: str, params: dict[str, Any], page_size: int = 100) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            p = dict(params)
            p["pageNo"] = page
            p["numOfRows"] = page_size
            data = self._get(url, p)
            items = self._items(data)
            for it in items:
                yield it
            total = self._total(data)
            if not items or page * page_size >= total:
                break
            page += 1

    def search_bids_by_name(
        self,
        keyword: str,
        start: date,
        end: date,
        biz: str = "servc",
    ) -> list[dict[str, Any]]:
        """Search bid notices whose 공고명 contains keyword (PPSSrch)."""
        url = BID_OPS[biz]
        out: list[dict[str, Any]] = []
        for bgn, edn in month_windows(start, end):
            params = {
                "inqryDiv": "1",
                "inqryBgnDt": _dt_param(bgn),
                "inqryEndDt": _dt_param(edn, end=True),
                "bidNtceNm": keyword,
            }
            out.extend(self.iter_pages(url, params))
        return out

    def search_bids_ai(
        self,
        start: date,
        end: date,
        keywords: list[str] | None = None,
        biz_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Collect AI-related notices by several title keywords, dedupe by bidNtceNo+Ord."""
        keywords = keywords or ["AI", "인공지능", "생성형", "LLM", "RAG", "AX"]
        biz_types = biz_types or ["servc", "thng"]
        seen: dict[str, dict[str, Any]] = {}
        for biz in biz_types:
            for kw in keywords:
                for item in self.search_bids_by_name(kw, start, end, biz=biz):
                    key = f"{item.get('bidNtceNo')}-{item.get('bidNtceOrd')}"
                    item = dict(item)
                    item["_biz"] = biz
                    item["_matched_kw"] = kw
                    seen[key] = item
        return list(seen.values())

    def fetch_award_status(
        self,
        start: date,
        end: date,
        biz: str = "servc",
    ) -> list[dict[str, Any]]:
        url = SCSBID_OPS[biz]
        out: list[dict[str, Any]] = []
        for bgn, edn in month_windows(start, end):
            params = {
                "inqryDiv": "1",
                "inqryBgnDt": _dt_param(bgn),
                "inqryEndDt": _dt_param(edn, end=True),
            }
            out.extend(self.iter_pages(url, params))
        return out

from __future__ import annotations

import os
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterator

import requests

_SERVICE_KEY_RE = re.compile(r"(serviceKey=)([^&\s]+)", re.IGNORECASE)

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

# 나라장터 검색조건 낙찰 목록 (공고명 키워드)
SCSBID_PPS_OPS = {
    "servc": f"{SCSBID_BASE}/getScsbidListSttusServcPPSSrch",
    "thng": f"{SCSBID_BASE}/getScsbidListSttusThngPPSSrch",
}

# 개찰결과 (용역/물품) — opengCorpInfo 등
OPENG_PPS_OPS = {
    "servc": f"{SCSBID_BASE}/getOpengResultListInfoServcPPSSrch",
    "thng": f"{SCSBID_BASE}/getOpengResultListInfoThngPPSSrch",
}

# 개찰완료 투찰업체별 순위 (BidResult 대체 — getBidResult* 는 400)
OPENG_COMPT = f"{SCSBID_BASE}/getOpengResultListInfoOpengCompt"
OPENG_FAILING = f"{SCSBID_BASE}/getOpengResultListInfoFailing"
OPENG_REBID = f"{SCSBID_BASE}/getOpengResultListInfoRebid"


class G2BError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def redact_secrets(text: str | None) -> str:
    """Strip serviceKey query values from log/exception text."""
    if not text:
        return ""
    return _SERVICE_KEY_RE.sub(r"\1***", str(text))


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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


class G2BClient:
    def __init__(
        self,
        key: str | None = None,
        sleep_s: float | None = None,
        timeout: float | None = None,
        max_attempts: int | None = None,
        connect_timeout: float | None = None,
    ):
        self.key = key or service_key()
        self.sleep_s = _env_float("G2B_SLEEP", 0.15) if sleep_s is None else sleep_s
        # Portal (apis.data.go.kr) often stalls from Actions — allow long reads, but fail
        # connects fast so a dead portal doesn't burn minutes per attempt.
        self.timeout = _env_float("G2B_TIMEOUT", 90.0) if timeout is None else timeout
        self.connect_timeout = (
            _env_float("G2B_CONNECT_TIMEOUT", 15.0) if connect_timeout is None else connect_timeout
        )
        self.max_attempts = (
            _env_int("G2B_HTTP_RETRIES", 8) if max_attempts is None else max_attempts
        )
        self.session = requests.Session()

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        # data.go.kr keys are often already URL-encoded; requests will encode again if we pass
        # via params. Prefer appending serviceKey manually when it contains '%'.
        q = dict(params)
        q.setdefault("type", "json")
        q.setdefault("numOfRows", 100)
        q.setdefault("pageNo", 1)
        last_err: Exception | None = None
        rate_limited = False
        timeout = (min(self.connect_timeout, self.timeout), self.timeout)
        attempts = max(1, self.max_attempts)
        for attempt in range(attempts):
            time.sleep(self.sleep_s if attempt == 0 else min(45.0, self.sleep_s * (2**attempt)))
            try:
                if "%" in self.key:
                    # pre-encoded key — build URL carefully
                    from urllib.parse import urlencode

                    other = urlencode({k: v for k, v in q.items()})
                    full = f"{url}?serviceKey={self.key}&{other}"
                    resp = self.session.get(full, timeout=timeout)
                else:
                    q["serviceKey"] = self.key
                    resp = self.session.get(url, params=q, timeout=timeout)
            except requests.exceptions.RequestException as e:
                # ConnectTimeout / ReadTimeout / ConnectionError — retry with backoff.
                last_err = G2BError(f"transport error for {url}: {redact_secrets(str(e))}")
                continue
            if resp.status_code == 429:
                rate_limited = True
                last_err = G2BError(f"429 Too Many Requests ({url})", status_code=429)
                continue
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                # Never keep raw response URL — it embeds serviceKey.
                last_err = G2BError(
                    f"HTTP {resp.status_code} for {url}: {redact_secrets(str(e))}",
                    status_code=resp.status_code,
                )
                if resp.status_code >= 500:
                    continue
                raise last_err from None
            try:
                data = resp.json()
            except ValueError:
                # Overloaded gateway answers 200 with XML/HTML instead of JSON.
                snippet = redact_secrets((resp.text or "")[:200])
                last_err = G2BError(f"non-JSON response for {url}: {snippet}")
                continue
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
        raise G2BError(
            f"HTTP retries exhausted: {redact_secrets(str(last_err))}",
            status_code=429 if rate_limited else getattr(last_err, "status_code", None),
        )

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
        if keywords is None:
            try:
                from .classify import load_keywords

                keywords = list(load_keywords().get("search_keywords") or [])
            except Exception:
                keywords = []
        if not keywords:
            keywords = ["AI", "인공지능", "생성형", "LLM", "RAG", "AX"]
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
        page_size: int = 999,
    ) -> list[dict[str, Any]]:
        """개찰·낙찰 완료 목록 (inqryDiv=1, 등록일시 기준, ~1개월 창)."""
        url = SCSBID_OPS[biz]
        out: list[dict[str, Any]] = []
        for bgn, edn in month_windows(start, end):
            params = {
                "inqryDiv": "1",
                "inqryBgnDt": _dt_param(bgn),
                "inqryEndDt": _dt_param(edn, end=True),
            }
            for item in self.iter_pages(url, params, page_size=page_size):
                row = dict(item)
                row["_biz"] = biz
                out.append(row)
        return out

    def fetch_awards_range(
        self,
        start: date,
        end: date,
        biz_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """용역+물품 낙찰 목록을 기간으로 수집 후 bidNtceNo+Ord 기준 중복 제거."""
        biz_types = biz_types or ["servc", "thng"]
        seen: dict[str, dict[str, Any]] = {}
        for biz in biz_types:
            for item in self.fetch_award_status(start, end, biz=biz):
                key = f"{item.get('bidNtceNo')}-{item.get('bidNtceOrd')}"
                seen[key] = item
        return list(seen.values())

    def fetch_award_by_bid(
        self,
        bid_no: str,
        bid_ord: str | None = None,
        biz_types: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """입찰공고번호로 낙찰 단건 조회 (inqryDiv=4)."""
        biz_types = biz_types or ["servc", "thng"]
        params = {
            "inqryDiv": "4",
            "bidNtceNo": bid_no,
            "inqryBgnDt": "202301010000",
            "inqryEndDt": "209912312359",
            "numOfRows": 10,
            "pageNo": 1,
        }
        if bid_ord:
            params["bidNtceOrd"] = str(bid_ord).zfill(3)
        for biz in biz_types:
            url = SCSBID_OPS[biz]
            try:
                data = self._get(url, params)
            except Exception:
                continue
            for item in self._items(data):
                if bid_ord and str(item.get("bidNtceOrd") or "").zfill(3) != str(bid_ord).zfill(3):
                    continue
                row = dict(item)
                row["_biz"] = biz
                return row
        return None

    def fetch_openg_by_bid(
        self,
        bid_no: str,
        bid_ord: str | None = None,
        biz: str = "servc",
    ) -> dict[str, Any] | None:
        """개찰결과 PPSSrch (opengCorpInfo / progrsDivCdNm)."""
        url = OPENG_PPS_OPS.get(biz) or OPENG_PPS_OPS["servc"]
        params = {
            "inqryDiv": "3",
            "bidNtceNo": bid_no,
            "inqryBgnDt": "202301010000",
            "inqryEndDt": "209912312359",
            "numOfRows": 10,
            "pageNo": 1,
        }
        if bid_ord:
            params["bidNtceOrd"] = str(bid_ord).zfill(3)
        data = self._get(url, params)
        items = self._items(data)
        if not items:
            return None
        if bid_ord:
            want = str(bid_ord).zfill(3)
            for it in items:
                if str(it.get("bidNtceOrd") or "").zfill(3) == want:
                    return it
        return items[0]

    def fetch_bidders_by_bid(
        self,
        bid_no: str,
        bid_ord: str | None = None,
        *,
        include_failing: bool = False,
        include_rebid: bool = False,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """투찰업체별 순위 목록 (개찰완료 OpengCompt).

        getBidResultList* 는 게이트웨이 400 — OpengCompt 가 동일 목적.
        inqryDiv=1 + bidNtceNo 로 단건 공고의 전 순위 행을 반환.
        """
        urls = [OPENG_COMPT]
        if include_failing:
            urls.append(OPENG_FAILING)
        if include_rebid:
            urls.append(OPENG_REBID)
        base = {
            "inqryDiv": "1",
            "bidNtceNo": bid_no,
            "inqryBgnDt": "202301010000",
            "inqryEndDt": "209912312359",
        }
        if bid_ord:
            base["bidNtceOrd"] = str(bid_ord).zfill(3)
        out: list[dict[str, Any]] = []
        want = str(bid_ord).zfill(3) if bid_ord else None
        for url in urls:
            for item in self.iter_pages(url, dict(base), page_size=page_size):
                if want and str(item.get("bidNtceOrd") or "").zfill(3) != want:
                    continue
                row = dict(item)
                row["_source_op"] = url.rsplit("/", 1)[-1]
                out.append(row)
        return out

from datetime import date
from pathlib import Path

import pytest

from g2b.client import (
    BID_AWARD_WINDOW_DAYS,
    G2BClient,
    G2BEmptyWindow,
    ORDER_PLAN_POSTED_WINDOW_DAYS,
    bisect_window,
    day_windows,
    window_has_weekday,
)
from g2b.collect import _range_has_weekday, cmd_collect


def test_day_windows_splits_14_days_into_4_day_chunks():
    windows = list(day_windows(date(2026, 11, 7), date(2026, 11, 20), max_days=4))
    assert windows[0] == (date(2026, 11, 7), date(2026, 11, 10))
    assert all((edn - bgn).days + 1 <= 4 for bgn, edn in windows)
    assert windows[-1][1] == date(2026, 11, 20)
    assert BID_AWARD_WINDOW_DAYS == 4
    assert list(day_windows(date(2026, 11, 7), date(2026, 11, 20))) == windows


def test_day_windows_single_day():
    assert list(day_windows(date(2026, 11, 20), date(2026, 11, 20))) == [
        (date(2026, 11, 20), date(2026, 11, 20))
    ]


def test_bisect_and_weekday_helpers():
    assert bisect_window(date(2026, 11, 10), date(2026, 11, 13)) == [
        (date(2026, 11, 10), date(2026, 11, 11)),
        (date(2026, 11, 12), date(2026, 11, 13)),
    ]
    assert bisect_window(date(2026, 11, 10), date(2026, 11, 10)) == [
        (date(2026, 11, 10), date(2026, 11, 10))
    ]
    assert not window_has_weekday(date(2026, 11, 14), date(2026, 11, 15))
    assert window_has_weekday(date(2026, 11, 13), date(2026, 11, 14))  # Fri–Sat


def test_range_has_weekday():
    # Nov 14–15 2026 = Sat–Sun → no weekday
    assert not _range_has_weekday(date(2026, 11, 14), date(2026, 11, 15))
    assert _range_has_weekday(date(2026, 11, 16), date(2026, 11, 20))  # Mon–Fri


def test_collect_keeps_file_when_weekday_range_returns_empty(tmp_path, monkeypatch):
    import argparse
    import json

    from g2b import collect as collect_mod

    out = tmp_path / "notices.json"
    out.write_text(
        json.dumps({"notices": [{"bid_no": "KEEP", "title": "기존"}], "stats": {"raw": 10}}),
        encoding="utf-8",
    )

    class EmptyClient:
        def search_bids_ai(self, start, end):
            return []

    monkeypatch.setattr("g2b.client.G2BClient", lambda: EmptyClient())
    monkeypatch.setattr(collect_mod, "_today_kst", lambda: date(2026, 11, 20))
    args = argparse.Namespace(
        since=None, until="2026-11-20", days=14, out=str(out), replace=False, all_budgets=True, skip_awards=True
    )
    assert cmd_collect(args) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["notices"][0]["bid_no"] == "KEEP"


def test_collect_keeps_file_on_empty_window_error(tmp_path, monkeypatch):
    import argparse
    import json

    from g2b import collect as collect_mod
    from g2b.client import G2BEmptyWindow

    out = tmp_path / "notices.json"
    out.write_text(
        json.dumps({"notices": [{"bid_no": "KEEP", "title": "기존"}], "stats": {"raw": 10}}),
        encoding="utf-8",
    )

    class BoomClient:
        def search_bids_ai(self, start, end):
            raise G2BEmptyWindow("empty weekday window 2026-11-10→2026-11-13 (bid)")

    monkeypatch.setattr("g2b.client.G2BClient", lambda: BoomClient())
    monkeypatch.setattr(collect_mod, "_today_kst", lambda: date(2026, 11, 20))
    args = argparse.Namespace(
        since=None, until="2026-11-20", days=14, out=str(out), replace=False, all_budgets=True, skip_awards=True
    )
    assert cmd_collect(args) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["notices"][0]["bid_no"] == "KEEP"


def test_collect_plans_fails_when_previous_also_empty(tmp_path, monkeypatch):
    import argparse
    import json

    from g2b.collect import cmd_collect_plans

    out = tmp_path / "order_plans.json"
    out.write_text(json.dumps({"plans": [], "generated_at": "x"}), encoding="utf-8")

    class Empty:
        def fetch_order_plans(self, *a, **k):
            return []

    monkeypatch.setattr("g2b.client.G2BClient", lambda: Empty())
    monkeypatch.setattr("g2b.collect._today_kst", lambda: date(2026, 11, 20))
    args = argparse.Namespace(months_ahead=12, posted_days=400, out=str(out))
    assert cmd_collect_plans(args) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["plans"] == []


def test_collect_plans_keeps_previous_but_fails_stage(tmp_path, monkeypatch):
    """W-03: keep snapshot, return 1 so run_status does not treat it as success."""
    import argparse
    import json

    from g2b.collect import cmd_collect_plans

    out = tmp_path / "order_plans.json"
    out.write_text(
        json.dumps({"plans": [{"plan_no": "P1", "title": "유지"}], "generated_at": "2026-11-18T10:07:25Z"}),
        encoding="utf-8",
    )

    class Empty:
        def fetch_order_plans(self, *a, **k):
            return []

    monkeypatch.setattr("g2b.client.G2BClient", lambda: Empty())
    monkeypatch.setattr("g2b.collect._today_kst", lambda: date(2026, 11, 20))
    args = argparse.Namespace(months_ahead=12, posted_days=400, out=str(out))
    assert cmd_collect_plans(args) == 1
    prev = json.loads(out.read_text(encoding="utf-8"))
    assert prev["plans"][0]["plan_no"] == "P1"
    assert prev["generated_at"] == "2026-11-18T10:07:25Z"


def _client_no_http(monkeypatch) -> G2BClient:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-key")
    return G2BClient(key="test-key", sleep_s=0, max_attempts=1)


def test_search_bids_ai_ok_when_one_keyword_empty(monkeypatch):
    """X-01: rare keyword 0 rows must not fail the whole collect window."""
    client = _client_no_http(monkeypatch)

    def fake_pull(url, bgn, edn, *, extra_params=None, page_size=100):
        kw = (extra_params or {}).get("bidNtceNm")
        if kw == "챗봇":
            return []
        return [{"bidNtceNo": f"N-{kw}", "bidNtceOrd": "00"}]

    monkeypatch.setattr(client, "_pull_window", fake_pull)
    rows = client.search_bids_ai(
        date(2026, 11, 18),
        date(2026, 11, 21),
        keywords=["AI", "챗봇"],
        biz_types=["servc"],
    )
    assert any(r.get("_matched_kw") == "AI" for r in rows)
    assert not any(r.get("_matched_kw") == "챗봇" for r in rows)


def test_search_bids_ai_raises_when_window_total_empty(monkeypatch):
    """X-01: all keyword×biz empty on a weekday window → G2BEmptyWindow after bisect."""
    client = _client_no_http(monkeypatch)
    monkeypatch.setattr(client, "_pull_window", lambda *a, **k: [])
    with pytest.raises(G2BEmptyWindow, match="empty weekday window"):
        client.search_bids_ai(
            date(2026, 11, 18),
            date(2026, 11, 21),
            keywords=["AI", "챗봇"],
            biz_types=["servc", "thng"],
        )


def test_award_continues_after_empty_weekday_chunk(monkeypatch):
    """X-01: one empty award weekday chunk must not drop later windows."""
    client = _client_no_http(monkeypatch)
    calls: list[tuple[date, date]] = []

    def fake_pull(url, bgn, edn, *, extra_params=None, page_size=100):
        calls.append((bgn, edn))
        # First 4-day window (Mon–Thu) and its bisect halves stay empty; later window has rows.
        if edn < date(2026, 11, 20):
            return []
        return [{"bidNtceNo": "A1", "bidNtceOrd": "00"}]

    monkeypatch.setattr(client, "_pull_window", fake_pull)
    rows = client.fetch_award_status(date(2026, 11, 16), date(2026, 11, 23), biz="servc")
    assert any(r.get("bidNtceNo") == "A1" for r in rows)
    assert any(bgn >= date(2026, 11, 20) for bgn, _ in calls)


def test_order_plans_use_14_day_windows(monkeypatch):
    """X-02: month windows return 0 after portal change; keep ≤14d posted chunks."""
    client = _client_no_http(monkeypatch)
    posted_start, posted_end = date(2025, 10, 16), date(2026, 11, 20)
    expected = list(day_windows(posted_start, posted_end, max_days=ORDER_PLAN_POSTED_WINDOW_DAYS))
    seen_windows: list[tuple[date, date]] = []

    def fake_pages(url, params, page_size=500):
        bgn = date(
            int(params["inqryBgnDt"][:4]),
            int(params["inqryBgnDt"][4:6]),
            int(params["inqryBgnDt"][6:8]),
        )
        edn = date(
            int(params["inqryEndDt"][:4]),
            int(params["inqryEndDt"][4:6]),
            int(params["inqryEndDt"][6:8]),
        )
        seen_windows.append((bgn, edn))
        return iter([])

    monkeypatch.setattr(client, "iter_pages", fake_pages)
    client.fetch_order_plans(
        ["AI"],
        date(2026, 11, 1),
        date(2027, 11, 1),
        posted_start,
        posted_end,
        biz_types=["servc"],
    )
    assert ORDER_PLAN_POSTED_WINDOW_DAYS == 14
    assert seen_windows == expected
    assert all((edn - bgn).days + 1 <= 14 for bgn, edn in seen_windows)

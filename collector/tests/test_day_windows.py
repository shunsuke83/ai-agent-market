from datetime import date
from pathlib import Path

from g2b.client import day_windows
from g2b.collect import _range_has_weekday, cmd_collect


def test_day_windows_splits_14_days_into_7_day_chunks():
    windows = list(day_windows(date(2026, 11, 7), date(2026, 11, 20), max_days=7))
    assert windows == [
        (date(2026, 11, 7), date(2026, 11, 13)),
        (date(2026, 11, 14), date(2026, 11, 20)),
    ]
    assert all((edn - bgn).days + 1 <= 7 for bgn, edn in windows)


def test_day_windows_single_day():
    assert list(day_windows(date(2026, 11, 20), date(2026, 11, 20))) == [
        (date(2026, 11, 20), date(2026, 11, 20))
    ]


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

def test_collect_plans_fails_when_previous_also_empty(tmp_path, monkeypatch):
    import argparse
    import json
    from datetime import date

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


def test_collect_plans_keeps_previous_when_fetch_empty(tmp_path, monkeypatch):
    import argparse
    import json
    from datetime import date

    from g2b.collect import cmd_collect_plans

    out = tmp_path / "order_plans.json"
    out.write_text(
        json.dumps({"plans": [{"plan_no": "P1", "title": "유지"}], "generated_at": "x"}),
        encoding="utf-8",
    )

    class Empty:
        def fetch_order_plans(self, *a, **k):
            return []

    monkeypatch.setattr("g2b.client.G2BClient", lambda: Empty())
    monkeypatch.setattr("g2b.collect._today_kst", lambda: date(2026, 11, 20))
    args = argparse.Namespace(months_ahead=12, posted_days=400, out=str(out))
    assert cmd_collect_plans(args) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["plans"][0]["plan_no"] == "P1"

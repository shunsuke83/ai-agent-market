import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import g2b.client as client_mod
from g2b.collect import cmd_enrich_awards


class FakeClient:
    def __init__(self, *a, **k):
        self.looked: list[str] = []
        self.lookup_errors = 0
        FakeClient.instance = self

    def fetch_awards_range(self, start, end):
        return []

    def fetch_award_by_bid(self, bid_no, bid_ord=None):
        self.looked.append(bid_no)
        return None


def _notice(bid_no, days_ago, **extra):
    n = {
        "bid_no": bid_no,
        "bid_ord": "000",
        "open_date": (date.today() - timedelta(days=days_ago)).isoformat(),
        "title": bid_no,
    }
    n.update(extra)
    return n


def test_lookup_skips_dead_notices_and_prefers_overdue(tmp_path, monkeypatch):
    notices = [
        _notice("RECENT-SMALL", 3, budget_eok=0.2),
        _notice("CANCELLED", 100, ntce_kind="취소공고", budget_eok=20),
        _notice("FAILED", 100, status="유찰", budget_eok=20),
        _notice("OVERDUE-SMALL", 90, budget_eok=1.0),
        _notice("OVERDUE-BIG", 120, budget_eok=25.0),
        _notice("LOOKED-LAST-WEEK", 200, budget_eok=30.0,
                award_lookup_at=(date.today() - timedelta(days=7)).isoformat()),
        _notice("WON", 120, winner="A", budget_eok=25.0),
    ]
    out = tmp_path / "notices.json"
    out.write_text(json.dumps({"notices": notices}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(client_mod, "G2BClient", FakeClient)

    args = argparse.Namespace(
        out=str(out), until=None, days=30, since=None, max_span_days=120,
        lookup_missing=True, lookup_limit=3,
    )
    assert cmd_enrich_awards(args) == 0
    assert FakeClient.instance.looked == ["OVERDUE-BIG", "OVERDUE-SMALL", "RECENT-SMALL"]

    saved = {n["bid_no"]: n for n in json.loads(out.read_text(encoding="utf-8"))["notices"]}
    assert saved["OVERDUE-BIG"]["award_lookup_at"] == date.today().isoformat()
    assert "award_lookup_at" not in saved["CANCELLED"]


def test_range_fetch_failure_still_runs_lookups(tmp_path, monkeypatch):
    class FlakyRange(FakeClient):
        def fetch_awards_range(self, start, end):
            raise client_mod.G2BError("HTTP retries exhausted: HTTP 500")

    out = tmp_path / "notices.json"
    out.write_text(
        json.dumps({"notices": [_notice("OVERDUE", 90, budget_eok=10)]}), encoding="utf-8"
    )
    monkeypatch.setattr(client_mod, "G2BClient", FlakyRange)
    args = argparse.Namespace(
        out=str(out), until=None, days=30, since=None, max_span_days=120,
        lookup_missing=True, lookup_limit=5,
    )
    assert cmd_enrich_awards(args) == 0
    assert FakeClient.instance.looked == ["OVERDUE"]

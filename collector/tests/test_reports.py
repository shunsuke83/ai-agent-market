import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.reports import (
    CORE_NATURES,
    aggregate_month_bidders,
    aggregate_monthly,
    aggregate_weekly,
    clean_bidder_name,
    iso_week_bounds,
    last_completed_iso_week,
    nature_label,
    sane_budget,
)

ROOT = Path(__file__).resolve().parents[2]


def test_sane_budget_won_misstored():
    assert sane_budget(9_185_000) == 0.0919
    assert sane_budget(10.5) == 10.5
    assert sane_budget(None) is None


def test_nature_label_mapping():
    assert nature_label("ISP·전략") == "ISP·전략·컨설팅"
    assert nature_label("인프라") == "인프라(GPU·서버·장비)"
    assert nature_label(None) == "기타"
    assert nature_label("시스템 구축·고도화") == "시스템 구축·고도화"


def test_iso_week_w43_2026():
    start, end = iso_week_bounds(2026, 43)
    assert start == date(2026, 10, 19)
    assert end == date(2026, 10, 25)


def test_last_completed_iso_week():
    # Thursday 2026-10-29 → last completed week is W43
    assert last_completed_iso_week(date(2026, 10, 29)) == (2026, 43)
    # Monday 2026-10-26 → last completed is still W43 (ended Sunday 10-25)
    assert last_completed_iso_week(date(2026, 10, 26)) == (2026, 43)


def test_aggregate_weekly_w43_from_notices():
    import json

    raw = json.loads((ROOT / "data" / "notices.json").read_text(encoding="utf-8"))
    notices = raw["notices"]
    agg = aggregate_weekly(notices, 2026, 43, today=date(2026, 10, 29))
    assert agg["start"] == date(2026, 10, 19)
    assert len(agg["core"]) >= 50
    assert all(n.get("nature") in CORE_NATURES for n in agg["core"])
    assert agg["budget_sum"] > 0
    assert agg["other_count"] > 0
    for n in agg["upcoming"]:
        assert n.get("nature") in CORE_NATURES
        assert (sane_budget(n.get("budget_eok")) or 0) >= 1.0


def test_aggregate_monthly_oct():
    import json

    raw = json.loads((ROOT / "data" / "notices.json").read_text(encoding="utf-8"))
    notices = raw["notices"]
    agg = aggregate_monthly(notices, 2026, 10, today=date(2026, 10, 29))
    assert agg["in_progress"] is True
    assert len(agg["core"]) >= 100
    assert len(agg["trend"]) == 12
    assert agg["trend"][-1]["ym"] == "2026-10"
    assert agg["large_count"] >= 1
    assert len(agg["top10"]) <= 10
    # OpengCompt-backed bid table (no empty firm names)
    assert len(agg["bidders"]) >= 5
    assert all(name and count >= 1 for name, count in agg["bidders"])
    assert agg["bidders"] == sorted(
        agg["bidders"], key=lambda x: (-x[1], x[0])
    )


def test_clean_bidder_name_strips_rank():
    assert clean_bidder_name("타임리 (1순위)") == "타임리"
    assert clean_bidder_name("") == ""
    assert clean_bidder_name(None) == ""


def test_aggregate_month_bidders_skips_blank_and_counts_unique():
    notices = [
        {
            "bid_no": "A1",
            "bid_ord": "000",
            "open_date": "2026-10-10",
            "bidders": [
                {"rank": 1, "name": ""},
                {"rank": 2, "name": "알파"},
                {"rank": 3, "name": "베타"},
            ],
        },
        {
            "bid_no": "A2",
            "bid_ord": "000",
            "open_date": "2026-10-15",
            "bidders": [
                {"rank": 1, "name": "알파 (1순위)"},
            ],
        },
        {
            "bid_no": "A3",
            "bid_ord": "000",
            "open_date": "2026-09-01",
            "bidders": [{"rank": 1, "name": "감마"}],
        },
    ]
    ranked = aggregate_month_bidders(
        notices, date(2026, 10, 1), date(2026, 10, 31), limit=10
    )
    assert ranked[0] == ("알파", 2)
    assert ("베타", 1) in ranked
    assert all(name for name, _ in ranked)
    assert not any(name == "감마" for name, _ in ranked)

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


def test_weekly_monthly_html_include_fit_when_profile():
    from datetime import datetime

    from g2b.render import KST
    from g2b.reports import render_monthly_html, render_weekly_html
    from tests.test_gonogo_policy import PROFILE

    notices = [
        {
            "bid_no": "R26FIT1",
            "title": "생성형 AI LLM 챗봇 구축",
            "org": "한국가스공사",
            "budget_eok": 10.0,
            "fields": ["생성형·LLM"],
            "nature": "시스템 구축·고도화",
            "notice_date": "2026-10-20",
            "open_date": "2026-11-05",
            "close_at": "2026-11-20 10:00",
            "contract_method": "협상에 의한 계약",
        }
    ]
    weekly = {
        "year": 2026,
        "week": 43,
        "start": date(2026, 10, 19),
        "end": date(2026, 10, 25),
        "core": notices,
        "gen_count": 1,
        "budget_sum": 10.0,
        "other_count": 0,
        "awards": [],
        "failed_count": 0,
        "pending_count": 0,
        "upcoming": notices,
        "slug": "weekly-2026-W43",
    }
    monthly = {
        "year": 2026,
        "month": 10,
        "end": date(2026, 10, 31),
        "in_progress": False,
        "core": notices,
        "budget_sum": 10.0,
        "prev_count": 0,
        "prev_budget": 0.0,
        "large_count": 0,
        "isp_count": 0,
        "isp": [],
        "trend": [{"ym": "2026-10", "label": "10월", "count": 1, "gen": 1, "sw": 0}],
        "natures": [("시스템 구축·고도화", 1)],
        "fields": [("생성형·LLM", 1)],
        "top10": notices,
        "top_orgs": [("한국가스공사", 1)],
        "winners": [],
        "bidders": [],
        "slug": "monthly-2026-10",
    }
    now = datetime(2026, 11, 2, 9, 0, tzinfo=KST)
    wh = render_weekly_html(weekly, profile=PROFILE, now=now)
    mh = render_monthly_html(monthly, profile=PROFILE, now=now)
    assert "적합도 · 참여 여부" in wh
    assert "fit-pill" in wh and "<th>참여</th>" in wh
    assert "적합도 · 참여 여부" in mh
    assert "fit-pill" in mh and "<th>참여</th>" in mh


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

import json
from datetime import datetime

import pytest

from g2b import alerts
from g2b.alerts import (
    _fold,
    build_ics,
    build_items,
    build_rss,
    matches,
    new_by_rule,
    run_alerts,
    slack_text,
)
from g2b.render import KST

SITE = "https://example.test/site/"
NOW = datetime(2026, 11, 1, 13, 0, tzinfo=KST)
RULES = [
    {"id": "genai", "name": "생성형", "match": {"kinds": ["notice", "prespec"], "scope": ["생성형·Agent"], "min_eok": 1}},
    {"id": "band", "name": "8~30억 구축", "match": {"kinds": ["notice"], "nature": ["시스템 구축·고도화"], "min_eok": 8, "max_eok": 30}},
]
CONFIG = {"site_url": SITE, "rules": RULES, "slack_max_age_days": 7, "slack_limit_per_rule": 15, "calendar_days": 60}


def _n(i, **kw):
    base = {
        "bid_no": f"R26BK{i:04d}",
        "bid_ord": "000",
        "title": f"생성형 AI 챗봇 구축 {i}",
        "org": "테스트청",
        "scope": "생성형·Agent",
        "fields": ["생성형·LLM"],
        "nature": "시스템 구축·고도화",
        "biz": "servc",
        "budget_eok": 12.0,
        "notice_date": "2026-10-30",
        "close_at": "2026-11-10 10:00",
    }
    return {**base, **kw}


def _p(i, **kw):
    base = {
        "prespec_no": f"R26BD{i:04d}",
        "title": f"생성형 AI 플랫폼 구축 {i}",
        "org": "예시부",
        "scope": "생성형·Agent",
        "fields": ["생성형·LLM"],
        "nature": "시스템 구축·고도화",
        "biz": "servc",
        "asign_budget_eok": 5.0,
        "registered_date": "2026-10-31",
        "opinion_close_at": "2026-11-05 18:00",
    }
    return {**base, **kw}


def test_items_skip_cancelled_and_equipment():
    items = build_items(
        [_n(1), _n(2, ntce_kind="취소공고"), _n(3, title="AI 학습용 GPU 서버 구매", biz="thng")],
        [_p(1)],
        SITE,
    )
    assert [i["key"] for i in items] == ["n:R26BK0001-000", "p:R26BD0001"]
    assert items[0]["url"] == SITE + "bids/R26BK0001-000.html"


def test_match_conditions_are_anded():
    (item,) = build_items([_n(1)], [], SITE)
    assert matches(item, RULES[0]["match"])
    assert matches(item, RULES[1]["match"])
    assert not matches(item, {"orgs": ["경찰청"]})
    assert matches(item, {"orgs": ["테스트"], "keywords": ["챗봇"]})
    assert not matches(item, {"min_eok": 30})
    assert not matches(item, {"kinds": ["prespec"]})


def test_new_items_show_under_first_rule_only_and_skip_sent_or_old():
    items = build_items([_n(1), _n(2), _n(3, notice_date="2026-09-01")], [_p(1)], SITE)
    groups = new_by_rule(items, RULES, {"n:R26BK0002-000": "2026-10-31"}, "2026-10-25")
    assert [(r["id"], [i["key"] for i in got]) for r, got in groups] == [
        ("genai", ["p:R26BD0001", "n:R26BK0001-000"])
    ]


def test_new_items_drop_notices_past_deadline_but_keep_closed_prespecs():
    items = build_items(
        [_n(1, close_at="2026-10-31 10:00"), _n(2)],
        [_p(1, opinion_close_at="2026-10-31 18:00")],
        SITE,
    )
    groups = new_by_rule(items, RULES, {}, "2026-10-25", "2026-11-01 13:00")
    assert [i["key"] for _, got in groups for i in got] == ["p:R26BD0001", "n:R26BK0002-000"]


def test_slack_text_escapes_and_truncates():
    items = build_items([_n(i, title=f"A<B> & C|{i}") for i in range(4)], [], SITE)
    text = slack_text(new_by_rule(items, RULES[:1], {}, "2026-01-01"), NOW.date(), 2, SITE)
    assert "A&lt;B&gt; &amp; C¦" in text
    assert "…외 2건" in text and f"{SITE}feeds/genai.xml" in text


def test_rss_and_ics_are_well_formed():
    items = build_items([_n(1), _n(2, close_at="2026-10-01 10:00")], [_p(1)], SITE)
    rss = build_rss(RULES[0], items, SITE)
    assert rss.count("<item>") == 3 and "[사전규격]" in rss
    ics = build_ics(items, NOW, 60)
    assert ics.count("BEGIN:VEVENT") == 2  # past deadline dropped
    assert "DTSTART;TZID=Asia/Seoul:20261110T100000" in ics
    assert "사전규격 의견 마감" in ics
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))


def test_fold_keeps_multibyte_chars_intact():
    folded = _fold("SUMMARY:" + "가" * 60)
    assert "".join(part.lstrip(" ") for part in folded.split("\r\n")) == "SUMMARY:" + "가" * 60


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "notices.json").write_text(json.dumps({"notices": [_n(1)]}), encoding="utf-8")
    (tmp_path / "data" / "prespecs.json").write_text(json.dumps({"prespecs": [_p(1)]}), encoding="utf-8")
    return tmp_path


def test_run_alerts_posts_once_and_records_state(repo, monkeypatch):
    posted = []
    monkeypatch.setattr(alerts, "post_slack", lambda url, text: posted.append(text))
    first = run_alerts(repo, now=NOW, webhook="https://hooks.test/x", config=CONFIG)
    assert first["slack"] == "sent" and first["new"] == 2 and len(posted) == 1
    assert (repo / "feeds" / "genai.xml").exists() and (repo / "feeds" / "deadlines.ics").exists()
    assert "알림 구독" in (repo / "alerts.html").read_text(encoding="utf-8")
    second = run_alerts(repo, now=NOW, webhook="https://hooks.test/x", config=CONFIG)
    assert second["slack"] == "nothing new" and len(posted) == 1


def test_run_alerts_without_webhook_keeps_items_pending(repo):
    out = run_alerts(repo, now=NOW, webhook="", config=CONFIG)
    assert out["slack"] == "no SLACK_WEBHOOK_URL" and out["new"] == 2
    assert not (repo / "data" / "alerts_state.json").exists()

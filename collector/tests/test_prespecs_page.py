from datetime import datetime

from g2b.prespecs import (
    STATUS_BID,
    STATUS_CLOSED,
    STATUS_OPEN,
    prespec_status,
    render_prespecs_html,
)
from g2b.render import KST

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=KST)


def _p(**kw):
    base = {
        "prespec_no": "R26BD1",
        "title": "AI 상담 챗봇 구축",
        "org": "테스트청",
        "registered_at": "2026-10-28 09:00",
        "registered_date": "2026-10-28",
        "opinion_close_at": "2026-11-02 18:00",
        "asign_budget_eok": 12.0,
        "scope": "생성형·Agent",
        "bid_nos": [],
        "spec_files": ["https://example/a?x=1&y=2"],
    }
    return {**base, **kw}


def test_status_prefers_posted_bid_then_opinion_window():
    assert prespec_status(_p(), NOW) == STATUS_OPEN
    assert prespec_status(_p(opinion_close_at="2026-10-29 18:00"), NOW) == STATUS_CLOSED
    assert prespec_status(_p(opinion_close_at=None), NOW) == STATUS_CLOSED
    assert prespec_status(_p(bid_nos=["R26BK1"]), NOW) == STATUS_BID


def test_page_counts_and_escapes_links():
    rows = [_p(), _p(prespec_no="R26BD2", asign_budget_eok=3.0, bid_nos=["R26BK9"])]
    status = {"stages": {"prespecs": {"last_outcome": "failure",
                                      "last_success_at": "2026-10-29T06:00:00Z",
                                      "last_attempt_at": "2026-10-30T06:00:00Z"}}}
    out = render_prespecs_html(rows, status, NOW)
    assert '<div class="v">2건</div>' in out
    assert '<div class="v">1건</div><div class="l">의견 접수 중</div>' in out
    assert "x=1&amp;y=2" in out
    assert "bidPbancNo=R26BK9" in out
    assert "최근 수집 실패 2026-10-30" in out
    assert 'class="notices prespecs js-filter"' in out

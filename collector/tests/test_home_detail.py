from datetime import date, datetime

from g2b.detail import render_detail_html
from g2b.home import build_home
from g2b.render import KST, title_link

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=KST)


def _n(**kw):
    base = {
        "bid_no": "R26BK1",
        "bid_ord": "000",
        "title": "AI 상담 챗봇 구축",
        "org": "테스트청",
        "scope": "생성형·Agent",
        "nature": "시스템 구축·고도화",
        "biz": "servc",
        "notice_date": "2026-10-28",
        "close_at": "2026-11-03 10:00",
        "open_date": "2026-11-03",
        "budget_eok": 12.0,
    }
    return {**base, **kw}


def test_title_link_points_to_detail_page():
    assert 'href="bids/R26BK1-000.html"' in title_link(_n())
    assert 'href="../bids/R26BK1-000.html"' in title_link(_n(), "../")
    assert "g2b.go.kr" in title_link(_n(bid_no=None, g2b_url="https://www.g2b.go.kr/x"))


def test_home_lists_only_open_real_opportunities():
    notices = [
        _n(),
        _n(bid_no="CLOSED", title="AI 플랫폼 구축", close_at="2026-10-29 10:00"),
        _n(bid_no="TINY", title="AI 챗봇 소규모", budget_eok=0.3),
        _n(bid_no="HW", title="AI 학습용 GPU 서버 구매", biz="thng"),
        _n(bid_no="LATER", title="AI 분석 시스템 구축", close_at="2026-11-20 10:00"),
    ]
    out = build_home(notices, [], {}, now=NOW)
    closing = out.split("<h2>마감 임박")[1].split("<h2>")[0]
    assert "R26BK1-000" in closing
    for bid in ("CLOSED", "TINY", "HW", "LATER"):
        assert bid not in closing
    assert '<div class="v">2건</div><div class="l">입찰 접수 중인 AI 공고</div>' in out


def test_detail_shows_first_rank_and_unknown_amount():
    pending = render_detail_html(
        _n(status="1순위", first_rank="가나다", bidders=[{"rank": 1, "name": "가나다", "amount_eok": 11.0, "rate_pct": 88.1}]),
        today=date(2026, 11, 5),
    )
    assert "개찰 1순위" in pending and "낙찰 확정 전" in pending
    assert "<th>낙찰자</th>" not in pending
    assert "88.100%" in pending
    won = render_detail_html(_n(winner="라마바", status="낙찰"), today=date(2026, 11, 5))
    assert "<th>낙찰자</th><td>라마바</td>" in won
    assert "미확인" in won
    assert 'href="../assets/site.css' in won

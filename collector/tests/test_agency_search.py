from datetime import date

from g2b.agencies import build_agencies_page, build_agency_index
from g2b.detail import _org_link


def _n(bid_no, org, winner=None, **kw):
    return {"bid_no": bid_no, "bid_ord": "000", "org": org, "title": f"AI 사업 {bid_no}",
            "notice_date": kw.pop("notice_date", "2026-10-01"), "budget_eok": 10.0,
            "winner": winner, "status": "낙찰" if winner else None, **kw}


def test_index_rows_dedupe_and_keep_winner_bizno():
    notices = [
        _n("A1", "한국전력공사", "에이(주)", award_amount_eok=9.1, bid_count=3, scope="생성형·Agent",
           bidders=[{"rank": 1, "name": "에이(주)", "bizno": "1111111111"}]),
        _n("A1", "한국전력공사", "에이(주)"),
        _n("B1", "통일부", first_rank="비", open_date="2026-01-05"),
        _n("C1", ""),
    ]
    rows = build_agency_index(notices, date(2026, 11, 9))["notices"]
    assert len(rows) == 2
    a = next(r for r in rows if r[1] == "한국전력공사")
    assert a[5:11] == ["에이(주)", "1111111111", 9.1, "낙찰", 3, 1]
    assert a[4] == "bids/A1-000.html"
    b = next(r for r in rows if r[1] == "통일부")
    assert b[5] == "비" and b[6] == "" and b[8] != "낙찰"


def test_page_and_org_link():
    html = build_agencies_page({"notices": [["2026-10-01", "통일부", "t", 1.0, "", "", "", None, "공고중", None, 0]]},
                               {}, "abc")
    assert 'data-src="data/agencies.json?v=abc"' in html and "assets/agency-search.js" in html
    assert 'href="agencies.html"' in html
    assert _org_link("한국 전력") == (
        '<a href="../agencies.html#org=%ED%95%9C%EA%B5%AD%20%EC%A0%84%EB%A0%A5" '
        'title="이 기관의 AI 사업 공고 모두 보기">한국 전력</a>'
    )

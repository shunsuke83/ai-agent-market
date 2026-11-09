from datetime import date

from g2b.bidders import build_bidder_index, build_bidders_page
from g2b.site import stamp_shell


def _notice(bid_no, open_date, bidders, winner=None):
    return {"bid_no": bid_no, "bid_ord": "000", "open_date": open_date, "org": "기관", "title": f"사업 {bid_no}",
            "budget_eok": 10.0, "winner": winner, "status": "낙찰" if winner else None, "bidders": bidders}


def test_bidder_index_groups_by_bizno_and_drops_ceo():
    notices = [
        _notice("R1", "2026-10-01", [
            {"rank": 1, "name": "에이", "bizno": "111-11-11111", "rate_pct": 88.5, "amount_eok": 8.85, "ceo": "홍길동"},
            {"rank": 2, "name": "비", "bizno": "2222222222", "rate_pct": 90.0, "amount_eok": 9.0},
        ], winner="에이"),
        _notice("R2", "2026-11-01", [{"rank": 1, "name": "에이(구)", "bizno": "1111111111", "rate_pct": 87.0}]),
        _notice("R3", "2026-11-02", [{"rank": 1, "name": "번호없음"}]),
        _notice("R1", "2026-10-01", [{"rank": 1, "name": "에이", "bizno": "1111111111"}]),
    ]
    idx = build_bidder_index(notices, {"2222222222": {"corp_name": "비주식", "employees": 30}}, date(2026, 11, 6))

    assert [r[2] for r in idx["notices"]] == ["사업 R2", "사업 R1"]
    assert idx["notices"][1][4] == "bids/R1-000.html"
    assert idx["notices"][1][5] == "1111111111"
    a = idx["firms"]["1111111111"]
    assert a[0] == "에이(구)" and [b[0] for b in a[2]] == [0, 1]
    assert idx["firms"]["2222222222"][:2] == ["비주식", "종업원 30명"]
    assert "홍길동" not in str(idx)


def test_bidders_page_points_at_versioned_index():
    html = build_bidders_page({"notices": [["2026-10-01", "", "", None, "", "", ""]], "firms": {"1": ["a", "", []]}},
                              {}, "abc123")
    assert 'data-src="data/bidders.json?v=abc123"' in html
    assert "assets/bidder-search.js" in html and 'href="bidders.html"' in html


def test_stamp_shell_replaces_hand_nav():
    out = stamp_shell('<nav class="top"><b>x</b><a href="band.html">8~30억</a></nav><p>본문</p>')
    assert 'href="bidders.html"' in out and 'href="plans.html"' in out and out.endswith("<p>본문</p>")

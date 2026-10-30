import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.normalize import apply_bidders_to_notice, normalize_bid_item
from g2b.render import render_notice_row

BASE = {
    "bidNtceNo": "R26BK00000001",
    "bidNtceOrd": "000",
    "bidNtceNm": "생성형 AI 기반 민원 상담 플랫폼 구축",
    "dminsttNm": "테스트청",
    "bidNtceDt": "2026-10-20 10:00:00",
}


def test_close_and_open_are_separate_events():
    n = normalize_bid_item(
        dict(BASE, bidClseDt="2026-11-03 10:00:00", opengDt="2026-11-03 11:00:00")
    )
    assert n["close_at"] == "2026-11-03 10:00"
    assert n["open_at"] == "2026-11-03 11:00"
    assert n["open_date"] == "2026-11-03"


def test_missing_opening_is_not_filled_from_close():
    n = normalize_bid_item(dict(BASE, bidClseDt="2026-11-03 10:00:00"))
    assert n["open_date"] is None and n["open_at"] is None
    assert n["close_date"] == "2026-11-03"


def test_budget_kind_records_which_money_field_was_used():
    n = normalize_bid_item(dict(BASE, presmptPrce="900000000", bsisAmount="990000000"))
    assert n["budget_kind"] == "추정가격"
    assert n["budget_eok"] == 9.0
    assert n["base_amount_eok"] == 9.9
    assert n["asign_budget_eok"] is None
    n = normalize_bid_item(dict(BASE, asignBdgtAmt="1000000000", presmptPrce="900000000"))
    assert (n["budget_kind"], n["budget_eok"]) == ("배정예산", 10.0)
    assert 'title="배정예산 기준"' in render_notice_row(n)


def test_bidders_do_not_overwrite_failed_status():
    n = apply_bidders_to_notice(
        {"bid_no": "X", "status": "유찰"}, [{"prcbdrNm": "알파", "opengRank": "1"}]
    )
    assert n["status"] == "유찰"
    assert n["first_rank"] == "알파"

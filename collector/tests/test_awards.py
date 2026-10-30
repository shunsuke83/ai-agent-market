import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.normalize import (
    always_won_to_eok,
    apply_awards_to_notices,
    clean_firm_name,
    coerce_stored_eok,
    normalize_award_item,
    normalize_bid_item,
    sanitize_notice_money_fields,
)


def test_clean_firm_name():
    assert clean_firm_name("대신정보통신 주식회사") == "대신정보통신"
    assert clean_firm_name("(주)엔디에스") == "엔디에스"


def test_normalize_award_item():
    row = normalize_award_item(
        {
            "bidNtceNo": "R26BK01409553",
            "bidNtceOrd": "001",
            "bidwinnrNm": "대신정보통신 주식회사",
            "prtcptCnum": "4",
            "sucsfbidAmt": "21601800000",
            "sucsfbidRate": "99.5",
            "rlOpengDt": "2026-05-08 17:33:32",
            "dminsttNm": "국방통합데이터센터",
            "bidNtceNm": "GPU 서버 구축",
            "_biz": "servc",
        }
    )
    assert row is not None
    assert row["bid_no"] == "R26BK01409553"
    assert row["winner"] == "대신정보통신"
    assert row["bid_count"] == 4
    assert abs(row["award_amount_eok"] - 216.018) < 0.001
    assert row["win_rate_pct"] == 99.5
    assert row["status"] == "낙찰"


def test_small_award_amount_is_won():
    row = normalize_award_item(
        {
            "bidNtceNo": "R26BK0001",
            "bidNtceOrd": "000",
            "bidwinnrNm": "테스트",
            "sucsfbidAmt": "6388800",  # 원 (< 1천만) must still convert
            "prtcptCnum": "1",
        }
    )
    assert row is not None
    assert abs(row["award_amount_eok"] - 0.0639) < 0.0001


def test_bid_budget_always_treated_as_won():
    row = normalize_bid_item(
        {
            "bidNtceNo": "R26BK01788034",
            "bidNtceOrd": "000",
            "bidNtceNm": "AI를 활용한 창업교육 용역",
            "asignBdgtAmt": "6655000",  # 원 → 0.06655억
            "dminsttNm": "연세대학교",
            "opengDt": "202610261000",
            "bidNtceDt": "202610200000",
        }
    )
    assert row is not None
    assert abs(row["budget_eok"] - 0.0666) < 0.0002


def test_sanitize_repairs_won_left_in_budget_eok():
    n, changed = sanitize_notice_money_fields(
        {"bid_no": "X", "budget_eok": 6_655_000.0, "award_amount_eok": 0.0639}
    )
    assert changed
    assert abs(n["budget_eok"] - 0.0666) < 0.0002
    assert n["award_amount_eok"] == 0.0639
    assert coerce_stored_eok(6_655_000) == always_won_to_eok(6_655_000)


def test_apply_awards_to_notices():
    notices = [
        {
            "bid_no": "R26BK01409553",
            "bid_ord": "001",
            "title": "GPU",
            "budget_eok": 217.1,
            "status": "개찰 확인 필요",
        }
    ]
    awards = [
        {
            "bid_no": "R26BK01409553",
            "bid_ord": "001",
            "winner": "대신정보통신",
            "bid_count": 4,
            "award_amount_eok": 216.0,
            "win_rate_pct": None,
            "status": "낙찰",
        }
    ]
    out, n = apply_awards_to_notices(notices, awards)
    assert n == 1
    assert out[0]["winner"] == "대신정보통신"
    assert out[0]["status"] == "낙찰"
    # award/budget is not the API 낙찰률 (vs 예정가격); keep them apart
    assert out[0].get("win_rate_pct") is None
    assert out[0]["award_to_budget_pct"] == 99.5

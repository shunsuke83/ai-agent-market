import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.normalize import (
    apply_awards_to_notices,
    clean_firm_name,
    normalize_award_item,
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
    assert out[0]["win_rate_pct"] == 99.5  # derived from amount/budget

from g2b.normalize import collapse_rounds


def row(bid_no, ord_="000", **kw):
    return {"bid_no": bid_no, "bid_ord": ord_, "title": "AI 상담 시스템 구축", "org": "기관", "notice_date": "2026-10-01", **kw}


def test_latest_round_kept_and_filled_from_older():
    out = collapse_rounds([row("A", winner="(주)갑"), row("A", "001", ntce_kind="변경공고", winner="")])
    assert len(out) == 1
    assert out[0]["bid_ord"] == "001" and out[0]["winner"] == "(주)갑"


def test_cancelled_latest_round_dropped():
    assert collapse_rounds([row("A"), row("A", "001", ntce_kind="취소공고")]) == []


def test_rows_without_bid_no_pass_through():
    assert collapse_rounds([{"title": "x"}]) == [{"title": "x"}]


def test_reissue_replaces_earlier_notice_without_winner():
    old = row("A")
    new = row("B", ntce_kind="재공고", prev_bid_no="A", notice_date="2026-10-10")
    assert [r["bid_no"] for r in collapse_rounds([old, new])] == ["B"]
    unlinked = {**new, "prev_bid_no": ""}
    assert [r["bid_no"] for r in collapse_rounds([old, unlinked])] == ["B"]


def test_awarded_or_old_notices_with_same_title_kept():
    awarded = row("A", winner="(주)갑")
    new = row("B", notice_date="2026-10-10")
    assert len(collapse_rounds([awarded, new])) == 2
    last_year = row("C", notice_date="2025-10-01")
    assert len(collapse_rounds([last_year, new])) == 2

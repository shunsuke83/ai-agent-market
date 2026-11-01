from datetime import date, datetime

from g2b.detail import render_detail_html
from g2b.home import build_home
from g2b.pricing import (
    ContextIndex,
    bid_rate,
    budget_band,
    build_pricing,
    competition_rows,
    context_html,
    firm_habits,
    rate_rows,
    weak_competition,
    winner_rate,
)
from g2b.render import KST

TODAY = date(2026, 11, 1)


def _b(rank, name, rate, bizno=None):
    return {"rank": rank, "name": name, "amount_eok": 1.0, "rate_pct": rate, "bizno": bizno}


def _n(i, **kw):
    base = {
        "bid_no": f"R26BK{i:04d}",
        "bid_ord": "000",
        "title": f"AI 플랫폼 구축 {i}",
        "org": "테스트청",
        "nature": "시스템 구축·고도화",
        "contract_method": "제한경쟁",
        "budget_eok": 12.0,
        "open_date": "2026-10-01",
        "status": "낙찰",
        "winner": "가나",
        "bid_count": 2,
        "bidders": [_b(1, "가나", 88.0 + i * 0.1, "111"), _b(2, "다라", 90.0, "222")],
    }
    return {**base, **kw}


def test_bid_rate_drops_price_scores_and_outliers():
    assert bid_rate({"rate_pct": 87.9}) == 87.9
    assert bid_rate({"rate_pct": 12.5}) is None  # 협상계약 가격평가 점수
    assert bid_rate({"rate_pct": 241.4}) is None
    assert bid_rate({"rate_pct": None}) is None


def test_budget_band_edges():
    assert budget_band(0.5) == "1억 미만"
    assert budget_band(8.0) == "8~30억"
    assert budget_band(30.0) == "30억 이상"
    assert budget_band(None) is None


def test_winner_rate_uses_winner_row_not_rank_one():
    n = _n(1, winner="다라")
    assert winner_rate(n) == 90.0
    assert winner_rate(_n(1, winner=None)) is None


def test_rate_rows_hide_figures_under_min_sample():
    rows = {r["label"]: r for r in rate_rows([_n(i) for i in range(5)] + [_n(9, nature="ISP·전략")], lambda n: n["nature"])}
    assert rows["시스템 구축·고도화"]["n"] == 5 and rows["시스템 구축·고도화"]["q"] is not None
    assert rows["ISP·전략"]["n"] == 1 and rows["ISP·전략"]["q"] is None


def test_competition_excludes_sole_source_contracts():
    notices = [_n(i, bid_count=1 if i < 2 else 3) for i in range(5)] + [
        _n(10 + i, contract_method="수의계약", bid_count=1) for i in range(5)
    ]
    (row,) = competition_rows(notices, lambda n: n["nature"])
    assert row["n"] == 5
    assert row["single_pct"] == 40.0


def test_firm_habits_groups_by_bizno_and_counts_wins():
    notices = [_n(i) for i in range(6)]
    notices[0]["bidders"][0]["name"] = "가나(주)"  # renamed, same 사업자번호
    rows = {r["name"]: r for r in firm_habits(notices)}
    assert set(rows) == {"가나", "다라"}
    assert rows["가나"]["bids"] == 6 and rows["가나"]["wins"] == 6
    assert rows["다라"]["wins"] == 0 and rows["다라"]["median_rate"] == 90.0


def test_weak_competition_lists_failed_and_single_bids_but_not_sole_source():
    notices = [
        _n(1, status="유찰", winner=None, bid_count=None, bidders=[]),
        _n(2, bid_count=1, open_date="2026-10-20"),
        _n(3, bid_count=1, contract_method="수의계약"),
        _n(4, bid_count=4),
        _n(5, bid_count=1, open_date="2025-01-01"),
    ]
    got = [n["bid_no"] for n in weak_competition(notices, TODAY)]
    assert got == ["R26BK0002", "R26BK0001"]


def test_weak_competition_merges_rebid_rounds_and_drops_hardware():
    notices = [
        _n(1, title="AI 관제 플랫폼 구축", bid_count=1, open_date="2026-09-01"),
        _n(2, title="AI 관제 플랫폼 구축 재공고", bid_count=1, open_date="2026-09-20"),
        _n(3, title="AI 학습용 GPU 서버 구매", biz="thng", bid_count=1),
    ]
    assert [n["bid_no"] for n in weak_competition(notices, TODAY)] == ["R26BK0002"]


def test_context_prefers_same_org_then_falls_back_to_kind():
    pool = [_n(i) for i in range(4)] + [_n(20 + i, org="다른청") for i in range(5)]
    idx = ContextIndex(pool)
    same = idx.context(_n(99))
    assert same["basis"] == "같은 기관" and same["n"] == 4
    assert same["regulars"][0] == ("가나", 4)
    other = idx.context(_n(99, org="처음청"))
    assert other["basis"].startswith("같은 사업 성격·예산대") and other["n"] == 9
    assert idx.context(_n(99, org="처음청", nature="인프라")) is None
    assert context_html(None) == ""
    assert "비슷한 과거 사업의 경쟁" in context_html(same)


def test_detail_page_includes_competition_block():
    ctx = ContextIndex([_n(i) for i in range(5)]).context(_n(99))
    out = render_detail_html(_n(99), competition_html=context_html(ctx), today=TODAY)
    assert "<th>투찰 업체 수</th><td>보통 2곳" in out and "낙찰 투찰률" in out


def test_pricing_page_renders_sections():
    notices = [_n(i) for i in range(6)] + [_n(50, status="유찰", winner=None, bid_count=None, bidders=[])]
    out = build_pricing(notices, {}, TODAY)
    for h in ("낙찰 투찰률 분포", "경쟁 강도", "업체별 투찰 습관", "경쟁이 약했던 사업"):
        assert h in out
    assert 'href="pricing.html"' in out


def test_home_flags_rebid_notices():
    now = datetime(2026, 10, 30, 12, 0, tzinfo=KST)
    n = _n(1, title="AI 상담 챗봇 구축", notice_date="2026-10-28", close_at="2026-11-03 10:00",
           open_date="2026-11-03", status=None, winner=None, bidders=[], ntce_kind="재공고")
    out = build_home([n], [], {}, now=now)
    closing = out.split("<h2>마감 임박")[1].split("<h2>")[0]
    assert "재공고</span>" in closing

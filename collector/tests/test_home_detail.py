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
    assert 'href="bids/R26BK1-000"' in title_link(_n())
    assert 'href="../bids/R26BK1-000"' in title_link(_n(), "../")
    assert "g2b.go.kr" in title_link(_n(bid_no=None, g2b_url="https://www.g2b.go.kr/x"))


def test_home_year_bars_live_from_notices():
    from g2b.home import year_counts

    notices = [
        _n(bid_no="A", notice_date="2025-03-01"),
        _n(bid_no="B", notice_date="2025-11-01"),
        _n(bid_no="C", notice_date="2026-01-15"),
    ]
    assert year_counts(notices) == [("2025", 2), ("2026", 1)]
    out = build_home(notices, [], {}, now=NOW)
    assert "AI 사업 공고 연도별 추이" in out
    assert "2건" in out and "1건" in out
    assert "2026-10-30까지 누계" in out
    assert "2,719건" not in out  # frozen keep-block must not stick


def test_home_closing_lists_all_within_deadline_days():
    """W-02: do not truncate closing-soon to 2×LIMIT=30."""
    notices = [
        _n(
            bid_no=f"C{i:02d}",
            title=f"생성형 AI 챗봇 구축 {i}",
            close_at=f"2026-11-{1 + (i % 5):02d} 10:00",
            budget_eok=10.0 + i,
        )
        for i in range(35)
    ]
    out = build_home(notices, [], {}, now=NOW)
    closing = out.split("<h2>마감 임박")[1].split("<h2>")[0]
    assert all(f"C{i:02d}" in closing for i in range(35))
    assert "건 더 있음" not in closing
    assert "D-3 이하도 펼치기" in closing


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
    for bid in ("CLOSED", "TINY", "LATER"):
        assert bid not in closing
    # 구매·장비는 지우지 않고 제외됨으로 숨긴다.
    assert "제외된 공고" in out and "제외됨" in out and "HW" in out
    assert '<div class="v">2건</div><div class="l">입찰 접수 중인 AI 공고</div>' in out


def test_home_dday_badge_and_competition_column():
    past = [
        _n(bid_no=f"P{i}", notice_date="2026-06-01", close_at="2026-06-10 10:00", open_date="2026-06-10",
           status="낙찰", winner="가나다", bid_count=4 + i,
           bidders=[{"rank": 1, "name": "가나다", "rate_pct": 88.0 + i}, {"rank": 2, "name": f"업체{i}"}])
        for i in range(5)
    ]
    notices = past + [_n(), _n(bid_no="LATE", close_at="2026-11-05 10:00", org="다른청", nature="ISP·전략")]
    out = build_home(notices, [], {}, now=NOW)
    closing = out.split("<h2>마감 임박")[1].split("<h2>")[0]
    assert ">경쟁·낙찰 범위</th>" in closing
    assert "D-4 임박" not in closing
    assert 'class="dday"' in closing and "data-close=" in closing
    assert ">D-4</span>" in closing and ">D-6</span>" in closing
    assert "보통 6곳" in closing and "낙찰률 89.0~91.0%" in closing
    assert "비교 표본 부족" in closing
    soon = build_home([_n(close_at="2026-11-02 10:00")], [], {}, now=NOW)
    assert 'class="dday urgent"' in soon and ">D-3 임박</span>" in soon
    assert "11-02 10:00" in soon.split("<h2>마감 임박")[1].split("<h2>")[0]
    assert "closing-soon" in soon
    assert 'id="urgent-label"' in soon
    today = build_home([_n(close_at="2026-10-30 18:00")], [], {}, now=NOW)
    assert 'class="dday urgent"' in today and ">D-day 임박</span>" in today
    assert "최근 7일 새 공고" in out
    assert 'class="dday-collapse"' in soon
    # New-notices table must not get closing-soon (T-03)
    new_sec = soon.split("<h2>최근")[1].split("<h2>")[0]
    assert "closing-soon" not in new_sec


def test_home_fit_uses_rfp_summary(monkeypatch):
    """Home and detail must score with the same RFP summary (not title-only)."""
    from tests.test_gonogo_policy import PROFILE

    monkeypatch.setattr("g2b.gonogo.load_profile", lambda: PROFILE)
    notices = [
        _n(
            bid_no="R26BK01784078",
            title="GKL 카지노 연계 AI 관광 플랫폼 앱 구축 사업",
            org="그랜드코리아레저(주)",
            budget_eok=9.9,
            close_at="2026-11-05 10:00",
            notice_date="2026-10-21",
        )
    ]
    summary = {
        "R26BK01784078": {
            "summary": {
                "overview": "LLM 및 RAG 기술 기반 AI 챗봇",
                "tasks": ["LLM 챗봇 구축"],
                "tech": ["LLM", "RAG"],
                "requirements": [],
                "cautions": [],
                "evaluation": "",
            }
        }
    }
    without = build_home(notices, [], {}, now=NOW)
    with_sum = build_home(notices, [], {}, now=NOW, summaries=summary)
    assert "솔루션 미매칭" in without or "GenON S/A 솔루션 신호 없음" in without
    assert "솔루션 미매칭" not in with_sum.split("<h2>적합도")[1].split("<h2>")[0]


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


def test_proposal_markdown_omits_zero_budget():
    from g2b.detail import proposal_markdown

    md = proposal_markdown(_n(budget_eok=0), None, None)
    assert "예산:" not in md
    md2 = proposal_markdown(_n(budget_eok=12.0), None, None)
    assert "- 예산:" in md2 and "12" in md2.split("- 예산:")[1].split("\n")[0]


def test_render_detail_pages_stubs_reissue_via_prev_bid_no(tmp_path, monkeypatch):
    """U-02: orphan bid HTML becomes a noindex stub linking to the reissue."""
    from g2b.detail import render_detail_pages

    live = _n(
        bid_no="R26NEW",
        title="재공고 AI 챗봇 구축",
        prev_bid_no="R26OLD",
        notice_date="2026-11-20",
    )
    orphan = tmp_path / "bids"
    orphan.mkdir()
    (orphan / "R26OLD-000.html").write_text("<html>old</html>", encoding="utf-8")
    (orphan / "ORPHAN-000.html").write_text("<html>gone</html>", encoding="utf-8")

    monkeypatch.setattr("g2b.detail.load_detail_notices", lambda root: [live])
    monkeypatch.setattr("g2b.gonogo.load_profile", lambda: None)
    monkeypatch.setattr("g2b.rfp.load_summaries", lambda root: {})
    monkeypatch.setattr("g2b.pricing.load_notices", lambda root: [live])
    monkeypatch.setattr("g2b.plans.contracts_by_bid", lambda root: {})
    monkeypatch.setattr("g2b.prespecs.load_prespecs", lambda root: [])

    out = render_detail_pages(tmp_path, today=date(2026, 11, 21))
    assert out["pages"] == 1 and out["stubbed"] == 2

    reissue = (orphan / "R26OLD-000.html").read_text(encoding="utf-8")
    assert "이 공고 페이지는 더 이상 없습니다" in reissue
    assert 'href="R26NEW-000.html">대체·재공고 보기' in reissue
    assert 'name="robots" content="noindex,follow"' in reissue

    lonely = (orphan / "ORPHAN-000.html").read_text(encoding="utf-8")
    assert "홈으로" in lonely and "대체·재공고" not in lonely

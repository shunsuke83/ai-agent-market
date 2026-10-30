import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.assets import ASSET_VER, stamp_asset_versions
from g2b.normalize import band_excluded
from g2b.render import (
    band_winner_rollup,
    infer_status,
    org_type,
    quarter_counts,
    replace_note_after,
    replace_stat_card,
)

TODAY = date(2026, 10, 30)


def test_winner_overrides_stale_stored_status():
    n = {"status": "낙찰 미수집", "winner": "와이즈넛", "open_date": "2026-01-10"}
    assert infer_status(n, TODAY) == "낙찰"


def test_stale_upcoming_is_recomputed_after_open_date():
    n = {"status": "개찰 예정", "open_date": "2026-10-01"}
    assert infer_status(n, TODAY) == "결과 등록 대기"
    n = {"status": "결과 등록 대기", "open_date": "2026-06-01"}
    assert infer_status(n, TODAY) == "개찰 확인 필요"


def test_sourced_statuses_are_kept():
    assert infer_status({"status": "유찰", "open_date": "2026-01-01"}, TODAY) == "유찰"
    assert infer_status({"status": "1순위", "winner": "A", "open_date": "2026-01-01"}, TODAY) == "1순위"
    assert infer_status({"status": "재공고됨", "open_date": "2026-01-01"}, TODAY) == "재공고됨"


def test_band_excludes_non_build_work_but_keeps_builds():
    assert band_excluded({"title": "AI 플랫폼 구축 사업 감리 용역"})
    assert band_excluded({"title": "상용SW 제3자단가(AI LMS v2.0)"})
    assert band_excluded({"title": "광주 인공지능사관학교 AI 도약과정 위탁운영"})
    assert band_excluded({"title": "2026년 AI ICT 사업 성과(활용) 조사 분석 연구"})
    assert not band_excluded({"title": "부산대학교 AI 기반 맞춤형 교육지원시스템(3단계) 구축"})
    assert not band_excluded({"title": "생성형 AI 기반 민원 상담 플랫폼 구축"})


def test_org_type_examples():
    assert org_type("국방부 국군재정관리단") == "중앙행정·국방"
    assert org_type("경찰청 제주특별자치도경찰청") == "중앙행정·국방"
    assert org_type("경기도 용인시") == "지자체"
    assert org_type("한국공항공사") == "공기업·공단"
    assert org_type("부산대학교") == "교육·대학"
    assert org_type("한국지능정보사회진흥원") == "연구·진흥기관"
    assert org_type("한국생산성본부") == "연구·진흥기관"
    assert org_type("주식회사 이룸기술") == "기타"


def test_quarter_counts_marks_running_quarter():
    notices = [
        {"notice_date": "2026-07-01"},
        {"notice_date": "2026-09-30"},
        {"notice_date": "2026-10-02"},
    ]
    counts, current = quarter_counts(notices, TODAY)
    assert current == "26-Q4"
    assert counts == [("26-Q3", 2), ("26-Q4*", 1)]


def test_band_winner_rollup_counts_confirmed_awards_with_reported_amounts():
    notices = [
        {"winner": "A", "status": "낙찰 미수집", "budget_eok": 10, "win_rate_pct": 90},
        {"winner": "A", "status": "낙찰", "award_amount_eok": 5},
        {"first_rank": "C", "status": "1순위", "budget_eok": 20},
        {"winner": "B", "status": "유찰"},
    ]
    # Budget is never used as a stand-in amount; 1순위 is not an award.
    assert band_winner_rollup(notices) == [("A", 2, 5.0)]


def test_replace_stat_card_and_note():
    html = (
        '<div class="stat"><div class="v">2.0곳</div><div class="l">공고당 투찰 업체 (중앙값)</div></div>'
        '<h2>낙찰 업체</h2><div class="tbl"></div><p class="note">old</p>'
    )
    html = replace_stat_card(html, "공고당 투찰 업체 (중앙값)", "3.5곳")
    html = replace_note_after(html, "<h2>낙찰 업체</h2>", '<p class="note">new</p>')
    assert '<div class="v">3.5곳</div>' in html
    assert '<p class="note">new</p>' in html and "old" not in html


def test_stamp_asset_versions_rewrites_all_asset_refs():
    html = (
        '<link href="assets/site.css?v=20261029f">'
        '<script src="../assets/table-sort.js?v=20261029"></script>'
        '<script src="assets/table-filter.js?v=0"></script>'
    )
    out = stamp_asset_versions(html)
    assert out.count(f"?v={ASSET_VER}") == 3
    assert "20261029" not in out

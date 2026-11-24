import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.competitors import (
    aggregate_competitor_kpis,
    build_alias_index,
    build_spa_competitors,
    core_bidder_coverage,
    count_live_bids,
    load_competitors_config,
    match_competitor,
    normalize_firm,
    replace_overview_table,
    render_overview_row,
)

ROOT = Path(__file__).resolve().parents[2]


def test_normalize_firm_strips_corp_and_rank():
    assert normalize_firm("아이브릭스 (1순위)") == normalize_firm("아이브릭스")
    assert normalize_firm("(주)코난테크놀로지") == normalize_firm("코난테크놀로지")


def test_match_timeli_alias():
    comps = load_competitors_config()
    idx = build_alias_index(comps)
    assert match_competitor("타임리 (1순위)", idx) == "타임리(업스테이지)"
    assert match_competitor("코난테크놀로지", idx) == "코난테크놀로지"
    # Parenthetical alias must not absorb the other firm name
    assert match_competitor("업스테이지", idx) is None


def test_aggregate_uses_live_values_only():
    rows = aggregate_competitor_kpis(ROOT)
    assert len(rows) == 23
    for r in rows:
        assert r["wins"] == r["live_wins"]
        assert r["award_amount_eok"] == r["live_amount_eok"]
        assert r["bids"] == max(r["live_bids"], r["wins"])
    assert [(-r["wins"], -r["award_amount_eok"]) for r in rows] == sorted(
        (-r["wins"], -r["award_amount_eok"]) for r in rows
    )


def test_core_bidder_coverage_ratio():
    cov = core_bidder_coverage(
        [
            {
                "bid_no": "1",
                "open_date": "2026-10-01",
                "nature": "시스템 구축·고도화",
                "bidders": [{"name": "A"}],
            },
            {
                "bid_no": "2",
                "open_date": "2026-10-02",
                "nature": "시스템 구축·고도화",
            },
            {"bid_no": "3", "open_date": "2026-10-03", "nature": "인프라"},
        ]
    )
    assert cov["core_open"] == 2
    assert cov["with_bidders"] == 1
    assert abs(float(cov["ratio"]) - 0.5) < 1e-9


def test_count_live_bids_from_openg_bidders():
    idx = build_alias_index(load_competitors_config())
    names = {c["name"] for c in load_competitors_config()}
    notices = [
        {
            "bid_no": "A1",
            "bid_ord": "000",
            "winner": "와이즈넛",
            "bidders": [
                {"rank": 1, "name": "와이즈넛"},
                {"rank": 2, "name": "코난테크놀로지"},
                {"rank": 3, "name": "무관상사"},
            ],
        },
        {
            "bid_no": "A2",
            "bid_ord": "000",
            "winner": "코난테크놀로지",
            "bidders": [
                {"rank": 1, "name": "코난테크놀로지"},
                {"rank": 2, "name": "솔트룩스"},
            ],
        },
    ]
    bids = count_live_bids(notices, [], idx, names)
    assert len(bids["와이즈넛"]) == 1
    assert len(bids["코난테크놀로지"]) == 2
    assert len(bids["솔트룩스"]) == 1


def test_replace_overview_roundtrip():
    # Root competitors.html is an SPA redirect stub; use a minimal legacy table fixture.
    html = (
        "<h2>한눈에 보기</h2><div class=\"tbl\"><table>"
        "<thead><tr><th>x</th></tr></thead><tbody><tr><td>old</td></tr></tbody></table></div>"
    )
    row = render_overview_row(
        {
            "name": "테스트사",
            "type": "테스트",
            "bids": 1,
            "wins": 1,
            "award_amount_eok": 1.5,
            "own_model": "없음",
            "procurement": "미확인",
        }
    )
    updated = replace_overview_table(html, row)
    assert "테스트사" in updated
    assert 'class="num">1.5</td>' in updated
    assert updated.count("편집 조사 낙찰</th>") == 1
    assert replace_overview_table(updated, row).count('<p class="note">낙찰 건수 순.') == 1


def test_spa_competitors_includes_analysis_and_kpis():
    payload = build_spa_competitors(ROOT)
    assert payload["summary"]["listed"] == 23
    assert payload["summary"]["outside"] == 20
    assert payload["summary"]["firms"] == 43
    assert len(payload["firms"]) == 43
    assert payload["analysis"]["title"]
    assert payload["analysis"]["sections"]
    assert any(f["name"] == "와이즈넛" and f["wins"] >= 1 for f in payload["firms"])
    assert any(f.get("group") == "outside" for f in payload["firms"])

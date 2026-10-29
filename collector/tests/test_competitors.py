import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.competitors import (
    aggregate_competitor_kpis,
    build_alias_index,
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


def test_live_wins_can_raise_above_seed():
    rows = {r["name"]: r for r in aggregate_competitor_kpis(ROOT)}
    pub = rows["퍼블릭에이아이"]
    assert pub["live_wins"] >= 3
    assert pub["wins"] >= 3
    assert pub["award_amount_eok"] >= 40.0


def test_aggregate_keeps_seed_floor():
    rows = aggregate_competitor_kpis(ROOT)
    assert len(rows) == 23
    by_name = {r["name"]: r for r in rows}
    konan = by_name["코난테크놀로지"]
    # Seed was 7 wins / 106.5억 — must not regress
    assert konan["wins"] >= 7
    assert konan["award_amount_eok"] >= 106.5
    assert konan["bids"] >= konan["wins"]
    # Sorted by amount desc
    assert rows[0]["award_amount_eok"] >= rows[1]["award_amount_eok"]


def test_replace_overview_roundtrip():
    html = (ROOT / "competitors.html").read_text(encoding="utf-8")
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
